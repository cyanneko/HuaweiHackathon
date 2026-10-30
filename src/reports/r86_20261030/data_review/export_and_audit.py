"""One bounded, eval-only Git export and full-stream audit. Never runs a generator/policy."""
from pathlib import Path,PurePosixPath
import collections,hashlib,importlib.util,json,os,signal,subprocess,sys,tarfile,time,traceback
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PLAN=OUT/'export_plan.json';PLAN_SHA='c0275620ed082c58e3f078e8a5e943f8ee3638e8e4646b028cd79751b3ebe028'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,obj):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def lin(p):return '/mnt/'+str(Path(p).resolve()).replace('\\','/')[0].lower()+str(Path(p).resolve()).replace('\\','/')[2:]
def worker():
    plan=read(PLAN);assert sha(PLAN)==PLAN_SHA
    start=time.monotonic();deadline=float(os.environ['R86_AUDIT_DEADLINE']);exported=[];results=[];failures=[];gitproc=None
    cache=Path(plan['cache_windows']).resolve();package=cache/'final_dataset';repo=Path(plan['repo_windows']);expected={e['path']:e for e in plan['files']}
    assert cache==ROOT/'tmp/r86_final3_cache' and cache.is_relative_to((ROOT/'tmp').resolve()) and not cache.exists()
    def checktime():
        if time.monotonic()>=deadline:raise TimeoutError('120 second export/audit budget exhausted')
    def gitbytes(commit,path):
        checktime();return subprocess.check_output(['git','-C',str(repo),'show',commit+':'+path],timeout=max(.01,deadline-time.monotonic()))
    def checkpoint(obj):
        with (OUT/'progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush()
    try:
        actual_tree=subprocess.check_output(['git','-C',str(repo),'rev-parse',plan['commit']+':final_dataset'],timeout=10).decode().strip()
        assert actual_tree==plan['tree'];cache.mkdir(exist_ok=False)
        directories={str(p) for name in expected for p in PurePosixPath(name).parents if str(p)!='.'}
        with (OUT/'archive.stderr').open('wb') as err:
            gitproc=subprocess.Popen(plan['archive_argv'],stdout=subprocess.PIPE,stderr=err)
            with tarfile.open(fileobj=gitproc.stdout,mode='r|') as tar:
                for member in tar:
                    checktime();name=member.name.rstrip('/')
                    if member.isdir():assert name in directories;continue
                    assert member.isfile() and name in expected,'unexpected tar member '+name
                    e=expected[name];assert member.size==e['bytes'] and name not in {x['path'] for x in exported}
                    target=(cache/name).resolve();assert target.is_relative_to(cache) and '..' not in PurePosixPath(name).parts
                    target.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();blob=hashlib.sha1(('blob '+str(member.size)+'\0').encode());size=0
                    with tar.extractfile(member) as src,target.open('xb') as dst:
                        while True:
                            chunk=src.read(1<<20)
                            if not chunk:break
                            checktime();dst.write(chunk);digest.update(chunk);blob.update(chunk);size+=len(chunk)
                    assert size==member.size and blob.hexdigest()==e['git_blob']
                    actual=digest.hexdigest();assert actual==e.get('declared_sha256',e.get('sha256'))
                    exported.append(dict(path=name,bytes=size,sha256=actual,git_blob=blob.hexdigest()))
            gitproc.stdout.close();assert gitproc.wait(timeout=max(.01,deadline-time.monotonic()))==0
        assert len(exported)==161 and sum(e['bytes'] for e in exported)==479972156
        assert not (package/'train').exists()
        write(OUT/'export_identity.json',dict(status='PASS',commit=plan['commit'],tree=plan['tree'],files=exported,seconds=time.monotonic()-start))
        checkpoint(dict(stage='EXPORT_PASS',files=len(exported),seconds=time.monotonic()-start))
        verify_path=package/'tools/verify.py';assert sha(verify_path)==plan['verifier_sha256']
        spec=importlib.util.spec_from_file_location('r86_unmodified_published_verifier',verify_path);verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)
        manifest_raw=(package/'manifest.json').read_bytes();manifest=verify.load_json(manifest_raw);recipe=verify.load_json((package/'recipe.json').read_bytes())
        assert sha(package/'manifest.json')==plan['manifest_sha256'] and sha(package/'recipe.json')==plan['recipe_sha256']==manifest['recipe_sha256']
        assert manifest['schema_version']==recipe['schema_version']==4 and manifest['version']==recipe['version']=='3.0.0'
        assert (package/'VERSION').read_text().strip()==(package/'eval/VERSION').read_text().strip()=='3.0.0'
        for name,h in recipe['tool_sha256'].items():assert sha(package/'tools'/name)==h
        allrows=manifest['cases'];rows=[r for r in allrows if r['split']=='eval'];items={r['path']:r for r in recipe['generated_cases']}
        assert len(allrows)==len(items)==612 and len(rows)==72
        assert collections.Counter(r['family'] for r in rows)==plan['family_counts']
        assert {p.relative_to(package).as_posix() for p in (package/'eval').glob('*.txt')}=={r['path'] for r in rows}
        assert {p.relative_to(package).as_posix() for p in (package/'eval').glob('*.meta.json')}=={str(PurePosixPath(r['path']).with_suffix('.meta.json')) for r in rows}
        parent_manifest=verify.load_json((package/'provenance/parent_manifest.json').read_bytes())
        parent_rows={r['path']:r for r in parent_manifest['cases']}
        def collect_records(obj):
            if isinstance(obj,dict):
                if all(k in obj for k in verify.HASH_FIELDS):yield obj
                for v in obj.values():yield from collect_records(v)
            elif isinstance(obj,list):
                for v in obj:yield from collect_records(v)
        parent_hash_records=list(collect_records(parent_manifest))
        for field in verify.HASH_FIELDS:
            assert len({r[field] for r in allrows})==612,'duplicate in published train/eval hash inventory'
            assert not ({r[field] for r in rows}&{r[field] for r in parent_hash_records}),'eval collision with declared parent hash inventory'
        published=verify.load_json((package/'reports/validation.json').read_bytes());published_rows={r['path']:r for r in published['cases']}
        assert published['status']=='passed' and published['summary']['passed_cases']==612 and not published['duplicates'] and not published['global_errors']
        assert published['manifest_sha256']==plan['manifest_sha256'] and published['recipe_sha256']==plan['recipe_sha256'] and published['verifier_sha256']==plan['verifier_sha256']
        contracts=[];parent_layouts=[]
        for row in rows:
            checktime();item=items[row['path']]
            assert item['split']==row['split']=='eval' and item['family']==row['family']
            actual=verify.verify_case(package.resolve(),row,plan['recipe_sha256'])
            checktime();meta_path=(package/row['path']).with_suffix('.meta.json');meta=verify.load_json(meta_path.read_bytes())
            assert meta['schema_version']==4 and meta['spec']==item['spec'] and meta['seed']==item['build_seed'] and meta['probe_seed']==item['probe_seed']
            assert meta['generator_sha256']==recipe['tool_sha256']['generate.py'] and meta['base_generator_sha256']==recipe['tool_sha256']['base_random_workloads.py'] and meta['strict_weights_sha256']==recipe['tool_sha256']['strict_weights.py']
            assert meta['parent']==dict(commit=recipe['source_data_commit'],path=item['parent_path'],sha256=item['parent_input_sha256'],metadata_sha256=item['parent_metadata_sha256'])
            parent=parent_rows[item['parent_path']]
            assert parent['split']=='eval' and parent['sha256']==item['parent_input_sha256'] and parent['metadata_sha256']==item['parent_metadata_sha256']
            layout_sha=hashlib.sha256(json.dumps(meta['partition_sizes'],separators=(',',':')).encode()).hexdigest()
            assert layout_sha==item['parent_partition_sizes_sha256'] and meta['insert_count']==item['parent_insert_count']
            # Read only each old small sidecar from its immutable Git commit, never an old raw input/cache.
            oldmeta_relative='final_dataset/'+str(PurePosixPath(item['parent_path']).with_suffix('.meta.json'))
            oldmeta_raw=gitbytes(recipe['source_data_commit'],oldmeta_relative)
            assert hashlib.sha256(oldmeta_raw).hexdigest()==item['parent_metadata_sha256']
            oldmeta=verify.load_json(oldmeta_raw)
            assert oldmeta['partition_sizes']==meta['partition_sizes'] and oldmeta['insert_count']==meta['insert_count']
            parent_layouts.append(dict(path=row['path'],parent_commit=recipe['source_data_commit'],parent_path=item['parent_path'],parent_metadata_sha256=item['parent_metadata_sha256'],partition_sizes_sha256=layout_sha,verified_against_actual_parent_sidecar=True))
            stored=published_rows[row['path']]
            assert stored['status']=='passed'
            for field in list(verify.HASH_FIELDS)+['metadata_sha256','operations','file_bytes','k','p','build_bytes']:assert actual[field]==stored[field]
            results.append(actual)
            inp=package/row['path'];par={key:meta[key] for key in ['k','p','memory','write','read','penalty','period']};par.update(n=meta['operations'],pressure=meta['spec']['pressure'])
            contracts.append(dict(case_id=inp.stem,split='eval',original_split='eval',family=row['family'],group='final72',input_path=str(inp),input_path_windows=str(inp),input_path_linux=lin(inp),input_sha256=actual['sha256'],metadata_path=str(meta_path),metadata_path_windows=str(meta_path),metadata_path_linux=lin(meta_path),metadata_sha256=actual['metadata_sha256'],meta_sha256=actual['metadata_sha256'],bytes=actual['file_bytes'],parameters=par,stats=dict(operations=meta['operations'],probe_count=meta['probe_count'],build_count=meta['insert_count'],switch_count=meta['switch_count'],penalty=meta['penalty']),operation_stream_sha256=actual['operation_stream_sha256'],partition_stream_sha256=actual['partition_stream_sha256'],parent_case_id=Path(item['parent_path']).stem,parent_path=item['parent_path'],parent_input_sha256=item['parent_input_sha256'],parent_partition_sizes_sha256=layout_sha,status='FULL_INPUT_AUDIT_PASS',audit_scope='eval-only full stream + probability certificate + actual parent sidecar BUILD layout'))
            checkpoint(dict(stage='CASE_PASS',case=row['path'],passed=len(results),seconds=time.monotonic()-start))
            if len(results)%12==0:print(json.dumps(dict(passed=len(results),total=72,seconds=time.monotonic()-start)),flush=True)
        assert len(results)==72 and sum(r['operations'] for r in results)==22528629 and sum(r['file_bytes'] for r in results)==474874682
        assert sha(package/'manifest.json')==plan['manifest_sha256'] and sha(package/'recipe.json')==plan['recipe_sha256']
        for name,h in recipe['tool_sha256'].items():assert sha(package/'tools'/name)==h
        write(OUT/'parent_layout_review.json',dict(status='PASS',cases=parent_layouts,parent_raw_inputs_read=0,parent_sidecars_read=72))
        target_ops=[v for c in results for v in c['probability_certificate']['per_operator']];observed_ops=[v for c in results for v in c['observed_per_operator']]
        summary=dict(cases=72,operations=22528629,input_bytes=474874682,operators=len(target_ops),family_counts=plan['family_counts'],minimum_target_tv=min(v['tv_from_uniform'] for v in target_ops),minimum_observed_tv=min(v['tv_from_uniform'] for v in observed_ops),minimum_target_hot_cold_ratio=min(v['hot_cold_ratio'] for v in target_ops),minimum_visited_partitions=min(v['visited_partitions'] for v in observed_ops),minimum_BUILD_size_ratio=min(c['build_partition_size_ratio'] for c in results),all_probability_and_observed_contracts_passed=True)
        write(OUT/'eval_audit.json',dict(status='PASS',scope='Locally rescanned all eval72 only, not train540/full612',summary=summary,cases=results,verifier_sha256=plan['verifier_sha256'],recipe_sha256=plan['recipe_sha256'],manifest_sha256=plan['manifest_sha256'],published612_report=dict(sha256=sha(package/'reports/validation.json'),status='passed',role='publisher stored evidence, not locally rerun'),duplicate_scope='all612 manifest hashes and parent declared hashes checked; only eval72 actual streams rescanned',parent_hash_records=len(parent_hash_records),seconds=time.monotonic()-start))
        write(cache/'data_manifest.json',dict(status='FULL_EVAL72_AUDIT_PASS',dataset_id='final_dataset',dataset_version='3.0.0',dataset_commit=plan['commit'],dataset_tree=plan['tree'],case_count=72,planned_cases=72,total_operations=22528629,input_bytes=474874682,family_counts=plan['family_counts'],cases=contracts,manifest_sha256=plan['manifest_sha256'],recipe_sha256=plan['recipe_sha256'],audit_path='tmp/r86_data_review/eval_audit.json',audit_sha256=sha(OUT/'eval_audit.json'),parent_layout_review_sha256=sha(OUT/'parent_layout_review.json'),export_identity_sha256=sha(OUT/'export_identity.json'),offline_only='Certificates/metadata/future counts are audit evidence, never online scheduler inputs',no_blind_generalization_claim=True,train_inputs_exported=0,scheduler_runs=0,generator_runs=0))
        write(OUT/'worker_result.json',dict(status='PASS',seconds=time.monotonic()-start,exported_files=len(exported),verified_cases=len(results),data_manifest_sha256=sha(cache/'data_manifest.json'),audit_sha256=sha(OUT/'eval_audit.json')))
    except BaseException as e:
        failures.append(dict(error=repr(e),traceback=traceback.format_exc()))
        write(OUT/'worker_failure.json',dict(status='PARTIAL_FAILED',seconds=time.monotonic()-start,exported_files=exported,verified_cases=results,failures=failures,unprocessed=72-len(results),no_retry=True))
        raise
    finally:
        if gitproc is not None and gitproc.poll() is None:gitproc.kill();gitproc.wait()

