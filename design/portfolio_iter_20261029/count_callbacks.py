"""Count actual callbacks separately from the already measured SDK D.

Explicit offline diagnostic only. It builds independent snapshot/audit programs
under callback_checks/<check-tag>; it NEVER modifies/runs the shared engine or
retimes the SDK. Run only after other SDK timing windows have ended.

Example:
  python count_callbacks.py --tag members_standalone_r3 --ids 0,113

--check-tag defaults to --tag and must be new. The final report is the new
<check-tag>_callback_cost.json. Repeating a tag refuses to overwrite anything.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import math
import os
import re
import statistics
import subprocess


ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent
PROJECT = DESIGN.parent
KINDS = ('overflow', 'miss', 'periodic')
EXPECTED_CASES = 785


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write_new(path, body):
    with path.open('xb') as stream:
        stream.write(body)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2,
                       allow_nan=False) + '\n').encode('utf8')


def portable(path):
    try:
        return path.resolve().relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def safe_relative(value):
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts
            and ':' not in value and '\\' not in value, 'Unsafe stored relative path')
    return Path(*path.parts)


def resolve_source(mode, registered, summary):
    recorded = summary.get('candidate_sources', {}).get(str(mode))
    require(isinstance(recorded, dict), 'SDK report lacks source identity for mode ' + str(mode))
    if mode == 0:
        candidates = [DESIGN/'MySpillScheduler_neural.cpp']
    else:
        require(mode in registered, 'Only original NN mode0 or registered variants are supported')
        variant = registered[mode]
        require(variant['name'] == recorded['name'], 'Registered variant/SDK name mismatch')
        require(variant['sha256'] == recorded['sha256'], 'Registered variant/SDK source SHA mismatch')
        candidates = [ROOT/safe_relative(variant['source'])]
        declared = safe_relative(recorded['source'])
        candidates.append(PROJECT/declared if declared.parts[0] == 'design' else ROOT/declared)
    chosen = next((p for p in candidates if p.is_file()
                   and digest(p) == recorded['sha256']), None)
    require(chosen is not None, 'No source matches the frozen SDK identity for mode ' + str(mode))
    return dict(mode=mode, name=recorded['name'], source=chosen.resolve(),
                source_sha256=recorded['sha256'])


def input_population(summary, datasets_root):
    result = {}
    for dataset in summary['datasets']:
        member = dataset['member']
        require(safe_relative(member).parts == (member,), 'Invalid member directory')
        files = [f for f in dataset['files'] if f['path'].endswith('.txt')]
        require(len(files) == dataset['case_count'], 'Dataset case count mismatch')
        for item in files:
            key = member, item['sha256']
            require(key not in result, 'Duplicate member/input SHA')
            path = datasets_root/member/'eval'/safe_relative(item['path'])
            require(path.is_file() and digest(path) == item['sha256'],
                    'Original input differs from the frozen SDK SHA: ' + item['path'])
            with path.open('rb') as stream:
                header = stream.readline().removeprefix(b'\xef\xbb\xbf').split()
                require(len(header) == 6, 'Invalid original input header')
                penalty = int(header[5])
            result[key] = dict(member=member, filename=item['path'],
                input_sha256=item['sha256'], path=path.resolve(), penalty=penalty,
                version=dataset['version'])
    require(len(result) == EXPECTED_CASES, 'Expected all 785 original member inputs')
    return result


def sdk_measurements(summary, runs_path, ids, cases):
    repeats = summary['repeats']
    require(type(repeats) is int and repeats >= 1, 'Invalid SDK repeats')
    start = summary.get('repeat_index_base', 0)
    require(type(start) is int and start >= 0, 'Invalid repeat index base')
    repeat_ids = list(range(start, start+repeats))
    indexed = {}
    for line in runs_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line)
        if row['mode'] not in ids:
            continue
        identity = row['member'], row['case']
        require(identity in cases and row['repeat'] in repeat_ids, 'Unknown SDK input/repeat')
        key = row['member'], row['case'], row['mode'], row['repeat']
        require(key not in indexed, 'Duplicate SDK input/mode/repeat')
        require(all(type(row[k]) is int and row[k] >= 0 for k in ('Hit_Count', 'Miss_Count')),
                'Invalid SDK probe counts')
        require(all(isinstance(row[k], (int,float)) and math.isfinite(row[k]) and row[k] >= 0
            for k in ('Total_IO_Time', 'Total_Decision_Time', 'Total_Score')), 'Invalid SDK costs')
        expected = row['Total_IO_Time'] + cases[identity]['penalty']*row['Miss_Count'] + row['Total_Decision_Time']
        require(math.isclose(row['Total_Score'], expected, rel_tol=1e-15, abs_tol=.05),
                'SDK Score arithmetic mismatch')
        indexed[key] = row
    require(set(indexed) == {(member, case, mode, repeat) for member, case in cases
        for mode in ids for repeat in repeat_ids}, 'Incomplete selected SDK measurement grid')
    for mode in ids:
        mean_d = statistics.mean(indexed[member,case,mode,rep]['Total_Decision_Time']
            for member,case in cases for rep in repeat_ids)
        stated = summary['summary'][str(mode)]
        require(stated['cases'] == len(cases), 'SDK summary population mismatch')
        require(math.isclose(mean_d, stated['mean_decision_us'], rel_tol=1e-12, abs_tol=.000001),
                'SDK summary/raw D mismatch')
    return indexed, repeat_ids


def instrument_teacher(template):
    include = '#include "../MySpillScheduler_neural.cpp"'
    require(template.count(include) == 1, 'Unexpected teacher scheduler include')
    template = template.replace(include,
        '#define PORTFOLIO_AUDIT\n#include "scheduler.cpp"\n#undef PORTFOLIO_AUDIT', 1)
    entry = '    std::vector<Action> invoke(int kind,int o,int p,int64_t bytes){'
    require(template.count(entry) == 1, 'Unexpected Simulator.invoke entry')
    template = template.replace('struct Simulator {',
        'struct Simulator {\n    std::array<uint64_t,3> callback_counts{},classification_counts{};', 1)
    template = template.replace(entry, entry + '''
        if(kind<0||kind>2)throw std::runtime_error("invalid callback kind");
        ++callback_counts[kind];
        uint64_t classification_before=policy.inferenceCount();''', 1)
    end = 'cpu+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();return as;'
    require(template.count(end) == 1, 'Unexpected Simulator.invoke return')
    template = template.replace(end,
        'cpu+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();'
        'classification_counts[kind]+=policy.inferenceCount()-classification_before;return as;', 1)
    return template


AUDIT_MAIN = r'''// Independent callback/count audit. Its CPU timer is NOT SDK D.
#define main unused_offline_label_main
#include "teacher.cpp"
#undef main
static void invariant(const Simulator& s) {
    int64_t used=0;
    for(const auto& op:s.ops)for(const auto& p:op.partitions){
        if(p.data_size<0)throw std::runtime_error("negative partition size");
        if(p.in_memory)used+=p.data_size;
    }
    if(used!=s.used||used<0||used>s.input->m)throw std::runtime_error("memory invariant");
}
int main(int argc,char** argv){try{
    if(argc!=3)return 2;
    std::ifstream list(argv[1]);std::ofstream out(argv[2]);
    if(!list||!out)throw std::runtime_error("audit files");
    std::string path;int files=0;
    while(std::getline(list,path)){
        if(!path.empty()&&path.back()=='\r')path.pop_back();
        if(path.empty())continue;
        Input x=read(path);Simulator s(x,-1);
        while(s.pos<int(x.rows.size())){s.step();if(s.pos%1024==0)invariant(s);}
        invariant(s);
        uint64_t callbacks=0,classifications=0;
        for(int kind=0;kind<3;++kind){callbacks+=s.callback_counts[kind];classifications+=s.classification_counts[kind];}
        if(s.callback_counts[1]!=uint64_t(s.miss))throw std::runtime_error("miss callback count");
        if(s.callback_counts[2]!=uint64_t(s.count/x.b))throw std::runtime_error("periodic callback count");
        if(classifications!=s.policy.inferenceCount())throw std::runtime_error("classification count");
        out<<std::setprecision(17)<<"{\"file\":"<<quoted(path)<<",\"mode\":@@MODE@@"
            <<",\"io\":"<<s.io<<",\"hit\":"<<s.hit<<",\"miss\":"<<s.miss
            <<",\"action_hash\":"<<s.action_hash<<",\"classifications\":"<<classifications
            <<",\"callbacks\":"<<callbacks<<",\"overflow_callbacks\":"<<s.callback_counts[0]
            <<",\"miss_callbacks\":"<<s.callback_counts[1]<<",\"periodic_callbacks\":"<<s.callback_counts[2]
            <<",\"classification_by_kind\":["<<s.classification_counts[0]<<','<<s.classification_counts[1]<<','<<s.classification_counts[2]<<"]}\n";
        if(++files%128==0)std::cerr<<"Counted "<<files<<" cases\n";
    }
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
'''


def ratio(numerator, denominator):
    return numerator/denominator if denominator else None


def aggregate(rows, repeat_ids, repeat=None):
    counts = {kind: sum(r['callback_counts'][kind] for r in rows) for kind in KINDS}
    classifications = sum(r['classifications'] for r in rows)
    classify_counts = {kind: sum(r['classification_by_kind'][kind] for r in rows) for kind in KINDS}
    callbacks = sum(counts.values())
    selected_d = [r['sdk_D_by_repeat_us'][str(repeat)] if repeat is not None
                  else r['sdk_mean_D_us'] for r in rows]
    d = math.fsum(selected_d)
    return dict(cases=len(rows), total_D_us=d, mean_D_per_case_us=d/len(rows),
        callback_counts_per_suite_pass=counts, callbacks_per_suite_pass=callbacks,
        classifications_per_suite_pass=classifications,
        classification_by_kind_per_suite_pass=classify_counts,
        mean_callbacks_per_case=callbacks/len(rows),
        mean_classifications_per_case=classifications/len(rows),
        D_per_callback_mixed_us=ratio(d,callbacks),
        D_per_classification_mixed_us=ratio(d,classifications),
        D_per_inference_mixed_us=ratio(d,classifications),
        zero_callback_cases=sum(r['callbacks']==0 for r in rows),
        zero_classification_cases=sum(r['classifications']==0 for r in rows),
        note='D is the SDK total over ALL callback types; neither ratio is isolated classifier latency.')


def align_audit(output, mode, cases, sdk, repeat_ids):
    expected_by_path = {row['path'].as_posix(): identity for identity,row in cases.items()}
    seen = set()
    result = []
    max_error = 0.0
    for line in output.read_text(encoding='utf8').splitlines():
        measured = json.loads(line)
        key = measured['file'].replace('\\','/')
        require(key in expected_by_path, 'Auditor returned an unknown original input')
        identity = expected_by_path[key]
        require(identity not in seen and measured['mode'] == mode, 'Duplicate/wrong-mode audit record')
        seen.add(identity)
        count_fields = ('hit','miss','action_hash','callbacks','classifications',
                        'overflow_callbacks','miss_callbacks','periodic_callbacks')
        require(all(type(measured[k]) is int and measured[k]>=0 for k in count_fields),
                'Invalid audit counters')
        by_kind = measured['classification_by_kind']
        require(len(by_kind)==3 and all(type(v) is int and v>=0 for v in by_kind),
                'Invalid per-kind classification count')
        require(sum(by_kind)==measured['classifications'], 'Classification total mismatch')
        require(sum(measured[k+'_callbacks'] for k in KINDS)==measured['callbacks'],
                'Callback total mismatch')
        require(math.isfinite(measured['io']) and measured['io']>=0, 'Invalid audited IO')
        ds = {}
        for rep in repeat_ids:
            recorded = sdk[identity[0],identity[1],mode,rep]
            require(recorded['Hit_Count']==measured['hit'] and recorded['Miss_Count']==measured['miss'],
                    'Audited hit/miss differs from SDK')
            require(math.isclose(recorded['Total_IO_Time'],measured['io'],rel_tol=1e-12,abs_tol=.02),
                    'Audited IO differs from SDK')
            max_error = max(max_error,abs(recorded['Total_IO_Time']-measured['io']))
            ds[str(rep)] = recorded['Total_Decision_Time']
        meta=cases[identity]
        mean_d=statistics.mean(ds.values())
        result.append(dict(member=meta['member'],filename=meta['filename'],version=meta['version'],
            input_sha256=meta['input_sha256'], io_time_us=measured['io'],
            hit_count=measured['hit'],miss_count=measured['miss'], action_hash=measured['action_hash'],
            callbacks=measured['callbacks'],classifications=measured['classifications'],
            callback_counts={kind:measured[kind+'_callbacks'] for kind in KINDS},
            classification_by_kind=dict(zip(KINDS,by_kind)),
            sdk_repeats_matched=len(repeat_ids),sdk_D_by_repeat_us=ds,sdk_mean_D_us=mean_d,
            D_per_callback_mixed_us=ratio(mean_d,measured['callbacks']),
            D_per_classification_mixed_us=ratio(mean_d,measured['classifications']),
            D_per_inference_mixed_us=ratio(mean_d,measured['classifications'])))
    require(seen==set(cases), 'Auditor did not cover every original input')
    return sorted(result,key=lambda r:(r['member'],r['filename'])),max_error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag',default='members_standalone_r3',help='Completed SDK summary/runs tag')
    parser.add_argument('--ids',default='0,113')
    parser.add_argument('--check-tag',help='New audit tag; defaults to --tag')
    parser.add_argument('--datasets-root',type=Path,
        default=DESIGN/'member_eval_20261030/worktree/datasets')
    parser.add_argument('--cxx',default='g++')
    parser.add_argument('--timeout',type=float,default=600,
        help='Whole audit-program limit per mode; not a callback timer')
    args=parser.parse_args()
    check_tag=args.check_tag or args.tag
    require(all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}',t)
                for t in (args.tag,check_tag)), 'Use simple tags, not paths')
    require(math.isfinite(args.timeout) and args.timeout>0, 'Invalid audit timeout')
    ids=[int(v) for v in args.ids.split(',')]
    require(ids and len(ids)==len(set(ids)) and all(i>=0 and i!=2 for i in ids),
            'Use unique nonnegative scheduler IDs; Naive mode2 has no compatible policy instrumentation')
    work=ROOT/'callback_checks'/check_tag
    target=ROOT/(check_tag+'_callback_cost.json')
    require(not work.exists() and not target.exists(), 'Check tag already exists; refusing to overwrite')
    summary_path=ROOT/(args.tag+'_summary.json')
    runs_path=ROOT/(args.tag+'_runs.jsonl')
    frozen={path:digest(path) for path in (summary_path,runs_path)}
    summary=read(summary_path)
    require(summary.get('status','complete')=='complete' and summary['scope']=='members',
            'A completed member SDK batch is required')
    require(summary.get('tag')==args.tag and summary.get('protocol')=='official-2026-10-26',
            'Unexpected SDK batch tag/protocol')
    for mode in ids:
        require(str(mode) in summary['summary'], 'Requested mode was not measured in the SDK batch')
    variants_path=ROOT/'variants.json'
    variants={v['id']:v for v in read(variants_path)}
    sources=[resolve_source(mode,variants,summary) for mode in ids]
    datasets_root=args.datasets_root.expanduser().resolve(strict=True)
    cases=input_population(summary,datasets_root)
    sdk,repeat_ids=sdk_measurements(summary,runs_path,ids,cases)
    teacher_path=DESIGN/'neural_selector/teacher.cpp'
    types_path=DESIGN/'neural_selector/reference_types.hpp'
    frozen.update({path:digest(path) for path in (teacher_path,types_path)})
    teacher=instrument_teacher(teacher_path.read_text(encoding='utf8'))
    frozen.update({s['source']:s['source_sha256'] for s in sources})
    require(all(digest(path)==h for path,h in frozen.items()),
            'A bound source/report changed before the audit began')
    work.mkdir(parents=True,exist_ok=False)
    paths=work/'inputs.txt'
    write_new(paths,''.join(cases[k]['path'].as_posix()+'\n' for k in sorted(cases)).encode('utf8'))
    output={}
    for source in sources:
        mode=source['mode'];directory=work/('mode_'+str(mode));directory.mkdir(exist_ok=False)
        scheduler=directory/'scheduler.cpp'
        write_new(scheduler,source['source'].read_bytes())
        require(digest(scheduler)==source['source_sha256'], 'Source snapshot does not match SDK SHA')
        write_new(directory/'reference_types.hpp',types_path.read_bytes())
        write_new(directory/'teacher.cpp',teacher.encode('utf8'))
        audit=directory/'audit.cpp'
        write_new(audit,AUDIT_MAIN.replace('@@MODE@@',str(mode)).encode('utf8'))
        binary=directory/('audit.exe' if os.name=='nt' else 'audit')
        command=[args.cxx,'-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors',str(audit),'-o',str(binary)]
        subprocess_options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        compiled=subprocess.run(command,capture_output=True,text=True,**subprocess_options)
        write_new(directory/'compile.log',(compiled.stdout+compiled.stderr).encode('utf8'))
        require(compiled.returncode==0, 'Independent callback auditor failed to compile: mode '+str(mode))
        audited=directory/'counts.jsonl'
        ran=subprocess.run([str(binary),str(paths),str(audited)],capture_output=True,text=True,
                           timeout=args.timeout,**subprocess_options)
        write_new(directory/'audit.log',(ran.stdout+ran.stderr).encode('utf8'))
        require(ran.returncode==0, 'Independent callback audit failed: mode '+str(mode))
        rows,max_error=align_audit(audited,mode,cases,sdk,repeat_ids)
        members=sorted({r['member'] for r in rows})
        output[str(mode)]=dict(name=source['name'],source=portable(source['source']),
            source_sha256=source['source_sha256'],source_snapshot_sha256=digest(scheduler),
            sdk_binary_sha256=(summary.get('binary_sha256_by_mode') or summary.get('binary_sha256',{})).get(str(mode)),
            auditor_binary_sha256=digest(binary),auditor_source_sha256=digest(audit),
            instrumented_teacher_sha256=digest(directory/'teacher.cpp'),
            strict_actions=True,audit_macro_enabled=True,
            feature_prediction_parity_enabled=('routeReference' in scheduler.read_text(encoding='utf8')
                and 'PORTFOLIO_AUDIT' in scheduler.read_text(encoding='utf8')),
            sdk_measurements_matched=len(rows)*len(repeat_ids),io_hit_miss_match=True,
            max_abs_io_difference_us=max_error,
            aggregate=aggregate(rows,repeat_ids),
            by_member={m:aggregate([r for r in rows if r['member']==m],repeat_ids) for m in members},
            per_repeat=[dict(repeat=rep,aggregate=aggregate(rows,repeat_ids,rep),
                by_member={m:aggregate([r for r in rows if r['member']==m],repeat_ids,rep) for m in members})
                for rep in repeat_ids],cases=rows)
        print('Counted and matched mode',mode,len(rows),'cases;',len(repeat_ids),'SDK repeats',flush=True)
    require(all(digest(path)==h for path,h in frozen.items()), 'A bound source/report changed during audit')
    require(all(digest(row['path'])==row['input_sha256'] for row in cases.values()),
            'An original input changed during audit')
    result=dict(status='passed',measurement_tag=args.tag,check_tag=check_tag,
        suite_id=summary['suite_id'],cases=len(cases),sdk_repeats=len(repeat_ids),modes=ids,
        operation='Independent semantic callback/count audit; existing SDK D reused, not retimed.',
        counter_location='Simulator.invoke entry before isChoice; periodic includes empty/no-choice calls.',
        classification_counter='Actual policy.inferenceCount increment measured for each callback kind.',
        D_source='Original timed SDK runs; offline auditor.cpu is discarded.',
        aggregate_definition='Sum of per-case arithmetic-mean SDK D divided by callbacks/classifications in one audited suite pass; per-repeat ratios also retained.',
        interpretation=[
            'D/callback mixes state snapshots, routing, feedback, expert planning and all callback types.',
            'D/classification also includes D from callbacks with no classification; it is NOT isolated route/inference latency.',
            'Policies can change callback counts and callback mix; neither D/case nor these normalized ratios alone proves that a tree routes faster than an NN.',
            'No microbenchmark, per-kind D attribution or modification to SDK timing was performed.'],
        io_tolerance=dict(abs_us=.02,relative=1e-12),
        evidence_files={portable(path):h for path,h in frozen.items()},
        generator_sha256=digest(Path(__file__)),audit_directory=portable(work),candidates=output)
    write_new(target,json_bytes(result))
    print('Wrote',target,flush=True)


if __name__=='__main__':
    main()
