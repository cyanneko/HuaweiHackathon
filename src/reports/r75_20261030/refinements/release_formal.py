from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[2];out=root/'tmp/r75_handoff'
p=out/'producer.json'
release=dict(released=True,final_sources_frozen=True,review_passed=True,all_compilation_released=True,
    diagnostics_compute_released=True,producer_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    independent_review='tmp/r75_final_review; final dense switch compile, callback, cache, threshold and exposure tests passed',
    master_release='Master confirmed all pushes exited and no active IO; old R74 main/source/data publication verified.',
    scope='32 main cells over 8 complete cases; optional separately reported 3-cell dense targeted regression, never pooled into main score')
(out/'release.json').write_text(json.dumps(release,indent=2)+'\n')
