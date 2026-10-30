"""At most24 new observer runs; reuse completed root100 references, no teachers/EM."""
import os,sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,re,subprocess,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from build import FROZEN,FROZEN_SHA,AUDIT,REPO
from round9.cost_replay_precise import replay,parse_output
from audit_phase_a import audit,trace_digest
SOURCE=ROOT/'round9/candidates/paired_penalty100.cpp'
SOURCE_SHA='3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15'
OUT=HERE/'build/phase_a_v1';REF=ROOT/'build/round9/proxy100_baseline_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,s):
    if p.exists():assert p.read_text()==s,p
    else:p.write_text(s)
def save(p,x):put(p,json.dumps(x,indent=2)+'\n')
def build_source():
    assert sha(SOURCE)==SOURCE_SHA;policy=SOURCE.read_text().replace('MySpillScheduler','Paired100Observed')
    edits=[
      ('class Paired100Observed : public SpillScheduler {','class Paired100Observed : public SpillScheduler {\n    PhaseAPair phase_a_;'),
      ('        if(scan || uniform_cycle_)return;','        if(scan || uniform_cycle_){phase_a_.reason=2;return;}'),
      ('        ++paired_checks_;','        phase_a_.eligible=1;phase_a_.history=actions;phase_a_.dynamic=alternative;\n        ++paired_checks_;'),
      ('        if(!different)return;','        phase_a_.different=different;phase_a_.immediate=immediate;phase_a_.mean=mean;\n        if(!different)return;'),
      ('        if(immediate+64.0*mean+2.0*sd>=0)return;','        phase_a_.sd=sd;phase_a_.effective=effective;phase_a_.margin=immediate+64.0*mean+2.0*sd;\n        if(immediate+64.0*mean+2.0*sd>=0)return;'),
      ('        actions.swap(alternative);++paired_chosen_;','        phase_a_.chosen=true;\n        actions.swap(alternative);++paired_chosen_;'),
      ('public:\n    std::vector<Action> onMemoryOverflow','public:\n    void resetPhaseA(){phase_a_=PhaseAPair{};}\n    const PhaseAPair& phaseAInfo()const{return phase_a_;}\n    double phaseAProbability(int id)const{return probability(id);}\n    std::vector<Action> onMemoryOverflow')]
    for old,new in edits:assert policy.count(old)==1,old;policy=policy.replace(old,new)
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    engine=ref.split('class HashJoinEngine',1)[1].split('/* ===== 主函数',1)[0]
    insert=(HERE/'phase_a_observer.hpp').read_text()+'\n'+policy+'\nclass MySpillScheduler: public PhaseAWrapper<Paired100Observed> {};\n'+AUDIT
    ref=ref.replace('class HashJoinEngine',insert+'\nclass HashJoinEngine',1)
    assert ref.split('class HashJoinEngine',1)[1].split('/* ===== 主函数',1)[0]==engine
    ref=ref.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<AuditScheduler>()')
    return ref,edits
def reference(case):
    canonical=REF/(Path(case['path']).stem+'.json');record=json.loads(canonical.read_text())
    assert record['input_sha256']==case['sha256'] and record['source_sha256']['paired100']==SOURCE_SHA
    assert record['case']==case['path'] and record['seed']==case['seed'];runs=record['runs']['paired100'];assert len(runs)==3
    good=[]
    for folder in sorted(REF.glob(Path(case['path']).stem+'_attempt*')):
        stdout=folder/'paired100_audit.stdout';stderr=folder/'paired100_audit.stderr'
        if not(stdout.exists() and stderr.exists()):continue
        valid=True
        for j,expected in enumerate(runs):
            path=folder/('paired100_repeat'+str(j)+'.stdout')
            if not path.exists():valid=False;break
            got=parse_output(path.read_text())
            if got!={k:v for k,v in expected.items() if k!='wall_seconds'}:valid=False;break
        if valid:
            got=parse_output(stdout.read_text());a=record['audit']['paired100']
            assert got['Hit_Count']==a['hits'] and got['Miss_Count']==a['misses'] and abs(got['Total_IO_Time']-a['io'])<.011
            good.append((folder,stdout,stderr))
    assert len(good)==1,(canonical,good)
    return record,canonical,good[0]
def assert_old_freezes():
    for root,name in [(HERE,'FINITE_STAGE_FREEZE.json'),(HERE,'CALIBRATION_STAGE_FREEZE.json'),(ROOT/'round8/ai','FREEZE_MANIFEST.json')]:
        for r in json.loads((root/name).read_text())['artifacts']:assert sha(root/r['path'])==r['sha256']
