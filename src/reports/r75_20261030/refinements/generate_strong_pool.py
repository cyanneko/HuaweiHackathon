from pathlib import Path
import json,hashlib
here=Path(__file__).resolve().parent;root=here.parents[1]
base=(root/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_text(encoding='utf-8')
needle='if(R74_MODE>=2)reuse=.75*reuse+.25*64./(64.+prior);'
assert base.count(needle)==1
variants={
 'R75_pool50':base.replace(needle,'if(R74_MODE>=2)reuse=.50*reuse+.50*64./(64.+prior);'),
 'R75_pool75':base.replace(needle,'if(R74_MODE>=2)reuse=.25*reuse+.75*64./(64.+prior);'),
 'R75_fast_pool75':(here/'R75_operator_fast.policy.cpp').read_text(encoding='utf-8').replace(needle,
    'if(R74_MODE>=2)reuse=.25*reuse+.75*64./(64.+prior);'),
}
guard=base.replace('#define R74_MODE 2','#define R74_MODE 3')
guard=guard.replace('return .15+.70*cov;','return .15+.85*std::min(1.,cov/.75);')
marker='double refaultReuse(int id,int64_t q,double visible,double observed_weight) {'
guard=guard.replace(marker,marker+'\n        if(observed_weight>=1.)return visible;')
variants['R75_dense_guard']=guard
items=[]
for name,code in variants.items():
 p=here/(name+'.policy.cpp');p.write_text(code,encoding='utf-8')
 items.append(dict(name=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(here/'strong_pool_sources.json').write_text(json.dumps(items,indent=2)+'\n')
old=json.loads((root/'tmp/r73_penalty_proxy/cases.json').read_text())['cases']
fresh=json.loads((root/'tmp/r75_fresh_data/cases.json').read_text())['cases']
(here/'cases41.json').write_text(json.dumps(dict(cases=old+fresh),indent=2)+'\n')
oldres=json.loads((root/'tmp/r73_penalty_proxy/results.json').read_text())
freshres=json.loads((root/'tmp/r75_fresh_eval/results.json').read_text())
(here/'baseline_results41.json').write_text(json.dumps(oldres+freshres,indent=2)+'\n')
