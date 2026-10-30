"""Bounded production generation and independent auditing. No scheduler runs."""
import argparse,concurrent.futures,gzip,hashlib,json,os,platform,signal,struct,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf8')
def args_for(parameters):return [v for k,x in parameters.items() for v in ('--'+k,str(x))]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=600);ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--tests-only',action='store_true');a=ap.parse_args()
    assert os.name=='posix' and 1<=a.jobs<=2 and a.seconds>0
    recipe_bytes=(ROOT/'recipe.json').read_bytes();recipe=json.loads(recipe_bytes);recipe_hash=hashlib.sha256(recipe_bytes).hexdigest();assert len(recipe['cases'])==40
    local=ROOT/'.local_work';local.mkdir(exist_ok=True)
    report_path=ROOT/('test_report.json' if a.tests_only else 'validation.json')
    assert not report_path.exists(),'immutable run result exists; do not overwrite'
    start=time.perf_counter();deadline=start+a.seconds;cancel=threading.Event();results=[];error=None;active=set();active_lock=threading.Lock()
    stage=Path('/var/tmp')/('stat_dataset_'+sha(ROOT/'recipe.json')[:16]+('_tests_' if a.tests_only else '_')+str(time.time_ns()))
    stage.mkdir(exist_ok=False)
    source_files=sorted(p for folder in ['source','tools','tests','audit'] for p in (ROOT/folder).glob('*') if p.is_file() and p.suffix in ['.py','.cpp','.hpp'])
    source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in source_files}
    if not a.tests_only:
        assert not (ROOT/'generation_protocol.json').exists(),'production protocol already frozen; do not silently rerun'
        dump(ROOT/'generation_protocol.json',{'recipe_sha256':recipe_hash,'source_sha256':source_hashes,'cases':recipe['cases'],
             'budget_seconds':a.seconds,'jobs':a.jobs,'frozen_before_native':True,'seed_substitution':False,'score_filtering':False})
    def remaining():
        if cancel.is_set():raise RuntimeError('batch cancelled after earlier failure')
        left=deadline-time.perf_counter()
        if left<=0:raise TimeoutError('frozen batch wall-clock budget exhausted')
        return left
    def run(cmd,stem):
        timeout=remaining();p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        with active_lock:active.add(p.pid)
        try:
            try:stdout,stderr=p.communicate(timeout=timeout)
            except BaseException:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.communicate();raise
        finally:
            with active_lock:active.discard(p.pid)
        (local/(stem+'.stdout')).write_text(stdout);(local/(stem+'.stderr')).write_text(stderr)
        if p.returncode:raise RuntimeError(stem+': '+stderr[-1600:])
        return subprocess.CompletedProcess(cmd,p.returncode,stdout,stderr)
    def generate(case,directory):
        directory.mkdir(exist_ok=True,parents=True)
        paths={k:directory/(case['case_id']+ext) for k,ext in [('out','.txt'),('meta','.json'),('trace','.csv')]}
        assert not any(p.exists() for p in paths.values())
        run([str(stage/'generator'),*args_for(case['parameters']),*args_for(paths)],case['case_id']+'_generate')
        return paths
    def compare(meta,audit):
        assert audit['valid'] and meta['operations']==audit['operations']
        for k in ['K','P','memory','build_counts','probe_counts','partition_bytes','partition_inserts','partition_probes','switch_at_zero_based','mixed_phase_steps_including_SWITCH']:
            assert meta[k]==audit[k],('generator/independent audit differs',k)
        assert meta['build_bytes']==audit['total_build_bytes']
        assert max(audit['partition_bytes'])<=audit['memory']*3//4
        assert min(audit['partition_bytes'])>0 and meta['max_probability_sum_error']<1e-12
        assert meta['mean_probe_l1_per_tick']==0 if meta['temporal']=='static' else meta['mean_probe_l1_per_tick']>0
    def unit_checks():
        run([str(stage/'process_test')],'process_test');run([str(stage/'hash_test')],'hash_test')
        fixture={'case_id':'fixture_a','parameters':dict(recipe['cases'][0]['parameters'],n=10000,k=2,p=16,memory=67108864,pressure=1.5,family='mixed',temporal='mixed',phase='staggered',trace_every=1024)}
        p=generate(fixture,stage/'fixtures');fixture['case_id']='fixture_b';q=generate(fixture,stage/'fixtures')
        assert all(sha(p[k])==sha(q[k]) for k in p),'same seed changed bytes'
        audit=json.loads(run([str(stage/'audit'),str(p['out']),'10000','10000'],'fixture_audit').stdout)
        compare(json.loads(p['meta'].read_text()),audit)
        lines=p['out'].read_text().splitlines();norm=hashlib.sha256();part=hashlib.sha256()
        def integer(h,x):h.update(struct.pack('>Q',int(x)))
        for h in (norm,part):integer(h,2);integer(h,16)
        for line in lines[4:]:
            v=line.split();tag={'INSERT':b'I','PROBE':b'P','SWITCH':b'S'}[v[0]]
            for h in (norm,part):h.update(tag);integer(h,v[1])
            if v[0]!='SWITCH':integer(norm,v[2]);integer(part,int(v[2])%16)
            if v[0]=='INSERT':integer(norm,v[3]);integer(part,v[3])
        assert norm.hexdigest()==audit['normalized_operation_sha256'] and part.hexdigest()==audit['partition_stream_sha256']
        bad=[]
        zero=lines.copy();i=next(i for i,x in enumerate(zero) if x.startswith('INSERT '));v=zero[i].split();v[-1]='0';zero[i]=' '.join(v);bad.append(('zero_tuple',zero))
        switched=lines.copy();i=next(i for i,x in enumerate(switched) if x.startswith('SWITCH '));switched[i]='PROBE '+switched[i].split()[1]+' 0';bad.append(('missing_switch',switched))
        bad.append(('extra_record',lines+['PROBE 0 0']))
        for name,body in bad:
            path=stage/(name+'.txt');path.write_text('\n'.join(body)+'\n')
            result=subprocess.run([str(stage/'audit'),str(path)],capture_output=True,text=True,timeout=remaining());assert result.returncode!=0,name
            (local/(name+'.stderr')).write_text(result.stderr)
        return {'native_process_invariants':'PASS','sha256_standard_vectors':'PASS','exact_fixture_reproduction':'PASS','python_vs_cpp_semantic_sha256':'PASS','invalid_stream_rejections':[x[0] for x in bad]}
    def one(case):
        name=case['case_id'];begin=time.perf_counter();paths=generate(case,ROOT/case['split'])
        meta=json.loads(paths['meta'].read_text())
        audited=json.loads(run([str(stage/'audit'),str(paths['out']),str(max(1,case['parameters']['n']//32)),str(case['parameters']['n'])],name+'_audit').stdout)
        compare(meta,audited)
        metadata=ROOT/'metadata';metadata.mkdir(exist_ok=True)
        # Only move files produced by this case; no recursive moves or deletes.
        meta_path=metadata/(name+'.json');trace_path=metadata/(name+'.probabilities.csv')
        paths['meta'].replace(meta_path);paths['trace'].replace(trace_path)
        audit_path=ROOT/'audit'/'cases'/(name+'.json');audit_path.parent.mkdir(exist_ok=True);dump(audit_path,audited)
        archive=ROOT/'archives'/case['split']/(name+'.txt.gz');archive.parent.mkdir(exist_ok=True,parents=True);assert not archive.exists()
        rawhash=hashlib.sha256()
        with paths['out'].open('rb') as src,archive.open('xb') as dst,gzip.GzipFile(filename='',mode='wb',fileobj=dst,mtime=0,compresslevel=1) as gz:
            for chunk in iter(lambda:src.read(1048576),b''):remaining();rawhash.update(chunk);gz.write(chunk)
        roundtrip=hashlib.sha256()
        with gzip.open(archive,'rb') as f:
            for chunk in iter(lambda:f.read(1048576),b''):remaining();roundtrip.update(chunk)
        assert rawhash.digest()==roundtrip.digest(),'gzip roundtrip changed input'
        def rel(p):return p.relative_to(ROOT).as_posix()
        return {'case_id':name,'split':case['split'],'parameters':case['parameters'],'input':rel(paths['out']),'sha256':rawhash.hexdigest(),'bytes':paths['out'].stat().st_size,
            'metadata':rel(meta_path),'metadata_sha256':sha(meta_path),'probabilities':rel(trace_path),'probabilities_sha256':sha(trace_path),
            'audit':rel(audit_path),'audit_sha256':sha(audit_path),'archive':rel(archive),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,
            'gzip_roundtrip_sha256':roundtrip.hexdigest(),'normalized_operation_sha256':audited['normalized_operation_sha256'],'partition_stream_sha256':audited['partition_stream_sha256'],
            'mean_probe_l1_per_tick':meta['mean_probe_l1_per_tick'],'maximum_probe_probability':meta['maximum_probe_probability'],
            'realized_pressure':audited['pressure'],'mixed_phase_operations':audited['mixed_phase_operations'],'seconds':time.perf_counter()-begin,'status':'COMPLETE'}
    try:
        compiler=run(['g++','--version'],'compiler_version').stdout.splitlines()[0]
        for target,source in [('generator','source/generator.cpp'),('audit','audit/audit.cpp'),('process_test','tests/process_test.cpp'),('hash_test','tests/hash_test.cpp')]:
            run(['g++','-std=c++14','-O2',str(ROOT/source),'-o',str(stage/target)],'compile_'+target)
        tests=unit_checks();dump(ROOT/'test_report.json',tests) if not a.tests_only else None
        if a.tests_only:dump(report_path,tests);return
        for split in ['train','dev','eval']:
            (ROOT/split).mkdir(exist_ok=True);(ROOT/split/'VERSION').write_text('1.0.0\n')
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
            futures={pool.submit(one,c):c for c in recipe['cases']}
            for future in concurrent.futures.as_completed(futures):
                try:result=future.result()
                except BaseException:cancel.set();raise
                results.append(result);dump(ROOT/'partial_manifest.json',{'completed':results})
                print(json.dumps({'completed':len(results),'of':40,'case':result['case_id'],'elapsed_seconds':time.perf_counter()-start}),flush=True)
        results.sort(key=lambda r:next(i for i,c in enumerate(recipe['cases']) if c['case_id']==r['case_id']))
        for key in ['sha256','normalized_operation_sha256','partition_stream_sha256']:
            assert len({r[key] for r in results})==40,('duplicate input/semantics',key)
        assert {p.relative_to(ROOT).as_posix():sha(p) for p in source_files}==source_hashes,'source changed during batch'
        assert sha(ROOT/'recipe.json')==recipe_hash,'frozen recipe changed during batch'
        summary={'cases':40,'operations':sum(r['parameters']['n'] for r in results),'raw_bytes':sum(r['bytes'] for r in results),'archive_bytes':sum(r['archive_bytes'] for r in results),
                 'splits':{s:{'cases':sum(r['split']==s for r in results),'operations':sum(r['parameters']['n'] for r in results if r['split']==s)} for s in ['train','dev','eval']}}
        manifest={'name':'stat_dataset','version':'1.0.0','recipe_sha256':recipe_hash,'source_sha256':source_hashes,
                  'build':{'compiler':compiler,'flags':['-std=c++14','-O2'],'generator_sha256':sha(stage/'generator'),'auditor_sha256':sha(stage/'audit')},'summary':summary,'cases':results}
        dump(ROOT/'manifest.json',manifest)
        dump(report_path,{'status':'COMPLETE_ALL_INPUTS_INDEPENDENTLY_AUDITED','tests':tests,'summary':summary,'manifest_sha256':sha(ROOT/'manifest.json'),
            'recipe_sha256':recipe_hash,'sources_unchanged_during_batch':True,'every_gzip_roundtrip_verified':True,'cross_split_raw_normalized_and_partition_hash_duplicates':0,
            'historical_dataset_semantic_comparison':'not performed; unique new seed namespace, no copied historical inputs; no broader isolation claim',
            'scheduler_performance_runs':0,'model_training_runs':0,'seconds':time.perf_counter()-start,'budget_seconds':a.seconds,'jobs':a.jobs,'generator_and_validator_independent':True})
    except BaseException as e:
        error=repr(e);dump(ROOT/'failure.json',{'error':error,'completed_cases':[r['case_id'] for r in results],'seconds':time.perf_counter()-start});raise
    finally:
        dump(ROOT/'cpu_released.json',{'status':'RELEASED','active_child_processes':len(active),'timeout_cleanup':'SIGKILL to spawned process group, then reap direct process','error':error,'seconds':time.perf_counter()-start})
if __name__=='__main__':main()
