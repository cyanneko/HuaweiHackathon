"""Authorized 65 states x 4 branches; first eight audited in-process, no model."""
import os,sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,re,subprocess,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
from build import FROZEN,FROZEN_SHA,REPO
from round9.cost_replay_precise import parse_input
from audit_next_action_v1 import CaseAudit
from run_phase_a import assert_old_freezes
SOURCE=ROOT/'round9/candidates/paired_penalty100.cpp'
SOURCE_SHA='3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15'
OUT=HERE/'build/next_action_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,value):
    text=json.dumps(value,indent=2)+'\n'
    if path.exists():assert path.read_text()==text,path
    else:path.write_text(text)
def put(path,text):
    if path.exists():assert path.read_text()==text,path
    else:path.write_text(text)
def generated_source():
    assert sha(SOURCE)==SOURCE_SHA
    policy=SOURCE.read_text().replace('MySpillScheduler','NAPolicy')
    summary='''public:
    const NAChoice& choice()const{return na_choice_;}
    void continuation(int mode){na_continuation_=mode;}
    std::string summary()const{
        std::ostringstream o;o<<std::setprecision(17)<<"{\\"miss_calls\\":"<<na_miss_calls_<<",\\"continuation\\":"<<na_continuation_
          <<",\\"sample_q\\":"<<sample_q_<<",\\"sample_total\\":"<<sample_total_<<",\\"sample_squares\\":"<<sample_squares_
          <<",\\"observed_q\\":"<<observed_q_<<",\\"observed_count\\":"<<observed_count_<<",\\"cycle\\":"<<uniform_cycle_<<",\\"streak\\":"<<streak_<<"}";return o.str();
    }
    std::vector<Action> onMemoryOverflow'''
    edits=[
      ('class NAPolicy : public SpillScheduler {','class NAPolicy : public SpillScheduler {\n    NAChoice na_choice_;int na_continuation_=0;int64_t na_miss_calls_=0;'),
      ('        ++paired_checks_;','        na_choice_.eligible=true;na_choice_.history=actions;na_choice_.dynamic=alternative;\n        ++paired_checks_;'),
      ('        if(!different)return;','        na_choice_.different=different;na_choice_.immediate=immediate;na_choice_.mean=mean;\n        if(!different)return;'),
      ('        if(immediate+64.0*mean+2.0*sd>=0)return;','        na_choice_.sd=sd;na_choice_.effective=effective;na_choice_.margin=immediate+64.0*mean+2.0*sd;\n        if(immediate+64.0*mean+2.0*sd>=0 && na_continuation_!=1)return;'),
      ('        actions.swap(alternative);++paired_chosen_;','        na_choice_.chosen=true;actions.swap(alternative);++paired_chosen_;'),
      ('public:\n    std::vector<Action> onMemoryOverflow',summary),
      ('        active_ = true; update(s);','        na_choice_=NAChoice{};active_ = true; update(s);'),
      ('        active_ = true; update(s,op,pid);','        na_choice_=NAChoice{};++na_miss_calls_;active_ = true; update(s,op,pid);'),
      ('        std::vector<Action> a;\n        update(s); sampleNext(s,1);','        na_choice_=NAChoice{};std::vector<Action> a;\n        update(s); sampleNext(s,1);')]
    for old,new in edits:assert policy.count(old)==1,old;policy=policy.replace(old,new)
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(x for x in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in x).replace('\xa0',' ')
    declarations=ref.split('class NaiveSpillScheduler',1)[0]
    code=(HERE/'next_action_teacher_v1.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',policy)
    return code,edits,hashlib.sha256(declarations.encode()).hexdigest()
