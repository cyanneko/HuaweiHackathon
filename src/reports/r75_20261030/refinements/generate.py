from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
parent=ROOT/'tmp/r74_fast/R74_fast_operator.policy.cpp'
base=parent.read_text(encoding='utf-8')
variants={}
mix='if(R74_MODE>=2)reuse=.75*reuse+.25*64./(64.+prior);'
assert base.count(mix)==1
variants['R75_adaptive_pool']=base.replace(mix,
    'if(R74_MODE>=2) { const double w=.25/(1.+r.events);\n'
    '            reuse=(1.-w)*reuse+w*64./(64.+prior); }')
variants['R75_prior_only']=base.replace(mix,
    '// The operator is already represented by the waiting-time prior above.')
variants['R75_event_rate']=base.replace('double reuse=64./(64.+r.mean(q,prior));',
    'double reuse=64./r.mean(q,prior);').replace(mix,
    'if(R74_MODE>=2)reuse=.75*reuse+.25*64./prior;')
assert variants['R75_event_rate']!=base
variants['R75_penalty32']=base.replace('1.0 / s.write_bandwidth + 1.0 / part.data_size',
    '1.0 / s.write_bandwidth + 31.622776601683793 / part.data_size').replace(
    '// lower bound (1 microsecond) is used in this cost-density heuristic.',
    '// geometric-range prior (31.6228 us), never the hidden real value, is used.')
# The first comment line also needs to stop describing this as a bound.
variants['R75_penalty32']=variants['R75_penalty32'].replace(
    '// The true penalty is absent from SystemState. Only its documented',
    '// The true penalty is absent from SystemState. Its public-range')

cached=base.replace('std::vector<r74::Risk> risk_, operator_risk_;',
    'std::vector<r74::Risk> risk_, operator_risk_;\n    std::vector<double> cached_priors_;')
cached=cached.replace('intents_.clear(); coverage_=0.; coverage_q_=0;',
    'intents_.clear(); coverage_=0.; coverage_q_=0; cached_priors_.assign(s.operators.size(),64.);')
assert cached.count('if(R74_MODE>=2)pool.advance(q);')==1
cached=cached.replace('if(R74_MODE>=2)pool.advance(q);','// Pool was advanced once at the beginning of this release decision.')
cached=cached.replace('const double prior=R74_MODE>=2 ? pool.mean(q) : 64.;',
    'const double prior=R74_MODE>=2 ? cached_priors_[id/p_] : 64.;')
needle='const int64_t now = s.hit_count + s.miss_count + 1;'
assert cached.count(needle)==1
cached=cached.replace(needle,needle+'\n        for(std::size_t o=0;o<operator_risk_.size();++o)\n'
    '            cached_priors_[o]=operator_risk_[o].mean(now-1);')
variants['R75_cached_pool']=cached

manifest=dict(parent=str(parent.relative_to(ROOT)),parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),variants=[])
for name,code in variants.items():
    assert code!=base
    p=HERE/(name+'.policy.cpp');p.write_text(code,encoding='utf-8')
    manifest['variants'].append(dict(name=name,policy=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(HERE/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Generated',len(variants),'isolated variants')
