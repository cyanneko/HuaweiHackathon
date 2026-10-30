"""Audit the P1 repair without fitting or changing model weights."""
from core import *
O=Path(__file__).resolve().parent
oldpath=O/'snapshot_p1_invalid_audit/path_demo.INVALID.jsonl'
newpath=O/'pilot_exact_04/path_demo.jsonl'
old=[json.loads(x) for x in oldpath.read_text().splitlines()]
new=[json.loads(x) for x in newpath.read_text().splitlines()]
c=Case.read(O.parents[3]/'tmp/r66_data_handoff_20261030/export/datasets/liunianwww/train/training_pair_fits_0350_613cccc25a2a.txt')
assert len(old)==len(new)==44
comparisons=[]
for before,after in zip(old,new):
    state=State.from_snapshot(c,after['full_state_snapshot'])
    plans=pool(state)
    reconstructed=[{'action_key':action_key(state,a),'x':features(state,a)} for a in plans]
    comparison={'callback_id':after['callback_id'],'x_unchanged':[p['x'] for p in before['plans']]==[p['x'] for p in after['plans']],
        'selected_unchanged':before['selected_action_key']==after['selected_action_key'],
        'candidate_order_unchanged':[p['action_key'] for p in before['plans']]==[p['action_key'] for p in after['plans']],
        'old_full_snapshot_matches_anchor_hash':digest(before['full_state_snapshot'])==before['anchor_snapshot_hash'],
        'new_full_snapshot_matches_anchor_hash':digest(after['full_state_snapshot'])==after['anchor_snapshot_hash'],
        'new_history_matches_hash':digest(after['full_state_snapshot']['history'])==after['history_snapshot_hash'],
        'json_reconstructed_pool_features_match':reconstructed==[{'action_key':p['action_key'],'x':p['x']} for p in after['plans']]}
    assert all(comparison[x] for x in ('x_unchanged','selected_unchanged','candidate_order_unchanged','new_full_snapshot_matches_anchor_hash','new_history_matches_hash','json_reconstructed_pool_features_match'))
    comparisons.append(comparison)
report={'rows':len(new),'old_invalid_file_sha256':hashlib.sha256(oldpath.read_bytes()).hexdigest(),'corrected_labels_sha256':hashlib.sha256(newpath.read_bytes()).hexdigest(),
    'core_sha256':hashlib.sha256((O/'core.py').read_bytes()).hexdigest(),
    'old_snapshot_hash_failures':sum(not x['old_full_snapshot_matches_anchor_hash'] for x in comparisons),
    'all_x_selected_and_order_unchanged':True,'all_json_anchors_reconstruct_exact_pool_and_features':True,
    'model_weight_disposition':'existing weights may be retained because all 44 input matrices and chosen labels are identical; update provenance only; no retraining performed',
    'official_verification':'pilot_exact_04/official_parity.json','per_row':comparisons}
(O/'snapshot_p1_repair_report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='per_row'}))
