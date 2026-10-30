"""After root review only: compile one observer and run each fixed input at most once."""
import json
from pathlib import Path
import subprocess
import sys
import time
from prepare_v1 import ROOT,HERE,sha,save
from audit_v1 import audit
sys.path.insert(0,str(ROOT))
import build
from workflow import experiment_lock


def main():
    fp=HERE/'BUILD_FREEZE_V1.json';frozen=json.loads(fp.read_text());fh=sha(fp)
    output=HERE/'artifacts_v1';output.mkdir(exist_ok=False)
    def verify():
        assert sha(fp)==fh
        for n,h in frozen['files'].items():assert sha(HERE/n)==h,n
        for n,h in frozen['dependencies'].items():assert sha(ROOT/n)==h,n
    records=[]
    def status(state,**kw):
        (output/'status.json').write_text(json.dumps({'state':state,'completed':len(records),'planned':2,'build_freeze_sha256':fh,**kw},indent=2)+'\n')
    try:
        status('waiting_compile_lock')
        with experiment_lock():
            verify();status('compiling')
            exe=build.build(HERE/'r80_observer_v1.cpp','round11_r80_observer_v1_'+sha(HERE/'r80_observer_v1.cpp')[:10])
            buildmeta=exe.with_suffix('.build.json');meta=json.loads(buildmeta.read_text());assert meta['engine_unchanged'] and not meta['audit']
            execution={'build_freeze_sha256':fh,'executable':str(exe.relative_to(ROOT)),'executable_sha256':sha(exe),
                'generated_source_sha256':sha(exe.with_suffix('.cpp')),'builder_metadata_sha256':sha(buildmeta),
                'engine_unchanged':True,'instrumented':True,'maximum_solver_runs':2,'reference_runs':0,'performance_runs':0}
            save(HERE/'EXECUTION_FREEZE_V1.json',execution)
        for case in frozen['cases']:
            status('waiting_case_lock',case=case['case'])
            with experiment_lock():
                verify();path=ROOT/case['input'];assert sha(path)==case['input_sha256']
                assert sha(exe)==execution['executable_sha256'] and sha(exe.with_suffix('.cpp'))==execution['generated_source_sha256']
                ref=ROOT/case['reference_stdout'];assert sha(ref)==case['reference_run']['stdout_sha256']
                prefix=output/Path(case['case']).stem;so=Path(str(prefix)+'.stdout');se=Path(str(prefix)+'.stderr')
                assert not so.exists() and not se.exists();event={'case':case['case'],'input_sha256':case['input_sha256'],
                    'executable_sha256':execution['executable_sha256'],'returncode':None,'timed_out':False,'diagnostic_only':True}
                status('instrumented_solver',case=case['case']);started=time.perf_counter()
                try:
                    with so.open('xb') as out,se.open('xb') as err:
                        proc=subprocess.run([str(exe),str(path)],stdout=out,stderr=err,timeout=60)
                    event['returncode']=proc.returncode
                except BaseException as exc:
                    event.update(error_type=type(exc).__name__,error=str(exc),timed_out=isinstance(exc,subprocess.TimeoutExpired));raise
                finally:
                    event['diagnostic_wall_seconds']=time.perf_counter()-started
                    save(Path(str(prefix)+'.execution.json'),event)
                assert proc.returncode==0
                checked=audit(path,so,se,ref)
                record={'case':case['case'],'seed':case['seed'],'input_sha256':case['input_sha256'],
                    'build_freeze_sha256':fh,'execution_freeze_sha256':sha(HERE/'EXECUTION_FREEZE_V1.json'),
                    'stdout_sha256':sha(so),'stderr_sha256':sha(se),'audit':checked,'execution':event}
                save(Path(str(prefix)+'.json'),record);records.append(record)
            print('complete',len(records),'/2',case['case'],'snapshots',checked['snapshots'],'exact physical match',flush=True)
        save(HERE/'RESULTS_V1.json',{'complete':True,'build_freeze_sha256':fh,'execution_freeze_sha256':sha(HERE/'EXECUTION_FREEZE_V1.json'),
             'records':records,'instrumented_solver_runs':2,'new_reference_solver_runs':0,'new_performance_runs':0,
             'new_teacher_runs':0,'dev_eval_dyna_input_accesses':0,'promoted':False})
        status('complete')
    except BaseException as exc:
        status('failed',error_type=type(exc).__name__,error=str(exc));raise


if __name__=='__main__':main()
