"""Create one candidate and test-only harnesses; no compilation or execution."""
from pathlib import Path
import json,hashlib,difflib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PLAN='docs/superpowers/plans/2026-10-30-r87-fixed-share-operator.md'
PLAN_SHA='0e3641da02e86d76ebba01f3c7a0cfaed6ff83a534d8af78f25c0d933eaf8c0d'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2);f.write('\n')
def main():
 assert sha(ROOT/PLAN)==PLAN_SHA
 parent=next(m for m in json.loads((ROOT/'tmp/r85_ablations/producer.json').read_text())['variants'] if m['name']=='R85_fast_prior8')
 assert parent['source_sha256']=='a0ebc08399a8cd8c039dae59a779231df0c35306af3ea3269df3067c321779b5'
 src=ROOT/parent['source_path'];tu=ROOT/parent['translation_unit_path']
 assert sha(src)==parent['source_sha256'] and sha(tu)==parent['translation_unit_sha256']
 raw=src.read_bytes();full=tu.read_bytes();assert full.count(raw)==1;prefix,suffix=full.split(raw)
 # Current test hashes are captured before any candidate source is written.
 save(HERE/'tests_before_source.json',dict(tests={p.name:sha(p) for p in HERE.iterdir() if p.name.startswith('test_') or p.name=='oracle.hpp'},initial_test_manifest_sha256=sha(HERE/'tests_preimplementation.json'),rounding_note='First-label K3 equality uses tolerance for floating division; no tests have yet executed'))
 s=raw.decode()
 def replace(old,new):
  nonlocal s
  assert s.count(old)==1,old[:90];s=s.replace(old,new,1)
 replace('    double fast_probability_total_=0.;','''    double fast_probability_total_=0.;
    // Persistent observed-label totals; probability_* totals remain query caches.
    double operator_fast_total_=0.,operator_slow_total_=0.;
    int64_t operator_total_q_=0;
    double operator_fast_weight_=.5;
    void advanceOperatorTotals(int64_t q) {
        if(q<=operator_total_q_)return;
        operator_fast_total_*=fastDecay(q-operator_total_q_);
        operator_slow_total_*=nextDecay(q-operator_total_q_);
        operator_total_q_=q;
    }
    void updateOperatorWeight(int op) {
        const double k=static_cast<double>(sharing_.size());
        const double pf=(fast_operator_[op].mass+8.009479828345365/k)/(operator_fast_total_+8.009479828345365);
        const double ps=(sharing_[op].mass+64./k)/(operator_slow_total_+64.);
        const double w=std::isfinite(operator_fast_weight_) && operator_fast_weight_>=0. && operator_fast_weight_<=1. ? operator_fast_weight_ : .5;
        const double evidence=w*pf+(1.-w)*ps;
        if(!(pf>0.) || !(ps>0.) || !std::isfinite(pf) || !std::isfinite(ps) || !(evidence>0.) || !std::isfinite(evidence)) {
            operator_fast_weight_=.5;return;
        }
        // Log-loss multiplicative update, then sharing to the OTHER expert.
        const double posterior=w*pf/evidence,alpha=1./256.;
        operator_fast_weight_=std::max(alpha,std::min(1.-alpha,alpha+(1.-2.*alpha)*posterior));
    }''')
 replace('        probability_clock_=std::max(s.hit_count+s.miss_count,next_sample_q_);','''        probability_clock_=std::max(std::max(s.hit_count+s.miss_count,next_sample_q_),operator_total_q_);
        advanceOperatorTotals(probability_clock_);''')
 replace('''        for(int op=0;op<k;++op) {
            const double marginal=(fast_operator_[op].mass+fast_op_prior)/fast_denom;''','''        const double w=std::isfinite(operator_fast_weight_) && operator_fast_weight_>=0. && operator_fast_weight_<=1. ? operator_fast_weight_ : .5;
        for(int op=0;op<k;++op) {
            const double fast_marginal=(fast_operator_[op].mass+fast_op_prior)/fast_denom;
            const double slow_marginal=(sharing_[op].mass+slow_op_prior)/probability_denom_;
            const double marginal=w*fast_marginal+(1.-w)*slow_marginal;''')
 replace('''        refreshSharing(op,ordinal);
        if(ordinal<=next_sample_q_)return;
        advanceFast(op,ordinal);fast_operator_[op].mass+=1.;''','''        if(ordinal<=next_sample_q_)return;
        const int64_t q=std::max(ordinal,operator_total_q_);
        advanceOperatorTotals(q);refreshSharing(op,q);advanceFast(op,q);
        // Score the exposed operator label BEFORE inserting it into either expert.
        updateOperatorWeight(op);
        operator_fast_total_+=1.;operator_slow_total_+=1.;
        fast_operator_[op].mass+=1.;''')
 replace('''        next_sample_q_=ordinal;
        refreshSharing(op,g.last);''','''        next_sample_q_=ordinal;
        probability_cache_valid_=false;
        refreshSharing(op,g.last);''')
 replace('''            fast_operator_.assign(s.operators.size(),FastOperator{});operator_scale_.clear();''','''            fast_operator_.assign(s.operators.size(),FastOperator{});operator_scale_.clear();
            operator_fast_total_=operator_slow_total_=0.;operator_total_q_=0;operator_fast_weight_=.5;
            probability_cache_valid_=false;''')
 name='R87_fixedshare_op';folder=HERE/name;folder.mkdir()
 policy=s.encode();(folder/'MySpillScheduler.cpp').write_bytes(policy);(folder/'main.cpp').write_bytes(prefix+policy+suffix)
 def header(code):return prefix+code.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1)
 (folder/'test_include.hpp').write_bytes(header(policy));(HERE/'parent_test_include.hpp').write_bytes(header(raw))
 (folder/'parent.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),s.splitlines(True),fromfile=parent['name'],tofile=name)),encoding='utf-8')
 # Deliberately wrong, test-only controls demonstrate discriminatory tests.
 uniform=s.replace('alpha+(1.-2.*alpha)*posterior','alpha*.5+(1.-alpha)*posterior',1)
 assert uniform!=s;(HERE/'mutant_uniform_pool.hpp').write_bytes(header(uniform.encode()))
 after=s.replace('        updateOperatorWeight(op);\n','',1)
 anchor='        g.squares+=2.*c.mass+1.; g.mass+=1.; g.weight2+=1.; c.mass+=1.;'
 assert after.count(anchor)==1;after=after.replace(anchor,anchor+'\n        updateOperatorWeight(op);',1)
 (HERE/'mutant_score_after_insert.hpp').write_bytes(header(after.encode()))
 for source,dest in [('tmp/r80_lazy_transfer/R80_next_hier_fast100/test_callbacks.cpp','test_callbacks.cpp'),('tmp/r81_two_timescale/R81_op256_cond2048/test_legality.cpp','test_legality.cpp')]:
  (folder/dest).write_bytes((ROOT/source).read_bytes())
 assert (folder/'main.cpp').read_bytes().replace(policy,b'__SCHEDULER__',1)==full.replace(raw,b'__SCHEDULER__',1)
 normalized=(prefix+policy+suffix).decode().replace('\r\n','\n').replace(s.replace('\r\n','\n'),'<SCHEDULER>')
 fw=hashlib.sha256(normalized.encode()).hexdigest();assert fw=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
 variant=dict(name=name,source_path=(folder/'MySpillScheduler.cpp').relative_to(ROOT).as_posix(),source_sha256=sha(folder/'MySpillScheduler.cpp'),translation_unit_path=(folder/'main.cpp').relative_to(ROOT).as_posix(),translation_unit_sha256=sha(folder/'main.cpp'),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_name=parent['name'],parent_sha256=parent['source_sha256'],parent_translation_unit_sha256=parent['translation_unit_sha256'],parent_binary_sha256=parent['binary_sha256'])
 save(HERE/'prepared.json',dict(status='SOURCE_TESTS_READY_AWAITING_ROOT_WINDOW',plan_path=PLAN,plan_sha256=PLAN_SHA,parent=parent,variant=variant,framework_sha256=fw,framework_unchanged=True,tests_before_source_sha256=sha(HERE/'tests_before_source.json'),no_compilation_or_scheduler_execution=True))
 print(json.dumps(dict(status='READY_REQUEST',source_sha256=variant['source_sha256'],TU_sha256=variant['translation_unit_sha256'],framework_sha256=fw)))
if __name__=='__main__':main()
