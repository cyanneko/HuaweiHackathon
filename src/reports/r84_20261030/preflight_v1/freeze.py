"""One-time static release; no selection preparation or input/body access."""
from pathlib import Path
import json
import inventory as inv
import test_protocol
H=inv.HERE;ROOT=inv.ROOT;R=ROOT/'tmp/r84_review'
assert not (H/'release.json').exists() and not (H/'methods.prepared.json').exists()
assert not (H/'dyna/selection.json').exists() and not (H/'final/selection.json').exists()
tests=test_protocol.tests();assert tests==inv.read(R/'protocol_tests.json')
review=inv.read(R/'final_static_review.json')
for rel in review['dependencies']:review['dependencies'][rel]=inv.sha(ROOT/rel)
review['final_release_gate']='Runner requires final release and pins its tests/review/environment artifacts into both selections.'
(R/'final_static_review.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
art=dict(review['dependencies'])
for rel in ['tmp/r84_review/final_static_review.json','tmp/r84_review/protocol_tests.json','tmp/r84_full_eval/freeze.py']:
    art[rel]=inv.sha(ROOT/rel)
release=dict(status='READY',ready=True,final=True,active_child_processes=0,solver_runs=0,compile_runs=0,input_body_scans=0,static_status='PASS',
    expected_methods=7,planned_dyna_cells=84,planned_final_cells=504,planned_total_cells=588,
    protocol_tests_sha256=inv.sha(R/'protocol_tests.json'),review_sha256=inv.sha(R/'final_static_review.json'),
    runner_sha256=inv.sha(H/'regression.py'),scorer_sha256=inv.sha(H/'scoring.py'),artifacts=art)
inv.save(H/'release.json',release)
print(json.dumps(dict(status='FINAL_READY',release_sha256=inv.sha(H/'release.json'),runner_sha256=release['runner_sha256'],review_sha256=release['review_sha256'],scorer_sha256=release['scorer_sha256'])))
