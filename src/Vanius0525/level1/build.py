"""Build the saved reference verbatim, inserting only a scheduler and its selection.
Generated engines/binaries stay in ignored build/. --audit is for correctness only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
FROZEN = REPO / 'docs/statement-2026-10-20/statement.md'
FROZEN_SHA = '464a542ad56f0b81ebad23371846a705c202c4461589a5f37d65af5a65c99d69'

AUDIT = r'''
#include <cstdlib>
class AuditScheduler : public SpillScheduler {
    MySpillScheduler inner_;
    void log(char tag, int op, int pid, int64_t bytes, const std::vector<Action>& a) {
        std::cerr << "TRACE " << tag << " " << op << " " << pid << " " << bytes << " " << a.size();
        for (const auto& x : a) std::cerr << " " << (x.type == Action::SPILL ? 'S' : 'L') << " " << x.op_id << " " << x.partition_id;
        std::cerr << '\n';
    }
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t z) override {
        auto a=inner_.onMemoryOverflow(s,o,p,z); log('O',o,p,z,a); return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        auto a=inner_.onPartitionMiss(s,o,p); log('M',o,p,0,a); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        auto a=inner_.onPeriodicAdjust(s); log('P',-1,-1,0,a); return a;
    }
};
'''

def build(scheduler=None, name=None, audit=False, sanitize=False):
    raw = FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(
        ['git', 'show', '11b719b:docs/statement-2026-10-20/statement.md'], cwd=REPO)
    assert hashlib.sha256(raw).hexdigest() == FROZEN_SHA
    blocks = re.findall(r'```cpp\n(.*?)```', raw.decode(), re.S)
    ref = next(b for b in blocks if 'class HashJoinEngine' in b)
    ref = ref.replace('\xa0', ' ')
    engine_before = ref.split('class HashJoinEngine', 1)[1].split('/* ===== 主函数', 1)[0]
    chosen = 'NaiveSpillScheduler'
    if scheduler:
        scheduler = Path(scheduler).resolve()
        source_bytes = scheduler.read_bytes()
        snapshot_dir = ROOT / 'build/source_snapshots'
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot = snapshot_dir / (hashlib.sha256(source_bytes).hexdigest() + '.cpp')
        if snapshot.exists():
            assert snapshot.read_bytes() == source_bytes
        else:
            snapshot.write_bytes(source_bytes)
        insert = source_bytes.decode()
        assert 'class MySpillScheduler' in insert and 'int main(' not in insert
        if audit:
            insert += AUDIT
        ref = ref.replace('class HashJoinEngine', insert + '\nclass HashJoinEngine', 1)
        chosen = 'AuditScheduler' if audit else 'MySpillScheduler'
    assert engine_before == ref.split('class HashJoinEngine', 1)[1].split('/* ===== 主函数', 1)[0]
    ref = ref.replace('std::make_unique<NaiveSpillScheduler>()', 'std::make_unique<' + chosen + '>()')
    out = ROOT / 'build'
    out.mkdir(exist_ok=True)
    name = name or (scheduler.stem if scheduler else 'official_naive')
    if audit: name += '_audit'
    if sanitize: name += '_sanitize'
    src = out / (name + '.cpp')
    exe = out / name
    src.write_text(ref)
    cmd = ['g++', '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic', str(src), '-o', str(exe)]
    if sanitize: cmd[3:3] = ['-g', '-fsanitize=undefined,address', '-fno-omit-frame-pointer']
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    meta = {'command': cmd, 'reference_sha256': FROZEN_SHA,
            'scheduler_sha256': hashlib.sha256(scheduler.read_bytes()).hexdigest() if scheduler else None,
            'engine_unchanged': True, 'audit': audit, 'sanitize': sanitize}
    (out / (name + '.build.json')).write_text(json.dumps(meta, indent=2) + '\n')
    return exe

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('scheduler', type=Path, nargs='?')
    p.add_argument('--name');p.add_argument('--audit', action='store_true');p.add_argument('--sanitize',action='store_true')
    a=p.parse_args(); print(build(a.scheduler,a.name,a.audit,a.sanitize))
