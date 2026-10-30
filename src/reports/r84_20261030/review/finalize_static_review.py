"""Final small-artifact binding; does not bind/prepare selections or execute native code."""
from pathlib import Path
import json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUNNER=ROOT/'tmp/r84_full_eval';sys.path.insert(0,str(RUNNER))
import inventory as inv
import test_protocol
folder=ROOT/'tmp/r84_van_build';p=inv.read(folder/'producer.json');proof=inv.read(folder/'latest_proof.json');release=inv.read(folder/'release.json');test=inv.read(folder/'test_summary.json')
assert inv.sha(folder/'producer.json')=='b6603fce041ba7e0ece971f4835a12284bfbd5e7ea5b761639a02a021443f4cc'
assert inv.sha(folder/'latest_proof.json')=='13e23973c1f3aca1aad7b0398d00563579c52c94fb6ddcc2d4c523a57ed3f17b'
assert release['final'] and release['active_child_processes']==0 and release['producer_sha256']==inv.sha(folder/'producer.json')
assert test['status']=='PASS' and release['test_summary_sha256']==inv.sha(folder/'test_summary.json')
assert proof['status']=='VERIFIED_LATEST_SUBMITTABLE_AT_CAPTURE' and inv.sha(ROOT/proof['evidence_path'])==proof['evidence_sha256']
van=p['variants'][0];assert van['name']=='Van_latest' and van['source_commit']==proof['source_commit'] and van['source_sha256']==proof['source_sha256']
assert van['source_branch']==proof['source_branch'] and van['upstream_source_path']==proof['source_repo_path']
inv.verify_source(van,elf=True)
ref=inv.read(ROOT/p['source_reference_path']);assert inv.sha(ROOT/p['source_reference_path'])==p['source_reference_sha256']
old=next(m for m in ref['methods'] if m['name']=='Van_paired_penalty100')
for key in ['source_sha256','translation_unit_sha256','binary_sha256']:assert van[key]==old[key]
assert test['old_compile_record']['returncode']==0 and test['old_compile_record']['argv'][:3]==['g++','-std=c++14','-O2']
assert inv.sha(ROOT/test['old_test_summary_path'])==test['old_test_summary_sha256']
tests=test_protocol.tests()
files=['tmp/r84_full_eval/regression.py','tmp/r84_full_eval/inventory.py','tmp/r84_full_eval/scoring.py','tmp/r84_full_eval/test_protocol.py','tmp/r84_full_eval/README.md','tmp/r84_full_eval/dyna.inventory.json','tmp/r84_full_eval/final.inventory.json','tmp/r84_full_eval/base_methods.prepared.json','tmp/r84_review/static_review.json','tmp/r84_review/STATIC_REVIEW.md','tmp/r84_review/finalize_static_review.py']
files += ['tmp/r84_van_build/'+n for n in ['producer.json','latest_proof.json','release.json','test_summary.json','environment.json']]
files += [inv.PROOF,inv.AMENDMENT,'docs/superpowers/plans/2026-10-30-r84-van-full-comparison.md',proof['evidence_path']]
out=dict(status='PASS_STATIC_READY_FOR_ROOT_BIND_PREPARE',methods=7,planned_dyna_cases=12,planned_final_cases=72,planned_dyna_cells=84,planned_final_cells=504,planned_cells=588,
    protocol_tests=tests,Van_latest=van,Van_build='REUSE_VERIFIED_IDENTICAL_SOURCE_TU_ELF; no new compilation/solver test',
    current_environment_path='tmp/r84_van_build/environment.json',current_environment_bound_in_selection_dependencies=True,
    input_gate='Root prepare not executed by this agent; full input SHA and headers still required',
    ELF_scope='Van ELF rehashed here, historical six ELF hashes deferred to Linux prepare',
    no_native_runs=True,no_large_input_scans=True,dependencies={n:inv.sha(ROOT/n) for n in files})
inv.save(HERE/'final_static_review.json',out)
print(json.dumps(dict(status=out['status'],runner_sha256=inv.sha(RUNNER/'regression.py'),review_sha256=inv.sha(HERE/'final_static_review.json'),README_sha256=inv.sha(RUNNER/'README.md'))))
