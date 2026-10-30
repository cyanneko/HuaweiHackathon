from pathlib import Path
import subprocess,hashlib,json,time,difflib,sys
r=Path(__file__).resolve().parent;root=r.parents[1];parent=root/'tmp/r80_lazy_transfer';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();save=lambda p,x:p.write_text(json.dumps(x,indent=2)+'\n');assert sys.platform.startswith('linux')
start=time.monotonic();records=[];error=None;variants=[]
def run(cmd,label):
 p=subprocess.run(cmd,cwd=r,capture_output=True,text=True,timeout=80-(time.monotonic()-start));(r/(label+'.stdout')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr);records.append(dict(name=label,returncode=p.returncode,argv=cmd));assert p.returncode==0,(label,p.stdout,p.stderr)
try:
 old=next(v for v in json.loads((parent/'producer.json').read_text())['variants'] if v['name']=='R80_next_hier_fast100');src=root/old['source_path'];raw=src.read_bytes();assert sha(src)=='0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d';full=(root/old['translation_unit_path']).read_bytes();prefix,suffix=full.split(raw)
 for half in (256,512):
  name='R81_op'+str(half)+'_cond2048';d=r/name;d.mkdir(exist_ok=True);s='#define R81_FAST_HALF '+str(half)+'\n'+raw.decode()
  s=s.replace('    bool probability_cache_valid_=false;','''    struct FastOperator {double mass=0.; int64_t last=0;};
    std::vector<FastOperator> fast_operator_;
    std::vector<double> operator_scale_;
    double fast_probability_total_=0.;
    static double fastDecay(int64_t delta) {
        static const std::array<double,8193> table=[]() {
            std::array<double,8193> a{};
            for(int i=0;i<=8192;++i)a[i]=std::exp(-0.693147180559945309417232121458176568*static_cast<double>(i)/R81_FAST_HALF);
            return a;
        }();
        return delta>=0 && delta<=8192 ? table[static_cast<std::size_t>(delta)] : std::exp(-0.693147180559945309417232121458176568*static_cast<double>(delta)/R81_FAST_HALF);
    }
    void advanceFast(int op,int64_t q) {
        auto& f=fast_operator_[op];
        if(q>f.last) {if(f.mass!=0.)f.mass*=fastDecay(q-f.last);f.last=q;}
    }
    bool probability_cache_valid_=false;''',1)
  s=s.replace('probability_total_=probability_weight2_=0.;','probability_total_=probability_weight2_=0.;fast_probability_total_=0.;',1)
  s=s.replace('            refreshSharing(op,probability_clock_);','            refreshSharing(op,probability_clock_);advanceFast(op,probability_clock_);\n            fast_probability_total_+=fast_operator_[op].mass;',1)
  s=s.replace('        probability_cache_valid_=true;','''        const int k=static_cast<int>(sharing_.size());
        operator_scale_.resize(k);
        const double op_prior=64./k,fast_denom=fast_probability_total_+64.;
        for(int op=0;op<k;++op) {
            const double marginal=(fast_operator_[op].mass+op_prior)/fast_denom;
            operator_scale_[op]=std::isfinite(marginal) && marginal>=0. ? marginal/(sharing_[op].mass+op_prior) : 1./probability_denom_;
        }
        probability_cache_valid_=true;''',1)
  needle='hier_probability_[id]=((1.-g.share)*mass+g.share*g.mass/p_+probability_prior_)/probability_denom_;';assert s.count(needle)==1;s=s.replace(needle,'hier_probability_[id]=((1.-g.share)*mass+g.share*g.mass/p_+probability_prior_)*operator_scale_[id/p_];')
  s=s.replace('        if(ordinal<=next_sample_q_)return;','        if(ordinal<=next_sample_q_)return;\n        advanceFast(op,ordinal);fast_operator_[op].mass+=1.;',1)
  s=s.replace('sharing_.assign(s.operators.size(),ShareGroup{});','fast_operator_.assign(s.operators.size(),FastOperator{});operator_scale_.clear();\n            sharing_.assign(s.operators.size(),ShareGroup{});',1)
  policy=s.encode();(d/'MySpillScheduler.cpp').write_bytes(policy);(d/'main.cpp').write_bytes(prefix+policy+suffix);public=policy.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1);(d/'test_include.hpp').write_bytes(prefix+public)
  (d/'parent.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),s.splitlines(True),fromfile='R80_next_hier_fast100',tofile=name)))
  (d/'test_callbacks.cpp').write_bytes((parent/'R80_next_hier_fast100/test_callbacks.cpp').read_bytes())
  t=(parent/'R80_next_hier_fast100/test_transfer.cpp').read_text()
  t=t.replace('assert(close(m.hier_probability_[0],(.25*c0+.75*(c0+c1)/2+16)/(S+64)));','assert(close(m.hier_probability_[0],(.25*c0+.75*(c0+c1)/2+16)*m.operator_scale_[0]));')
  t=t.replace('for(int i=0;i<4;++i)assert(close(x.flat_probability_[i],x.hier_probability_[i]));','assert(close(x.hier_probability_[0],x.hier_probability_[1])&&close(x.hier_probability_[2],x.hier_probability_[3]));')
  (d/'test_transfer.cpp').write_text(t)
  # Reuse legal-action simulation helpers, without demanding equality of this new policy to its parent.
  legal=(parent/'test_equivalence.cpp').read_text();head=legal[:legal.index('int main(){')].replace('#include EQUIV_INCLUDE','#include TEST_INCLUDE');body=legal[legal.index(' {auto s=fixture();FrozenScheduler a;MySpillScheduler b;for(int j=0;'):legal.index(' std::cout<<')]
  body=body.replace('FrozenScheduler a;MySpillScheduler b;','MySpillScheduler b;').replace('auto x=a.onMemoryOverflow(s,o,p,30),y=b.onMemoryOverflow(s,o,p,30);same(x,y);apply(s,x);','auto y=b.onMemoryOverflow(s,o,p,30);apply(s,y);').replace('auto x=a.onPartitionMiss(s,o,p),y=b.onPartitionMiss(s,o,p);same(x,y);apply(s,x);','auto y=b.onPartitionMiss(s,o,p);apply(s,y);').replace('auto x=a.onPeriodicAdjust(s),y=b.onPeriodicAdjust(s);same(x,y);apply(s,x);','auto y=b.onPeriodicAdjust(s);apply(s,y);')
  body=body[:body.index('assert(a.intents_.size()')]+ '}}\n'
  (d/'test_legality.cpp').write_text(head+'int main(){\n'+body+'std::cout<<"400 callback sequence legal PASS\\n";}\n')
  run(['g++','-std=c++14','-O2',str(d/'main.cpp'),'-o',str(d/'scheduler')],name+'_TU')
  for test in ['test_switch','test_oracle','test_transfer','test_callbacks','test_legality']:
   source=r/(test+'.cpp') if test in ('test_switch','test_oracle') else d/(test+'.cpp');cmd=['g++','-std=c++14','-O2','-DTEST_INCLUDE="'+str(d/'test_include.hpp')+'"',str(source),'-o',str(d/test)];run(cmd,name+'_'+test+'_compile');run([str(d/test)],name+'_'+test)
  if half==256:
   ref=raw.replace(b'MySpillScheduler',b'FrozenScheduler').replace(b'r74',b'oldr74').replace(b'r75op',b'oldr75op').replace(b'class FrozenScheduler : public SpillScheduler {',b'class FrozenScheduler : public SpillScheduler {\npublic:',1)
   (r/'identity_include.hpp').write_bytes(prefix+ref+public.replace(b'#define R81_FAST_HALF 256',b'#define R81_FAST_HALF 2048',1));run(['g++','-std=c++14','-O2','-DIDENTITY_INCLUDE="'+str(r/'identity_include.hpp')+'"',str(r/'test_identity.cpp'),'-o',str(r/'test_identity')],'identity_compile');run([str(r/'test_identity')],'identity')
  variants.append(dict(name=name,source_path=(d/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(d/'MySpillScheduler.cpp'),translation_unit_path=(d/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(d/'main.cpp'),binary=str(d/'scheduler'),binary_sha256=sha(d/'scheduler'),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_name=old['name'],parent_sha256=old['source_sha256']))
 assert sha(src)==old['source_sha256'] and sha(root/old['translation_unit_path'])==old['translation_unit_sha256'] and sha(Path(old['binary']))==old['binary_sha256']
 manifest=dict(parent=old,parent_producer_sha256=sha(parent/'producer.json'),plan_sha256=sha(root/'docs/superpowers/plans/2026-10-30-r81-two-timescale-heat.md'),framework_unchanged=True,files={p.name:sha(p) for p in [Path(__file__),r/'test_switch.cpp',r/'test_oracle.cpp',r/'test_identity.cpp']})
 save(r/'source_manifest.json',manifest);save(r/'producer.json',dict(status='READY',parent_sha256=old['source_sha256'],variants=variants,source_manifest_path='tmp/r81_two_timescale/source_manifest.json',source_manifest_sha256=sha(r/'source_manifest.json'),framework_unchanged=True))
except BaseException as e:error=repr(e);raise
finally:
 elapsed=time.monotonic()-start;save(r/'test_summary.json',dict(status='PASS' if error is None else 'FAIL',error=error,seconds=elapsed,total_compile_test_seconds=elapsed+5.5850925,budget_seconds=90,expected_parent_red=dict(stdout_sha256=sha(r/'parent_red.stdout'),stderr_sha256=sha(r/'parent_red.stderr'),behavior='slow parent op marginal remains below .5 after1024 next samples from new op'),records=records,performance_runs=0));release=dict(status='RELEASED',ready=error is None,final=error is None,active_child_processes=0,total_compile_test_seconds=elapsed+5.5850925,test_summary_sha256=sha(r/'test_summary.json'))
 if error is None:release['producer_sha256']=sha(r/'producer.json')
 save(r/'release.json',release);print(json.dumps(release))
