"""Verify the packaged model, split and recorded SDK scores without a compiler."""
from pathlib import Path
import collections, hashlib, json, math, statistics
import numpy as np
import deploy, train
ROOT=Path(__file__).resolve().parent
def read(n):return json.loads((ROOT/n).read_text('utf8'))
result=read('results.json')
source=ROOT.parent/'MySpillScheduler_neural.cpp'
assert hashlib.sha256(source.read_bytes()).hexdigest()==result['source_sha256']
deploy.export('model_16.json',.5)
assert (ROOT/'generated.cpp').read_bytes()==source.read_bytes(), 'Export differs from benchmarked source'
data=read('data_manifest.json');byhash={r['sha256']:r for r in data}
groups={s:{r['group_sha256'] for r in data if r['split']==s} for s in ['train','valid','github_eval']}
assert not groups['train']&(groups['valid']|groups['github_eval'])
assert not groups['valid']&groups['github_eval']
counts={}
for stem in ['train','valid','dagger']:
    p=ROOT/(stem+'_labels.npz')
    assert hashlib.sha256(p.read_bytes()).hexdigest()==result['training'][stem]['sha256']
    d=train.load([stem+'_labels.jsonl']);_,x,c,soft,regret,w=d
    assert x.shape[1]==32 and c.shape[1]==8 and np.isfinite(x).all() and np.isfinite(c).all()
    assert np.allclose(soft.sum(1),1) and np.all(c>=0)
    with np.load(p,allow_pickle=False) as a:
        assert all(byhash[str(g)]['split']==('valid' if stem=='valid' else 'train') for g in a['groups'])
        assert np.allclose(c-(a['decision_us']+a['misses']*np.array([byhash[str(g)]['penalty'] for g in a['groups']])[:,None]),np.maximum(0,c-(a['decision_us']+a['misses']*np.array([byhash[str(g)]['penalty'] for g in a['groups']])[:,None])),atol=.01)
    counts[stem]=len(x)
rows=[json.loads(s) for s in (ROOT/'optimized_valid_runs.jsonl').read_text().splitlines()]
g=collections.defaultdict(list)
for r in rows:
    assert abs(r['Total_Score']-r['Total_IO_Time']-r['Total_Decision_Time']-byhash[r['case']]['penalty']*r['Miss_Count'])<.05
    g[r['case'],r['mode']].append(r)
assert len(g)==150*3 and all(len(v)==3 for v in g.values())
med={k:statistics.median(r['Total_Score'] for r in v) for k,v in g.items()}
ratios=[med[c,-1]/med[c,8] for c,m in med if m==-1]
geo=math.exp(statistics.mean(map(math.log,ratios)))
assert abs(geo-result['validation']['summary']['-1']['geometric_vs_previous'])<1e-12
total=len(rows)
fresh=json.loads((ROOT/'fresh_manifest.json').read_text('utf8'))
assert len(fresh)==378
assert not {r['group_sha256'] for r in fresh}&set.union(*groups.values())
assert read('fresh_entropy.json')['source_sha256']==result['source_sha256']
for label,meta in [('fresh_final',fresh),('github_final',[r for r in data if r['split']=='github_eval']),('scale_final',read('scale_manifest.json'))]:
    by={r['sha256']:r for r in meta};runs=[json.loads(s) for s in (ROOT/(label+'_runs.jsonl')).read_text().splitlines()];total+=len(runs)
    assert len(runs)==len(meta)*4*3
    assert all(abs(r['Total_Score']-r['Total_IO_Time']-r['Total_Decision_Time']-by[r['case']]['penalty']*r['Miss_Count'])<.05 for r in runs)
for n,digest in result['artifacts'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==digest
audit=read('action_audit.json');assert audit['source_sha256']==result['source_sha256'] and audit['neural_cases_including_scale']==1150 and audit['sdk_io_hit_miss_matches_including_scale']==542
out=dict(exact_model_export=True,split_overlap=0,label_counts=counts,recorded_sdk_runs=total,score_arithmetic_valid=True,geometric_ratio=geo,fresh_cases=len(fresh),independent_audit_cases=1150,
    note='Consistency checks of recorded SDK runs and independent action-audit results.')
(ROOT/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(out))
