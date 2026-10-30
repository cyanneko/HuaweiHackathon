"""Build uninstrumented C++14/O2 binaries in persistent Linux HOME and bind evidence."""
import json
import base64
from pathlib import Path
import subprocess
import time
import pipeline as p
import verify_cpp as v

M=p.ROOT/'model_v2';OUT=M/'production'
def rel(path):return Path(path).resolve().relative_to(p.WS).as_posix()

def wsl(code,timeout=60):
    encoded=base64.b64encode(code.encode('utf8')).decode('ascii')
    bridge="import base64;exec(base64.b64decode('"+encoded+"'))"
    r=subprocess.run(['wsl','-d','Ubuntu','--','python3','-c',bridge],capture_output=True,timeout=timeout)
    if r.returncode:
        (OUT/'wsl_failure.log').write_bytes(r.stdout+r.stderr)
        raise RuntimeError('production WSL failed; see wsl_failure.log')
    lines=r.stdout.decode('utf8',errors='replace').splitlines()
    return json.loads(next(line for line in reversed(lines) if line.startswith('{')))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    validation=json.loads((M/'verification/report.json').read_text())
    cases=p.inventory();dev={k:m for k,m in cases.items() if m['split']=='dev'}
    assert len(dev)==8 and validation['passed'] and validation['max_score_error']==0
    checked={(r['case_id'],r['mode']):r for r in validation['results']}
    for case_id in dev:
        for mode in ('nn','heuristic'):
            r=checked[case_id,mode]
            assert r['input_sha256']==dev[case_id]['sha256'] and r['full_physical_next_actions_match'] and r['feature_history_score_callback_hashes_match']
    raw=v.FRAME.read_text(encoding='utf8');a=raw.index('class NaiveSpillScheduler');b=raw.index('class HashJoinEngine')
    suffix=raw[b:];needle='std::make_unique<NaiveSpillScheduler>()';replacement='std::make_unique<MySpillScheduler>()'
    assert suffix.count(needle)==1;changed=suffix.replace(needle,replacement);assert changed.replace(replacement,needle)==suffix
    specs=[]
    for name,filename in [('Heuristic','Heuristic.policy.hpp'),('TinyNN','MySpillScheduler.policy.hpp')]:
        source=M/filename;policy=source.read_text(encoding='utf8')
        assert 'R70DETAIL' not in policy and 'R66TRACE' not in policy
        tu=OUT/(name+'.cpp');tu.write_text(raw[:a]+policy+'\n'+changed,encoding='utf8')
        specs.append(dict(name=name,source_path=str(source),source_sha256=p.sha(source),
                          translation_unit_path=str(tu),translation_unit_sha256=p.sha(tu),linux_tu=v.linux(tu)))
    linux_code='''import hashlib,json,pathlib,subprocess,time
specs=json.loads(SPECS)
home=pathlib.Path.home();root=home/'.local/share/codex_benchmarks'/('r70_'+MODEL)
root.mkdir(parents=True,exist_ok=True)
compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0];results=[]
for s in specs:
 dest=root/(s['name']+'_'+s['translation_unit_sha256'][:12]);begin=time.perf_counter()
 command=['g++','-std=c++14','-O2',s['linux_tu'],'-o',str(dest)]
 r=subprocess.run(command,capture_output=True,text=True,timeout=45)
 if r.returncode:raise RuntimeError(r.stderr)
 results.append(dict(name=s['name'],binary_linux_path=str(dest),binary_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),command=command,compiler=compiler,stdout=r.stdout,stderr=r.stderr,seconds=time.perf_counter()-begin))
print(json.dumps(dict(home=str(home),compiler=compiler,methods=results)))
'''.replace('SPECS',repr(json.dumps(specs))).replace('MODEL',repr(p.sha(M/'model.json')[:16]))
    built=wsl(linux_code,120);records=[]
    for spec,item in zip(specs,built['methods']):
        record=OUT/(spec['name']+'.compile.json');p.dump(record,{**spec,**item,'instrumented':False,'framework_sha256':p.sha(v.FRAME),'engine_changed_only_scheduler_and_factory':True})
        records.append({**{k:spec[k] for k in ('name','source_sha256','translation_unit_sha256')},
                        'source_path':rel(spec['source_path']),'translation_unit_path':rel(spec['translation_unit_path']),
                        'role':'zero_residual_same32_pool_control' if spec['name']=='Heuristic' else 'frozen_trained_candidate',
                        'binary_linux_path':item['binary_linux_path'],'binary_sha256':item['binary_sha256'],
                        'framework_sha256':p.sha(v.FRAME),'compile_flags':['-std=c++14','-O2'],
                        'compile_record_path':rel(record),'compile_record_sha256':p.sha(record),'instrumented':False})
    # A later WSL call verifies persistence, binary identities and aggregate outputs.
    jobs=[dict(case_id=k,input=v.linux(m['path']),expected={mode:checked[k,mode] for mode in ('nn','heuristic')}) for k,m in dev.items()]
    check_code='''import hashlib,json,pathlib,subprocess
methods=json.loads(METHODS);jobs=json.loads(JOBS);checks=[]
for method in methods:
 path=pathlib.Path(method['binary_linux_path']);assert path.is_relative_to(pathlib.Path.home())
 assert hashlib.sha256(path.read_bytes()).hexdigest()==method['binary_sha256']
 for job in jobs:
  r=subprocess.run([str(path),job['input']],capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
  assert 'R70DETAIL' not in r.stderr and 'R66TRACE' not in r.stderr
  values={k:float(v.strip()) for line in r.stdout.splitlines() if ':' in line for k,v in [line.split(':',1)]}
  e=job['expected']['nn' if method['name']=='TinyNN' else 'heuristic']
  assert values['Hit_Count']==e['hits'] and values['Miss_Count']==e['misses']
  expected_io=e['write_bytes']/1000+e['read_bytes']/100
  assert abs(values['Total_IO_Time']-expected_io)<=.011
  checks.append(dict(case_id=job['case_id'],method=method['name'],aggregate_matches_diagnostic=True,formal_D=None))
print(json.dumps(dict(passed=True,checked=checks,persistent_home_reopened=True,holdout_runs=0)))
'''.replace('METHODS',repr(json.dumps(records))).replace('JOBS',repr(json.dumps(jobs)))
    final_check=wsl(check_code,120);p.dump(OUT/'production_check.json',final_check)
    p.dump(M/'feature_schema.json',dict(version=p.FEATURE_VERSION,names=p.FEATURE_NAMES,dimension=32,
                                      observation='current public callback plus causal executed-intent R65 history and physical next_op',
                                      hidden_penalty_future_seed_filename_N_as_features=False))
    p.dump(M/'preprocessing.json',dict(feature_version=p.FEATURE_VERSION,normalization='fixed dimensionless formulas; no fitted scaler',
                                     cast='double calculations then float32',max_plans=8,tie=['spill_count','integer_bytes','sorted_partition_ids'],
                                     label_normalization='integer G subtraction before division by same-state maxgap',
                                     inference='base x13 plus clipped [-1,1] residual; lower wins'))
    dependencies=[p.ROOT/'pipeline.py',p.ROOT/'verify_cpp.py',M/'policy.hpp',M/'shared_pool.hpp',M/'tiny_score.hpp',p.R66/'core.py',p.R70/'teacher_portfolio.py',p.WS/'tmp/r70_interval/interval_teacher.py']
    artifact=dict(schema_version=1,status='frozen_validated_ready_for_formal_D_after_Root_release',framework_sha256=p.sha(v.FRAME),
                  compiler=built['compiler'],compiler_flags=['-std=c++14','-O2'],model_json_path=rel(M/'model.json'),model_json_sha256=p.sha(M/'model.json'),
                  feature_schema_sha256=p.sha(M/'feature_schema.json'),preprocessing_sha256=p.sha(M/'preprocessing.json'),
                  feature_schema_path=rel(M/'feature_schema.json'),preprocessing_path=rel(M/'preprocessing.json'),
                  source_dependencies=[dict(path=rel(q),sha256=p.sha(q)) for q in dependencies],methods=records,
                  validation=dict(score_vectors_path=rel(M/'score_vectors.json'),score_vectors_sha256=p.sha(M/'score_vectors.json'),
                    score_check_report_path=rel(M/'verification/report.json'),score_check_report_sha256=p.sha(M/'verification/report.json'),
                    score_check_tolerances=dict(abs=0,rel=0),score_check_max_errors=dict(abs=validation['max_score_error']),
                    dev_parity_report_path=rel(M/'verification/report.json'),dev_parity_report_sha256=p.sha(M/'verification/report.json'),
                    dev_cases_checked=[dict(case_id=k,input_sha256=m['sha256']) for k,m in dev.items()],
                    dev_complete_action_match=True,dev_io_hit_miss_match=True,holdout_cases_used=0,
                    tested_source_hashes={r['name']:r['source_sha256'] for r in records},tested_binary_hashes={r['name']:r['binary_sha256'] for r in records},
                    production_check_path=rel(OUT/'production_check.json'),production_check_sha256=p.sha(OUT/'production_check.json'),
                    diagnostic_to_formal_equivalence='same flattened policies and unchanged engine; diagnostic adds only logging decorator and feature/history hash call; formal binaries independently rechecked on dev8 aggregate IO/hit/miss; diagnostic D unused'),
                  compute_release=dict(training_released=True,validation_released=True,worker_released=None,active_child_processes=0,
                                       worker_release_authority='Root must bind separate teacher-worker release'))
    p.dump(M/'producer_artifact.json',artifact);print(json.dumps(dict(path=str(M/'producer_artifact.json'),sha256=p.sha(M/'producer_artifact.json'),methods=records)),flush=True)

if __name__=='__main__':main()
