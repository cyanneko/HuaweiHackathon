"""Retain unchanged weights after independently checking repaired label inputs."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

OUT=Path(__file__).resolve().parent
ROUND=OUT.parent
WORKSPACE=ROUND.parents[3]
sys.path[:0]=[str(ROUND),str(WORKSPACE/'tmp/r66_root_nn')]
from core import Case,State,digest,pool,features,action_key
from tiny_train import prepare_rows

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return [json.loads(x) for x in p.read_text().splitlines()]

def main():
    old=ROUND/'snapshot_p1_invalid_audit/path_demo.INVALID.jsonl'
    new=ROUND/'pilot_exact_04/path_demo.jsonl'
    before,after=read(old),read(new)
    a,b=prepare_rows(before),prepare_rows(after)
    for key in ('x','valid','selected','weights'):
        assert np.array_equal(a[key],b[key]),key
    assert a['action_keys']==b['action_keys'] and len(after)==44
    entries=json.loads((ROUND/'data/train_manifest.json').read_text())['cases']
    case=Case.read(next(e['input'] for e in entries if e['selection_id']=='exact_04'))
    for row in after:
        assert digest(row['full_state_snapshot'])==row['anchor_snapshot_hash']
        assert digest(row['full_state_snapshot']['history'])==row['history_snapshot_hash']
        s=State.from_snapshot(case,json.loads(json.dumps(row['full_state_snapshot'])))
        plans=pool(s)
        assert [action_key(s,p) for p in plans]==[p['action_key'] for p in row['plans']]
        assert [features(s,p) for p in plans]==[p['x'] for p in row['plans']]
    tensor_hash=hashlib.sha256()
    for key in ('x','valid','selected','weights'):
        tensor_hash.update(key.encode());tensor_hash.update(b[key].tobytes())
    provenance=dict(original_labels_invalid_for_snapshot_reconstruction=True,
                    original_labels_sha256=sha(old),corrected_labels_sha256=sha(new),
                    training_tensor_sha256=tensor_hash.hexdigest(),
                    all_training_tensors_masks_labels_and_weights_identical=True,
                    corrected_anchors_independently_reconstructed=44,
                    model_weight_disposition='retained_unchanged_no_retraining',
                    model_sha256=sha(OUT/'model.json'),corrected_core_sha256=sha(ROUND/'core.py'),
                    repair_report_sha256=sha(ROUND/'snapshot_p1_repair_report.json'))
    (OUT/'corrected_provenance.json').write_text(json.dumps(provenance,indent=2))
    manifest_path=OUT/'manifest.json';original=OUT/'manifest_before_snapshot_repair.INVALID.json'
    if not original.exists():original.write_bytes(manifest_path.read_bytes())
    manifest=json.loads(original.read_text())
    manifest['original_training_provenance']=manifest['identities'].copy()
    manifest['identities'][str(new.relative_to(WORKSPACE))]=sha(new)
    manifest['identities'][str((ROUND/'core.py').relative_to(WORKSPACE))]=sha(ROUND/'core.py')
    manifest['snapshot_repair']=provenance
    manifest_path.write_text(json.dumps(manifest,indent=2))
    print(json.dumps(provenance,indent=2))

if __name__=='__main__':main()
