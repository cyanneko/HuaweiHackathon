from pathlib import Path
import json,hashlib,subprocess,time,difflib,sys
r=Path(__file__).resolve().parent;root=r.parents[1];parent=root/'tmp/r80_van_transfer';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();save=lambda p,x:p.write_text(json.dumps(x,indent=2)+'\n')
assert sys.platform.startswith('linux')
start=time.monotonic();records=[];variants=[];error=None
def run(cmd,label):
 p=subprocess.run(cmd,cwd=r,capture_output=True,text=True,timeout=54-(time.monotonic()-start));(r/(label+'.stdout')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr);records.append(dict(name=label,argv=cmd,returncode=p.returncode));assert p.returncode==0,(label,p.stdout,p.stderr)
try:
 pm=json.loads((parent/'producer.json').read_text());parents=[]
 for oldname,name in [('R80_next_hier100','R80_next_hier_fast100'),('R80_paired_hier100','R80_paired_hier_fast100')]:
  old=next(v for v in pm['variants'] if v['name']==oldname);src=root/old['source_path'];tu=root/old['translation_unit_path'];assert sha(src)==old['source_sha256'] and sha(tu)==old['translation_unit_sha256'];parents.append(dict(name=oldname,source_sha256=sha(src),translation_unit_sha256=sha(tu),binary_sha256=sha(parent/oldname/'scheduler')))
  raw=src.read_bytes();data=tu.read_bytes();assert data.count(raw)==1;prefix,suffix=data.split(raw);s=raw.decode();s=s.replace('    std::vector<double> flat_probability_,hier_probability_;','    std::vector<double> flat_probability_,hier_probability_;\n    std::vector<uint64_t> probability_tags_;\n    uint64_t probability_epoch_=0;\n    double probability_prior_=0.,probability_denom_=1.;')
  begin=s.index('        const double prior=64./n,denom=probability_total_+64.;');end=s.index('    struct PairDelta',begin)
  s=s[:begin]+'''        if(static_cast<int>(probability_tags_.size())!=n)probability_tags_.assign(n,0);
        if(++probability_epoch_==0) {
            std::fill(probability_tags_.begin(),probability_tags_.end(),0);
            probability_epoch_=1;
        }
        probability_prior_=64./n;probability_denom_=probability_total_+64.;
        probability_cache_valid_=true;
    }
    void ensureProbability(int id) {
        if(probability_tags_[id]==probability_epoch_)return;
        const auto& c=next_mass_[id];const auto& g=sharing_[id/p_];
        const double mass=c.mass==0. ? 0. : c.mass*probabilityDecay(std::max<int64_t>(0,probability_clock_-c.last));
        flat_probability_[id]=(mass+probability_prior_)/probability_denom_;
        hier_probability_[id]=((1.-g.share)*mass+g.share*g.mass/p_+probability_prior_)/probability_denom_;
        probability_tags_[id]=probability_epoch_;
    }
'''+s[end:]
  s=s.replace('            d.mean+=flat_probability_[id]*coefficient;','            ensureProbability(id);\n            d.mean+=flat_probability_[id]*coefficient;')
  s=s.replace('ensureProbabilities(s);const int id=o.op_id*p_+part.partition_id;','ensureProbabilities(s);const int id=o.op_id*p_+part.partition_id;ensureProbability(id);')
  d=r/name;d.mkdir(exist_ok=True);policy=s.encode();(d/'MySpillScheduler.cpp').write_bytes(policy);(d/'main.cpp').write_bytes(prefix+policy+suffix)
  public=policy.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1);(d/'test_include.hpp').write_bytes(prefix+public)
  ref=raw.replace(b'MySpillScheduler',b'FrozenScheduler').replace(b'r74',b'oldr74').replace(b'r75op',b'oldr75op').replace(b'class FrozenScheduler : public SpillScheduler {',b'class FrozenScheduler : public SpillScheduler {\npublic:',1)
  (d/'equiv_include.hpp').write_bytes(prefix+ref+public)
  (d/'parent.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),s.splitlines(True),fromfile=oldname,tofile=name)))
  t=(parent/'test_transfer.cpp').read_text()
  for obj,st in [('m','s'),('x','u')]:
   expr=obj+'.ensureProbabilities('+st+');';t=t.replace(expr,expr+'for(int lazy_id=0;lazy_id<(int)'+obj+'.next_mass_.size();++lazy_id)'+obj+'.ensureProbability(lazy_id);')
  (d/'test_transfer.cpp').write_text(t);(d/'test_callbacks.cpp').write_bytes((parent/oldname/'test_callbacks.cpp').read_bytes())
  run(['g++','-std=c++14','-O2',str(d/'main.cpp'),'-o',str(d/'scheduler')],name+'_TU')
  for test,macro,header in [('test_transfer','TEST_INCLUDE','test_include.hpp'),('test_callbacks',None,None),('test_equivalence','EQUIV_INCLUDE','equiv_include.hpp'),('test_lazy_red','TEST_INCLUDE','test_include.hpp')]:
   source=d/(test+'.cpp') if test in ['test_transfer','test_callbacks'] else r/(test+'.cpp');cmd=['g++','-std=c++14','-O2'];
   if macro:cmd+=['-D'+macro+'="'+str(d/header)+'"']
   run(cmd+[str(source),'-o',str(d/test)],name+'_'+test+'_compile');run([str(d/test)],name+'_'+test)
  variants.append(dict(name=name,source_path=(d/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(d/'MySpillScheduler.cpp'),translation_unit_path=(d/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(d/'main.cpp'),binary=str(d/'scheduler'),binary_sha256=sha(d/'scheduler'),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_name=oldname,parent_sha256=old['source_sha256']))
 for v in pm['variants']:
  assert sha(root/v['source_path'])==v['source_sha256'] and sha(root/v['translation_unit_path'])==v['translation_unit_sha256'] and sha(Path(v['binary']))==v['binary_sha256']
 manifest=dict(parent_producer_sha256=sha(parent/'producer.json'),parents=parents,files={p.name:sha(p) for p in [Path(__file__),r/'test_lazy_red.cpp',r/'test_equivalence.cpp']},frozen_r80_unchanged=True)
 save(r/'source_manifest.json',manifest);save(r/'producer.json',dict(status='READY',variants=variants,source_manifest_path='tmp/r80_lazy_transfer/source_manifest.json',source_manifest_sha256=sha(r/'source_manifest.json'),framework_unchanged=True,performance_runs=0))
except BaseException as e:error=repr(e);raise
finally:
 elapsed=time.monotonic()-start;save(r/'test_summary.json',dict(status='PASS' if error is None else 'FAIL',error=error,seconds=elapsed,red_compile_and_test_seconds=5.3946328,total_compile_test_seconds=elapsed+5.3946328,budget_seconds=60,records=records,performance_runs=0));release=dict(status='RELEASED',final=error is None,ready=error is None,active_child_processes=0,total_compile_test_seconds=elapsed+5.3946328,test_summary_sha256=sha(r/'test_summary.json'))
 if error is None:release['producer_sha256']=sha(r/'producer.json')
 save(r/'release.json',release);print(json.dumps(release))
