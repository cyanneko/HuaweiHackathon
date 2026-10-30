"""C++14 syntax/type check through unchanged official declarations, no executable."""
import hashlib
import json
import re
import subprocess
import sys
from prepare_v1 import ROOT, HERE, sha, save
sys.path.insert(0, str(ROOT))
import build
from workflow import experiment_lock


def main():
    with experiment_lock():
        source = HERE / 'R80_soft_tail100_v1.cpp'
        plan = json.loads((HERE / 'PLAN_PROPOSAL_V1.json').read_text())
        assert sha(source) == plan['sources']['soft_tail100']['sha256']
        raw = build.FROZEN.read_bytes() if build.FROZEN.exists() else subprocess.check_output(
            ['git', 'show', '11b719b:docs/statement-2026-10-20/statement.md'], cwd=build.REPO)
        assert hashlib.sha256(raw).hexdigest() == build.FROZEN_SHA
        ref = next(b for b in re.findall(r'```cpp\n(.*?)```', raw.decode(), re.S) if 'class HashJoinEngine' in b).replace('\xa0', ' ')
        before = ref.split('class HashJoinEngine', 1)[1].split('/* ===== 主函数', 1)[0]
        full = ref.replace('class HashJoinEngine', source.read_bytes().decode() + '\nclass HashJoinEngine', 1)
        assert before == full.split('class HashJoinEngine', 1)[1].split('/* ===== 主函数', 1)[0]
        full = full.replace('std::make_unique<NaiveSpillScheduler>()', 'std::make_unique<MySpillScheduler>()')
        command = ['g++', '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic', '-fsyntax-only', '-x', 'c++', '-']
        proc = subprocess.run(command, input=full, text=True, capture_output=True)
        (HERE / 'STATIC_COMPILER_STDERR_V1.txt').write_text(proc.stderr)
        save(HERE / 'STATIC_CHECK_V1.json', {'passed': proc.returncode == 0, 'returncode': proc.returncode,
            'command': command, 'candidate_sha256': sha(source), 'plan_sha256': sha(HERE / 'PLAN_PROPOSAL_V1.json'),
            'official_framework_sha256': build.FROZEN_SHA, 'engine_unchanged': True,
            'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
            'stderr_sha256': sha(HERE / 'STATIC_COMPILER_STDERR_V1.txt'),
            'executable_built': False, 'solver_runs': 0, 'input_file_reads': 0,
            'scope': 'Syntax and type checking only; no performance, empirical action equivalence, or legality proof.'})
        assert proc.returncode == 0, proc.stderr
        print('C++14/O2 syntax check passed; zero solver/input reads')


if __name__ == '__main__':
    main()
