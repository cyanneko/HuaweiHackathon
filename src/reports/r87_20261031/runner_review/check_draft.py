"""Linux small-contract evidence before producer binding. Never prepares inputs."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'tmp/r87_eval'))
import inventory as inv,test_r87
assert sys.platform.startswith('linux')
tests=test_r87.tests();counts={m:inv.build_inventory(m)['case_count'] for m in ['dyna','final']}
files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tmp/r87_eval').iterdir() if p.is_file()}
result=dict(status='DRAFT_TESTS_PASS_AWAIT_PRODUCER_AND_ROOT_APPROVAL',linux_protocol_tests=tests,metadata_case_counts=counts,files=files,
    missing_contracts=['Exact R87 producer SHA and READY framework_unchanged single variant','Source/TU/ELF hashes, g++ C++14/O2 flags, noninstrumented, parent A three hashes','PASS test_summary SHA, source manifest SHA, final ready RELEASED active0 producer release','Root approval before freeze.py --root-approved'],
    not_created=['release.json','methods.prepared.json','dyna/selection.json','final/selection.json'],
    pre_execution_failures=['parent_red.stderr: expected unsupported new method matrix on old scorer','inventory_red.stderr: repaired incorrect assumption that dyna raw inputs use d70'],
    runtime_failures=0,native_runs=0,compile_runs=0,input_body_scans=0,active_child_processes=0)
with (OUT/'draft_review.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(status=result['status'],runner_sha256=files['tmp/r87_eval/regression.py'],draft_review_sha256=hashlib.sha256((OUT/'draft_review.json').read_bytes()).hexdigest())))