def main():
    proposal_path=HERE/'NEXT_ACTION_OPPORTUNITY_PROPOSAL_V1.json';proposal=json.loads(proposal_path.read_text())
    phase=json.loads((HERE/'PHASE_A_RESULTS_V1.json').read_text());phase_by={r['case']:r for r in phase['rows']}
    old=json.loads((HERE/'PHASE_A_FINAL_FREEZE_V1.json').read_text())
    for a in old['artifacts']:assert sha(HERE/a['path'])==a['sha256']
    assert sha(HERE/'PHASE_A_RESULTS_V1.json')==proposal['phase_a_results_sha256']
    full=[s for s in proposal['states'] if s['complete_8192']];assert len(full)==65
    cases=list(dict.fromkeys(s['case'] for s in full));assert len(cases)==23
    lock_path=ROOT/'round9/V21_DATASET_LOCK.json';lock=json.loads(lock_path.read_text())
    assert set(cases)<=set(lock['pilot_train'])
    data=ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset'
    OUT.mkdir(exist_ok=True)
    with experiment_lock():
        assert_old_freezes();code,edits,decl_sha=generated_source();cpp=OUT/'teacher.cpp';put(cpp,code)
        exe=OUT/'teacher'
        if not exe.exists():
            proc=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic',str(cpp),'-o',str(exe)],capture_output=True,text=True)
            put(OUT/'compile.log',proc.stderr);proc.check_returncode()
        files=['NEXT_ACTION_OPPORTUNITY_PLAN_V1.md','NEXT_ACTION_EXECUTION_CONTRACT_V1.md','NEXT_ACTION_OPPORTUNITY_PROPOSAL_V1.json',
               'freeze_next_action_proposal_v1.py','next_action_teacher_v1.cpp','audit_next_action_v1.py','run_next_action_v1.py']
        freeze={'scope':'authorized finite two-continuation opportunity; no EM/training/dev/eval',
                'files':{f:sha(HERE/f) for f in files},'paired100_sha256':SOURCE_SHA,'official_reference_sha256':FROZEN_SHA,
                'official_declarations_sha256':decl_sha,'generated_source_sha256':sha(cpp),'source_insertions':edits,
                'phase_a_final_freeze_sha256':sha(HERE/'PHASE_A_FINAL_FREEZE_V1.json'),'dataset_lock_sha256':sha(lock_path),
                'independent_parser_sha256':sha(ROOT/'round9/cost_replay_precise.py'),'branches':260,'collector_prefixes':23}
        save(HERE/'NEXT_ACTION_BUILD_FREEZE_V1.json',freeze)
    if '--prepare-only' in sys.argv:print('Next action prepared, no collector/branch',flush=True);return
    results=[]
    for case in cases:
        states=[s for s in full if s['case']==case];identifier=Path(case).stem;work=OUT/identifier;work.mkdir(exist_ok=True)
        canonical=work/'result.json'
        with experiment_lock():
            for name,h in freeze['files'].items():assert sha(HERE/name)==h
            if canonical.exists():
                row=json.loads(canonical.read_text());assert row['build_freeze_sha256']==sha(HERE/'NEXT_ACTION_BUILD_FREEZE_V1.json');results.append(row);continue
            previous=phase_by[case];path=data/case;assert sha(path)==previous['input_sha256']
            reference=ROOT/'build/round9/proxy100_baseline_v2'/previous['reference_success_attempt']/'paired100_audit.stderr'
            assert sha(reference)==previous['reference_stderr_sha256']
            started=work/'started.json'
            if started.exists():raise RuntimeError('unfinished attempt retained, do not rerun: '+case)
            header,ops=parse_input(path);audit=CaseAudit(header,ops,reference,states,previous)
            selected=work/'selected.txt';put(selected,''.join(str(s['id'])+' '+str(s['raw_operation_index_zero_based'])+' '+str(s['q'])+'\n' for s in states))
            pause=proposal['audit_first_two_state_ids'][-1] if case==cases[0] else -1
            save(started,{'case':case,'input_sha256':previous['input_sha256'],'build_freeze_sha256':sha(HERE/'NEXT_ACTION_BUILD_FREEZE_V1.json'),'state_ids':[s['id'] for s in states]})
            stderr=work/'stderr.log';stdout=work/'stdout.log';rows=[];verified=[];completion=None;checkpoint=None
            with stderr.open('x') as err,stdout.open('x') as out:
                proc=subprocess.Popen([str(exe),str(path),str(selected),str(work),str(pause)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
                print('Collector started',identifier,'pid',proc.pid,'complete cases',len(results),flush=True)
                (OUT/'status.json').write_text(json.dumps({'state':'running','case':case,'pid':proc.pid,'complete_cases':len(results)})+'\n')
                try:
                    for line in proc.stdout:
                        out.write(line);out.flush()
                        if line.startswith('STATE '):
                            row=json.loads(line[6:]);checked=audit.row(row,work);rows.append(row);verified.append(checked)
                            save(work/('state_'+str(row['state_id'])+'_audit.json'),checked)
                            print('State audited',row['state_id'],'4 branches C0 exact',flush=True)
                        elif line.startswith('CHECKPOINT '):
                            assert [r['state_id'] for r in rows]==proposal['audit_first_two_state_ids']
                            callbacks=audit.collector_prefix(work/'collector.trace')
                            checkpoint={'state_ids':[r['state_id'] for r in rows],'branches':8,'all_independent_audits_pass':True,'C0_original_TRACE_exact':True,'collector_prefix_callbacks':callbacks,'first_eight_not_periodic_boundary_coverage':True}
                            save(HERE/'NEXT_ACTION_FIRST_EIGHT_AUDIT_V1.json',checkpoint)
                            print('First eight audit passed, continuing SAME collector process',flush=True)
                            proc.stdin.write('CONTINUE\n');proc.stdin.flush()
                        elif line.startswith('COMPLETE '):completion=json.loads(line[9:])
                        else:raise AssertionError(line)
                    code=proc.wait();assert code==0,(case,code)
                except BaseException:
                    # Closing input stops a checkpoint wait; failures are retained, never rerun here.
                    proc.stdin.close()
                    if proc.poll() is None:proc.terminate();proc.wait()
                    raise
            assert completion and len(rows)==len(states)
            callbacks=audit.collector_prefix(work/'collector.trace',completion)
            boundary=[]
            for state in states:
                counter=audit.snapshots[state['id']].count
                boundary.append({'state_id':state['id'],'current_periodic':(counter+1)%header[-1]==0,
                                 'endpoint4096_periodic':(counter+4096)%header[-1]==0,'endpoint8192_periodic':(counter+8192)%header[-1]==0})
            result={'case':case,'input_sha256':previous['input_sha256'],'build_freeze_sha256':sha(HERE/'NEXT_ACTION_BUILD_FREEZE_V1.json'),
                    'reference_stderr_sha256':sha(reference),'collector_trace_sha256':sha(work/'collector.trace'),
                    'collector_callbacks_byte_equal':callbacks,'collector_complete':completion,'rows':rows,'audits':verified,'periodic_boundaries':boundary,
                    'branch_trace_sha256':{b['trace']:sha(work/b['trace']) for row in rows for b in row['branches']},'header_offline_only':header}
            save(canonical,result);results.append(result)
            print('Case complete',len(results),'/23',identifier,'states',len(rows),flush=True)
    assert sum(len(x['rows']) for x in results)==65
    save(HERE/'NEXT_ACTION_RESULTS_V1.json',{'complete':True,'build_freeze_sha256':sha(HERE/'NEXT_ACTION_BUILD_FREEZE_V1.json'),
        'cases':results,'collector_runs':23,'branch_runs':260,'teacher_count':2,'model_training_runs':0,'em_runs':0,'dev_eval_accesses':0})
    (OUT/'status.json').write_text(json.dumps({'state':'complete','cases':23,'states':65,'branches':260})+'\n')
    print('Next action complete 65 states /260 branches',flush=True)
if __name__=='__main__':main()