def main():
    proposal_path=HERE/'PRESSURE_PILOT_PROPOSAL_V1.json';proposal=json.loads(proposal_path.read_text());cases=proposal['cases'];assert len(cases)==24
    lock_path=ROOT/'round9/V21_DATASET_LOCK.json';assert sha(lock_path)==proposal['dataset_lock_sha256'];lock=json.loads(lock_path.read_text())
    assert set(c['path'] for c in cases)<=set(lock['pilot_train'])
    complete=ROOT/'round9/PROXY100_BASELINE_RESULTS_V3.json';root_result=json.loads(complete.read_text());assert root_result['complete'] and len(root_result['cases'])==60
    assert_old_freezes();OUT.mkdir(exist_ok=True)
    with experiment_lock():
        source,edits=build_source();cpp=OUT/'observer.cpp';put(cpp,source);exe=OUT/'observer'
        if not exe.exists():
            p=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic',str(cpp),'-o',str(exe)],capture_output=True,text=True)
            put(OUT/'compile.log',p.stderr);p.check_returncode()
        freeze={'scope':'PhaseA observations only; no EM/teacher/model/newreference/old1/dev/eval',
            'files':{f:sha(HERE/f) for f in ['PHASE_A_CONTRACT_V1.md','phase_a_observer.hpp','audit_phase_a.py','run_phase_a.py','PRESSURE_PILOT_PROPOSAL_V1.json']},
            'paired100_sha256':SOURCE_SHA,'official_reference_sha256':FROZEN_SHA,'engine_unchanged':True,
            'generated_source_sha256':sha(cpp),'byte_replay_sha256':sha(ROOT/'round9/cost_replay_precise.py'),
            'root_completed_baseline_sha256':sha(complete),'baseline_execution_freeze_sha256':root_result['execution_freeze_sha256'],
            'diagnostic_source_insertions':edits,'cases':cases,'maximum_new_observer_runs':24}
        save(HERE/'PHASE_A_BUILD_FREEZE_V1.json',freeze)
    if '--prepare-only' in sys.argv:print('PhaseA prepared, no observer run',flush=True);return
    data=ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset';records=[]
    for case in cases:
        identifier=Path(case['path']).stem;result_path=OUT/(identifier+'.json')
        (OUT/'status.json').write_text(json.dumps({'state':'waiting_lock','complete':len(records),'case':case['path']})+'\n')
        with experiment_lock():
            assert sha(SOURCE)==SOURCE_SHA and sha(ROOT/'round9/cost_replay_precise.py')==freeze['byte_replay_sha256']
            path=data/case['path'];assert sha(path)==case['sha256']
            base,canonical,(work,base_stdout,base_stderr)=reference(case)
            if result_path.exists():
                rec=json.loads(result_path.read_text());assert rec['build_freeze_sha256']==sha(HERE/'PHASE_A_BUILD_FREEZE_V1.json');records.append(rec);continue
            # Completed references are re-audited, never rerun.
            base_audit=replay(path,base_stderr.read_text(),base_stdout.read_text())
            assert base_audit['costs']==base['audit']['paired100']['costs']
            started=OUT/(identifier+'.started.json');stdout=OUT/(identifier+'.stdout');stderr=OUT/(identifier+'.stderr')
            if started.exists():raise RuntimeError('An unfinished observer attempt is preserved; do not rerun automatically: '+identifier)
            save(started,{'input_sha256':case['sha256'],'build_freeze_sha256':sha(HERE/'PHASE_A_BUILD_FREEZE_V1.json'),'reference_attempt':work.name})
            env=os.environ.copy();env['PHASE_A_SAMPLE_SEED']=str(case['seed']);begin=time.monotonic()
            with stdout.open('x') as out,stderr.open('x') as err:
                proc=subprocess.run([str(exe),str(path)],env=env,stdout=out,stderr=err,timeout=240)
            assert proc.returncode==0,(identifier,proc.returncode)
            observer_wall=time.monotonic()-begin
            expected_trace=trace_digest(base_stderr);actual_trace=trace_digest(stderr);assert expected_trace==actual_trace
            checked=replay(path,stderr.read_text(),stdout.read_text());assert checked['costs']==base_audit['costs']
            detailed=audit(path,stderr,case['seed'])
            assert detailed['hits']==checked['hits'] and detailed['misses']==checked['misses'] and detailed['callback_count']==checked['callbacks']
            rec={'case':case['path'],'seed':case['seed'],'family':case['family'],'input_sha256':case['sha256'],
                 'build_freeze_sha256':sha(HERE/'PHASE_A_BUILD_FREEZE_V1.json'),'reference_canonical_sha256':sha(canonical),
                 'reference_success_attempt':work.name,'reference_stdout_sha256':sha(base_stdout),'reference_stderr_sha256':sha(base_stderr),
                 'trace':actual_trace,'trace_byte_identical_to_reference':True,'independent_byte_audit':checked,
                 'reference_precision_check':base_audit['precision'],'observer_wall_seconds_not_deployment_timing':observer_wall,
                 'observation_audit':detailed,'observer_stdout_sha256':sha(stdout),'observer_stderr_sha256':sha(stderr)}
            save(result_path,rec);records.append(rec)
            print('PhaseA',len(records),'/24',identifier,'pressure',sum(detailed['independent_pressure_counts']),'wall',round(observer_wall,2),flush=True)
        (OUT/'status.json').write_text(json.dumps({'state':'running','complete':len(records)})+'\n')
    assert_old_freezes()
    save(HERE/'PHASE_A_RESULTS_V1.json',{'complete':True,'scope':freeze['scope'],'build_freeze_sha256':sha(HERE/'PHASE_A_BUILD_FREEZE_V1.json'),
        'rows':records,'new_observer_runs':24,'new_reference_runs':0,'teacher_runs':0,'model_training_runs':0,'dev_eval_accesses':0})
    (OUT/'status.json').write_text(json.dumps({'state':'complete','complete':24})+'\n');print('PhaseA complete',flush=True)
if __name__=='__main__':main()
