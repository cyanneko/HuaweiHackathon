"""Freeze two temporal-scale probes and a strictly lazy cache refinement."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
base=(ROOT/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_text(encoding='utf-8')
variants={}
for horizon in [128,2048]:
    code=base.replace('/512.',f'/{horizon}.').replace('*512.',f'*{horizon}.')
    assert code!=base and '/512.' not in code and '*512.' not in code
    variants['R75_memory'+str(horizon)]=code
cached=(HERE/'R75_cached_pool.policy.cpp').read_text(encoding='utf-8')
cached=cached.replace('std::vector<double> cached_priors_;','std::vector<double> cached_priors_;\n    std::vector<unsigned char> cached_valid_;')
cached=cached.replace('cached_priors_.assign(s.operators.size(),64.);','cached_priors_.assign(s.operators.size(),64.); cached_valid_.assign(s.operators.size(),0);')
cached=cached.replace('// Pool was advanced once at the beginning of this release decision.',
    'if(!cached_valid_[id/p_]) { pool.advance(q); cached_priors_[id/p_]=pool.mean(q); cached_valid_[id/p_]=1; }')
needle='for(std::size_t o=0;o<operator_risk_.size();++o)\n            cached_priors_[o]=operator_risk_[o].mean(now-1);'
assert cached.count(needle)==1
cached=cached.replace(needle,'std::fill(cached_valid_.begin(),cached_valid_.end(),0);')
variants['R75_lazy_cache']=cached
manifest=[]
for name,code in variants.items():
    path=HERE/(name+'.policy.cpp');path.write_text(code,encoding='utf-8')
    manifest.append(dict(name=name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(HERE/'followups.json').write_text(json.dumps(manifest,indent=2)+'\n')
