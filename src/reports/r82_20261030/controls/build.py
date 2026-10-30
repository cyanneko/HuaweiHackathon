from pathlib import Path
import subprocess,hashlib,json,time,difflib,sys
r=Path(__file__).resolve().parent;root=r.parents[1];parent=root/'tmp/r80_lazy_transfer';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();save=lambda p,x:p.write_text(json.dumps(x,indent=2)+'\n');assert sys.platform.startswith('linux')
start=time.monotonic();records=[];error=None;variants=[];red=json.loads((r/'red_evidence.json').read_text())
def run(cmd,label):
 p=subprocess.run(cmd,cwd=r,capture_output=True,text=True,timeout=85-red['seconds']-(time.monotonic()-start));(r/(label+'.stdout')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr);records.append(dict(name=label,returncode=p.returncode,argv=cmd));assert p.returncode==0,(label,p.stdout,p.stderr)
try:
 old=next(v for v in json.loads((parent/'producer.json').read_text())['variants'] if v['name']=='R80_next_hier_fast100');src=root/old['source_path'];raw=src.read_bytes();assert sha(src)=='0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d';prefix,suffix=(root/old['translation_unit_path']).read_bytes().split(raw)
 for effect,name in [(1,'R82_singlefit025'),(2,'R82_write1')]:
  d=r/name;d.mkdir(exist_ok=True);s=raw.decode()
  ordinary='''        bool ordinary=!scan && !uniform_cycle_;
        for(const auto& state_op:s.operators)if(state_op.phase!=Phase::PROBE)ordinary=false;
'''
  s=s.replace('        const double observed_weight=demandWeight(now-1);',ordinary+'        const double observed_weight=demandWeight(now-1);',1)
  if effect==1:
   s='#define R82_SINGLEFIT 1\n'+s
   s=s.replace('class MySpillScheduler : public SpillScheduler {','''class MySpillScheduler : public SpillScheduler {
    bool single_active_=false;
    int single_id_=-1;
    double single_loss_=0.;
    std::vector<double> candidate_loss_;
    void finishSingle(const SystemState& s,int64_t required,std::vector<Action>& actions) {
        if(!single_active_ || single_id_<0)return;
        pruneSpills(s,required,actions);
        double loss=0.;
        for(const auto& a:actions)loss+=candidate_loss_[a.op_id*p_+a.partition_id];
        if(single_loss_<loss) {
            actions.clear();actions.emplace_back(Action::SPILL,single_id_/p_,single_id_%p_);
        }
    }
''',1)
   s=s.replace('        const int64_t free_bytes = s.memory_limit - s.memory_used;','        single_active_=false;single_id_=-1;\n        const int64_t free_bytes = s.memory_limit - s.memory_used;',1)
   s=s.replace('        victims_.clear();','        if(ordinary) {single_active_=true;candidate_loss_.resize(history_.size());}\n        victims_.clear();',1)
   s=s.replace('            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});','''            if(single_active_) {
                const int id=o.op_id*p_+part.partition_id;
                const double loss=priority*part.data_size+0.25*static_cast<double>(part.data_size)/s.write_bandwidth;
                candidate_loss_[id]=loss;
                if(part.data_size>=need && !(o.op_id==next_op && part.partition_id==next_pid) &&
                   (single_id_<0 || loss<single_loss_ || (loss==single_loss_ && id<single_id_))) {
                    single_id_=id;single_loss_=loss;
                }
            }
            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});''',1)
   needle='        propose(s,op,pid,required,actions,R80_MODE==1?1:(R80_MODE==2?2:0));';s=s.replace(needle,needle+'\n        finishSingle(s,required,actions);',1)
  else:
   s=s.replace('loss+=v.priority*v.bytes+0.25*static_cast<double>(v.bytes)/s.write_bandwidth;','loss+=v.priority*v.bytes+(ordinary?1.:0.25)*static_cast<double>(v.bytes)/s.write_bandwidth;',1)
  policy=s.encode();(d/'MySpillScheduler.cpp').write_bytes(policy);(d/'main.cpp').write_bytes(prefix+policy+suffix);public=policy.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1);(d/'test_include.hpp').write_bytes(prefix+public)
  ref=raw.replace(b'MySpillScheduler',b'FrozenScheduler').replace(b'r74',b'oldr74').replace(b'r75op',b'oldr75op').replace(b'class FrozenScheduler : public SpillScheduler {',b'class FrozenScheduler : public SpillScheduler {\npublic:',1);(d/'equiv_include.hpp').write_bytes(prefix+ref+public)
  (d/'parent.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),s.splitlines(True),fromfile='R80_next_hier_fast100',tofile=name)))
  for test in ['test_transfer','test_callbacks']:(d/(test+'.cpp')).write_bytes((parent/'R80_next_hier_fast100'/(test+'.cpp')).read_bytes())
  (d/'test_legality.cpp').write_bytes((root/'tmp/r81_two_timescale/R81_op256_cond2048/test_legality.cpp').read_bytes())
  run(['g++','-std=c++14','-O2',str(d/'main.cpp'),'-o',str(d/'scheduler')],name+'_TU')
  for test in ['test_effect','test_search','test_transfer','test_callbacks','test_legality']:
   source=r/(test+'.cpp') if test in ('test_effect','test_search') else d/(test+'.cpp');macro='EQUIV_INCLUDE' if test=='test_search' else 'TEST_INCLUDE';header='equiv_include.hpp' if test=='test_search' else 'test_include.hpp';cmd=['g++','-std=c++14','-O2','-DEFFECT='+str(effect),'-D'+macro+'="'+str(d/header)+'"',str(source),'-o',str(d/test)];run(cmd,name+'_'+test+'_compile');run([str(d/test)],name+'_'+test)
  variants.append(dict(name=name,source_path=(d/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(d/'MySpillScheduler.cpp'),translation_unit_path=(d/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(d/'main.cpp'),binary=str(d/'scheduler'),binary_sha256=sha(d/'scheduler'),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_name=old['name'],parent_sha256=old['source_sha256']))
 assert sha(src)==old['source_sha256'] and sha(root/old['translation_unit_path'])==old['translation_unit_sha256'] and sha(Path(old['binary']))==old['binary_sha256']
 manifest=dict(parent=old,parent_producer_sha256=sha(parent/'producer.json'),plan_sha256=sha(root/'docs/superpowers/plans/2026-10-30-r82-victim-search-ablation.md'),framework_unchanged=True,files={p.name:sha(p) for p in [Path(__file__),r/'test_effect.cpp',r/'test_search.cpp',r/'red_evidence.json']});save(r/'source_manifest.json',manifest);save(r/'producer.json',dict(status='READY',parent_sha256=old['source_sha256'],variants=variants,source_manifest_path='tmp/r82_victim_search/source_manifest.json',source_manifest_sha256=sha(r/'source_manifest.json'),framework_unchanged=True))
except BaseException as e:error=repr(e);raise
finally:
 elapsed=time.monotonic()-start;save(r/'test_summary.json',dict(status='PASS' if error is None else 'FAIL',error=error,seconds=elapsed,total_compile_test_seconds=elapsed+red['seconds'],budget_seconds=90,expected_parent_red=red,records=records,performance_runs=0));release=dict(status='RELEASED',ready=error is None,final=error is None,active_child_processes=0,total_compile_test_seconds=elapsed+red['seconds'],test_summary_sha256=sha(r/'test_summary.json'))
 if error is None:release['producer_sha256']=sha(r/'producer.json')
 save(r/'release.json',release);print(json.dumps(release))
