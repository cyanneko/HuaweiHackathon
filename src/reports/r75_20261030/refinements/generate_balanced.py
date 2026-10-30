from pathlib import Path
import hashlib,json
here=Path(__file__).resolve().parent
code=(here/'R75_fast_pool75.policy.cpp').read_text(encoding='utf-8')
code=code.replace('#define R74_MODE 2','#define R74_MODE 3')
assert code.count('return .15+.70*cov;')==1
code=code.replace('return .15+.70*cov;','return .25+.75*std::min(1.,cov/.75);')
marker='double refaultReuse(int id,int64_t q,double visible,double observed_weight) {'
code=code.replace(marker,marker+'\n        if(observed_weight>=1.)return visible;')
code=code.replace('std::vector<r74::Risk> risk_; std::vector<r75op::Risk> operator_risk_;',
    'std::vector<r74::Risk> risk_; std::vector<r75op::Risk> operator_risk_;\n'
    '    std::vector<double> cached_priors_; std::vector<unsigned char> cached_valid_;')
code=code.replace('intents_.clear(); coverage_=0.; coverage_q_=0;',
    'intents_.clear(); coverage_=0.; coverage_q_=0; cached_priors_.assign(s.operators.size(),64.); cached_valid_.assign(s.operators.size(),0);')
code=code.replace('if(R74_MODE>=2)pool.advance(q);',
    'if(!cached_valid_[id/p_]) { pool.advance(q); cached_priors_[id/p_]=pool.mean(q); cached_valid_[id/p_]=1; }')
code=code.replace('const double prior=R74_MODE>=2 ? pool.mean(q) : 64.;',
    'const double prior=R74_MODE>=2 ? cached_priors_[id/p_] : 64.;')
needle='const int64_t now = s.hit_count + s.miss_count + 1;'
code=code.replace(needle,needle+'\n        std::fill(cached_valid_.begin(),cached_valid_.end(),0);')
path=here/'R75_balanced.policy.cpp';path.write_text(code,encoding='utf-8')
(here/'balanced_source.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    components=['operator128/partition512','75 percent explicit operator blend','dense periodic demand guard','lazy per-decision pool cache'],
    visible_weight='.25+.75*min(1,periodic_peek_coverage/.75)',hidden_penalty_proxy=1),indent=2)+'\n')
