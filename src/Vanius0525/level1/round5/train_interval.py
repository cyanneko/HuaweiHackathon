"""Train-only 256-observation configuration intervention with two continuations.

Full remaining streams are used offline; online features remain callback-only.
This is a conditional counterfactual teacher, never a global optimum claim.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
from sklearn.tree import DecisionTreeRegressor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'round4'))
from build import FROZEN, FROZEN_SHA, REPO, build
from replay import parse_input, parse_output
from workflow import experiment_lock
from round5.audit_splits import audit
from lazy_gate_family import source


def interval_source(gate='return 0;', force=-1):
    s = source(gate, force)
    s = s.replace('int selected_mode_=-1;',
                  'int selected_mode_=-1; int64_t last_selection_=-1,rollout_end_=-1; int fallback_=0;')
    s = s.replace('uniform_cycle_=false;selected_mode_=-1;',
                  'uniform_cycle_=false;selected_mode_=-1;last_selection_=-1;')
    s = s.replace('        int mode=forced_mode_;', '''        if(rollout_end_>=0 && observed_count_>=rollout_end_) {
            forced_mode_=fallback_;rollout_end_=-1;
        }
        int mode=forced_mode_;''')
    s = s.replace('if(selected_mode_<0 && observed_count_>=32)',
                  'if(observed_count_>=32 && (selected_mode_<0 || observed_count_-last_selection_>=256))')
    s = s.replace('selected_mode_=gate(gf);', 'selected_mode_=gate(gf);last_selection_=observed_count_;')
    s = s.replace('    void forceMode(int mode)', '''    int64_t observedClock() const {return observed_count_;}
    void forceInterval(int mode,int64_t end,int fallback) {
        forced_mode_=mode;rollout_end_=end;fallback_=fallback;
    }
    void forceMode(int mode)''')
    return s


def teacher_source():
    raw = FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(
        ['git', 'show', '11b719b:docs/statement-2026-10-20/statement.md'], cwd=REPO)
    assert hashlib.sha256(raw).hexdigest() == FROZEN_SHA
    ref = next(b for b in re.findall(r'```cpp\n(.*?)```', raw.decode(), re.S)
               if 'class HashJoinEngine' in b).replace('\xa0', ' ')
    declarations = ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    t = (ROOT / 'teacher.cpp').read_text().replace('// OFFICIAL_DECLARATIONS', declarations)
    t = t.replace('// POLICY_DEFINITION', interval_source(force=0))
    # Uniform reservoir over eligible legal states, rather than early-prefix rows.
    marker = '    MySpillScheduler base;base.forceMode(0);int events=0,samples=0;'
    preview = '''    Sim initial=sim;MySpillScheduler preview;preview.forceMode(0);
    std::vector<int> selected;std::mt19937 rng(510030);int eligible=0;
    for(int i=0;i<n;++i) {
        const auto& o=ops[i];sim.pending(ops,i);bool decision=false;
        if(o.type=="INSERT")decision=sim.s.operators[o.op].partitions[o.pid].in_memory && sim.s.memory_used+o.bytes>m;
        if(o.type=="PROBE")decision=!sim.s.operators[o.op].partitions[o.pid].in_memory;
        if(decision) {
            Sim fs=sim;MySpillScheduler fp=preview;if(o.type=="PROBE")++fs.s.miss_count;
            float f[14];fp.prepareFeatures(fs.s,o.op,o.pid,o.type=="INSERT"?o.bytes:fs.s.operators[o.op].partitions[o.pid].data_size,o.type=="PROBE",f);
            if(fp.gateReady(fs.s)) {
                ++eligible;
                if(static_cast<int>(selected.size())<max_samples)selected.push_back(i);
                else {int j=std::uniform_int_distribution<int>(0,eligible-1)(rng);if(j<max_samples)selected[j]=i;}
            }
        }
        sim.step(ops,i,preview);
    }
    std::sort(selected.begin(),selected.end());sim=initial;
'''
    assert marker in t
    t = '#include <random>\n' + t.replace(marker, preview + marker)
    t = t.replace('if(decision && ++events%stride==0 && samples<max_samples)',
                  'if(decision && std::binary_search(selected.begin(),selected.end(),i))')
    t = t.replace('float f[12];', 'float f[14];')
    t = t.replace('            std::vector<double> losses;', '''            f[12]=std::log2(sim.s.read_bandwidth/sim.s.write_bandwidth)/14.;
            f[13]=std::log2(sim.s.write_bandwidth)/14.;
            std::vector<double> losses;''')
    t = t.replace('for(int mode=0;mode<6;++mode)', 'for(int continuation: {0,2}) for(int mode: {0,2,3})')
    t = t.replace('policy.forceMode(mode);',
                  'policy.forceInterval(mode,feature_policy.observedClock()+256,continuation);')
    t = t.replace('                policy.forceMode(0);', '')
    t = t.replace('std::min(n,i+1+horizon)', 'n')
    t = t.replace('losses.push_back(trial.cost-sim.cost);', 'losses.push_back(trial.cost);')
    t = t.replace('if(hi-lo>1e-6)', 'if(true)')
    return t


def main(train_data=None, val_data=None, output_dir=None, candidate_path=None,
         report_path=None, max_samples=12):
    started = time.time()
    train_data = Path(train_data) if train_data is not None else ROOT / 'build/data/train'
    val_data = Path(val_data) if val_data is not None else ROOT / 'build/data/val'
    folder = Path(output_dir) if output_dir is not None else ROOT / 'build/round5-interval-train'
    folder.mkdir(exist_ok=False)  # Keep partial runs; never silently overwrite.
    check = audit({'train': train_data, 'val': val_data})
    assert check['passed']
    teacher = folder / 'teacher.cpp'
    teacher.write_text(teacher_source())
    exe = folder / 'teacher'
    subprocess.run(['g++', '-std=c++14', '-O2', str(teacher), '-o', str(exe)], check=True)
    base = folder / 'base.cpp'
    base.write_text(interval_source(force=0))
    base_exe = build(base, 'r5_interval_base')
    naive = build(name='r5_interval_naive')
    x, y, groups, sources = [], [], [], []
    conflicts = 0
    for group, case in enumerate(sorted(train_data.glob('*.txt'))):
        proc = subprocess.run([str(exe), str(case), '0', '1', str(max_samples)],
                              capture_output=True, text=True, check=True, timeout=300)
        (folder / (case.stem + '.rows')).write_text(proc.stdout)
        (folder / (case.stem + '.log')).write_text(proc.stderr)
        official = parse_output(subprocess.check_output([str(base_exe), str(case)], text=True, timeout=60))
        pen = parse_input(case)[0][5]
        sim = re.search(r'SIM ([\deE.+-]+) (\d+) (\d+)', proc.stderr)
        assert sim
        physical = official['Total_IO_Time'] + pen * official['Miss_Count']
        assert abs(float(sim[1]) - physical) <= max(.1, physical * 2e-5)
        assert int(sim[2]) == official['Hit_Count'] and int(sim[3]) == official['Miss_Count']
        nv = parse_output(subprocess.check_output([str(naive), str(case)], text=True, timeout=60))
        bc = nv['Total_IO_Time'] + pen * nv['Miss_Count']
        for line in proc.stdout.splitlines():
            if not line.startswith('ROW '):
                continue
            row = np.asarray(list(map(float, line.split()[2:])), dtype=np.float64)
            assert len(row) == 20
            costs = row[14:].reshape(2, 3)
            scores = 10 * np.clip(1 - costs / bc, 0, 1) if bc > 0 else np.zeros_like(costs)
            gains = scores - scores[:, :1]
            # A configuration must beat default under BOTH continuation teachers.
            conflicts += int(np.argmax(scores[0]) != np.argmax(scores[1]))
            target = np.min(gains, axis=0)
            x.append(row[:14]); y.append(target); groups.append(group)
        sources.append({'file': case.name, 'sha256': hashlib.sha256(case.read_bytes()).hexdigest(), 'split': 'train'})
        print(json.dumps({'traces': group+1, 'rows': len(x), 'seconds': time.time()-started}), flush=True)
    x, y, groups = np.asarray(x, np.float32), np.asarray(y, np.float64), np.asarray(groups)
    assert len(x) > 0
    np.savez_compressed(folder / 'rows.npz', x=x, y=y, groups=groups)
    weights = 1 / np.bincount(groups)[groups]
    model = DecisionTreeRegressor(max_depth=3, min_samples_leaf=24, random_state=510030)
    model.fit(x, y, sample_weight=weights)
    t = model.tree_

    def expr(i):
        if t.children_left[i] < 0:
            values = t.value[i, :, 0]
            best = int(np.argmax(values))
            return str([0, 2, 3][best] if values[best] >= .05 else 0)
        return f'(f[{t.feature[i]}]<={t.threshold[i]:.10g}?{expr(t.children_left[i])}:{expr(t.children_right[i])})'

    target = Path(candidate_path) if candidate_path is not None else HERE / 'ai_interval256_d3.cpp'
    with target.open('x') as out:
        out.write(interval_source('return ' + expr(0) + ';'))
    report = {'sources': sources, 'rows': len(x), 'continuation_ranking_disagreements': conflicts,
              'training_weight': 'equal total mass per contributing flow',
              'teacher': '256 distinct legal observed ordinals per configuration intervention; complete suffix; separate forced 0 and 2 continuations; minimum score gain across both',
              'target': 'clipped per-flow relative IO+Miss score gain to Naive; decision CPU excluded and must be measured in deployment',
              'collector': f'pure forced0, uniform reservoir{max_samples} per eligible flow, >=32 observed ordinals; no evaluation fitting',
              'limitations': 'conditional teacher, not OPT; collector state shift; near-end shorter intervals; no zero-baseline gain; no hidden penalty in online features',
              'teacher_sha256': hashlib.sha256(teacher.read_bytes()).hexdigest(),
              'candidate_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'seconds': time.time()-started}
    report_target = Path(report_path) if report_path is not None else HERE / 'INTERVAL_TRAINING.json'
    with report_target.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    with experiment_lock():
        main()
