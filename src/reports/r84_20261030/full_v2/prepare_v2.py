"""One-time pre-execution v2 copy. V1 files remain byte-for-byte untouched."""
from pathlib import Path
import hashlib,json,shutil
H=Path(__file__).resolve().parent;ROOT=H.parents[1];OLD=ROOT/'tmp/r84_full_eval'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(H/n).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
assert not (OLD/'dyna/selection.json').exists() and not (OLD/'final/selection.json').exists()
assert not list(OLD.glob('*/campaign.json'))
original={p.relative_to(ROOT).as_posix():sha(p) for p in OLD.rglob('*') if p.is_file()}
save('v1_file_hashes.json',original)
for name in ['inventory.py','regression.py','scoring.py','test_protocol.py','README.md','base_methods.prepared.json','methods.prepared.json']:
    assert not (H/name).exists();shutil.copyfile(OLD/name,H/name)
save('failed_preparation.json',dict(status='V1_PRE_EXECUTION_PREPARE_FAILED',failure='AssertionError: metadata inventory changed',stage='prepare dyna; fresh inventory compared to frozen inventory before input hash loop',
    methods_binding_sha256=sha(OLD/'methods.prepared.json'),selection_files=0,campaign_files=0,solver_runs=0,
    diagnosis='Only dependency dictionary path separators differ between Windows frozen and Linux fresh. Dyna3 keys/final2 keys; all corresponding SHA and all other fields equal.',
    observed_diff=dict(dyna=['tmp/d70/dyna_dataset/manifest.json','tmp/d70/dyna_dataset/dataset.json','tmp/d70/dyna_dataset/VERSION'],final=['tmp/d70/final_dataset/manifest.json','tmp/d70/final_dataset/eval/VERSION']),
    evidence_source='Root failure report plus separate Linux metadata-only recursive comparisons before v2; no whole-input hash/solver execution',v1_unchanged=True))
print('V1 snapshots and necessary v2 copies ready; no source edits or scans yet')