def controller():
    assert sha(PLAN)==PLAN_SHA and not (OUT/'controller_started.json').exists(),'unique authorized attempt only'
    start=time.monotonic();deadline=start+120
    write(OUT/'controller_started.json',dict(plan_sha256=PLAN_SHA,controller_sha256=sha(__file__),started_unix=time.time(),budget_seconds=120,scope='export+full eval-only input audit; no native policy'))
    env=dict(os.environ,R86_AUDIT_DEADLINE=str(deadline),PYTHONDONTWRITEBYTECODE='1')
    timed_out=False
    with (OUT/'window.stdout').open('wb') as out,(OUT/'window.stderr').open('wb') as err:
        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdout=out,stderr=err,env=env,start_new_session=os.name!='nt')
        try:p.wait(timeout=max(.01,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out=True
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=5)
            else:os.killpg(p.pid,signal.SIGKILL)
            p.wait(timeout=5)
    success=p.returncode==0 and not timed_out and (OUT/'worker_result.json').exists() and read(OUT/'worker_result.json')['status']=='PASS'
    release=dict(status='RELEASED',ready=success,final=success,active_child_processes=0,seconds=time.monotonic()-start,budget_seconds=120,worker_returncode=p.returncode,watchdog_timeout=timed_out,plan_sha256=PLAN_SHA,controller_sha256=sha(__file__),scheduler_runs=0,compile_runs=0,generator_runs=0,training_runs=0)
    if success:release.update(data_manifest_path='tmp/r86_final3_cache/data_manifest.json',data_manifest_sha256=sha(ROOT/'tmp/r86_final3_cache/data_manifest.json'),audit_sha256=sha(OUT/'eval_audit.json'),worker_result_sha256=sha(OUT/'worker_result.json'))
    write(OUT/'release.json',release);print(json.dumps(release),flush=True)
    return 0 if success else 1
if __name__=='__main__':
    if '--worker' in sys.argv:worker()
    else:raise SystemExit(controller())
