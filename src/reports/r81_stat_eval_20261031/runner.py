"""Frozen stat 1.0 R81/Naive evaluation. No compilation, tuning, retries or resume."""
from pathlib import Path
import argparse, ast, hashlib, json, math, os, signal, shutil, subprocess, time, traceback

O = Path(__file__).resolve().parent
ROOT = O.parents[1]
DATA = ROOT / 'stat_dataset'
MANIFEST = 'd6a3584ab2385e45c7aeeb30a1c2c4d5fdda013dd0606ff994dc264463558149'
R81 = 'R81_op256_cond2048'
HELPER = ROOT / 'tmp/r79_final_eval/process_helper.py'
PARSER = ROOT / 'tmp/r79_final_eval/dependencies/evaluation/evaluate.py'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def save(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(p)

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''): h.update(block)
    return h.hexdigest()

def require(ok, message):
    if not ok: raise RuntimeError(message)

def imported_function(path, name):
    # Execute the exact existing function AST with its explicit standard-library dependencies.
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(globals())
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[name]

def score(c, baseline):
    if c <= 0 or baseline <= 0: return 0.
    return min(10., max(0., 10. * (1. - c / baseline)))

def contract():
    require(not (O/'protocol.json').exists(), 'protocol already exists; no overwrite')
    require(sha(DATA/'manifest.json') == MANIFEST, 'stat manifest mismatch')
    manifest = load(DATA/'manifest.json')
    methods = [m for m in load(ROOT/'tmp/r87_eval/methods.prepared.json')['methods'] if m['name'] in ('Naive', R81)]
    require([m['name'] for m in methods] == ['Naive', R81], 'method selection')
    cases = []
    for c in manifest['cases']:
        if c['split'] != 'eval': continue
        require(sha(DATA/c['audit']) == c['audit_sha256'], 'audit identity')
        require(sha(DATA/c['metadata']) == c['metadata_sha256'], 'metadata identity')
        a = load(DATA/c['audit'])
        require(a['valid'] and a['operations'] == c['parameters']['n'] and a['penalty'] == c['parameters']['penalty'], 'audit consistency')
        cases.append(dict(case_id=c['case_id'], input=c['input'], input_sha256=c['sha256'],
            operations=a['operations'], family=c['parameters']['family'], temporal=c['parameters']['temporal'],
            phase=c['parameters']['phase'], audit=c['audit'], audit_sha256=c['audit_sha256'],
            metadata=c['metadata'], metadata_sha256=c['metadata_sha256'],
            stats=dict(probe_count=sum(a['probe_counts']), penalty=a['penalty'])))
    require(len(cases) == 10 and sum(c['operations'] for c in cases) == 42000000, 'eval size')
    dependencies = {str(p.relative_to(ROOT)): sha(p) for p in [HELPER, PARSER, ROOT/'tmp/r87_eval/methods.prepared.json']}
    for m in methods:
        for field in ['source', 'translation_unit']:
            require(sha(ROOT/m[field+'_path']) == m[field+'_sha256'], 'method '+field)
            dependencies[m[field+'_path']] = m[field+'_sha256']
    order = []
    for repeat in range(3):
        for i, c in enumerate(cases):
            names = ['Naive', R81] if (repeat+i)%2 == 0 else [R81, 'Naive']
            for name in names:
                order.append(dict(index=len(order), repeat=repeat, case_id=c['case_id'], method=name,
                                  cell_id=f'r{repeat}_{c["case_id"]}_{name}'))
    save(O/'protocol.json', dict(schema=1, manifest_sha256=MANIFEST, dataset_version=manifest['version'],
        methods=methods, cases=cases, order=order, dependencies=dependencies, repeats=3, intended_cells=60,
        serial=1, per_cell_wall_seconds=60, global_compute_seconds=900,
        budget='prepare elapsed plus formal wall; review wait excluded; 5 seconds reserved for cleanup',
        score='C or Naive <=0 gives 0; otherwise clip(10*(1-C/Naive),0,10); C=native Total_Score verified as IO+penalty*miss+real_D; per repeat then mean; ten cases equal weight',
        physical='IO+penalty*miss; physical_multiplier=Naive_physical/R81_physical',
        failure_policy='stop, preserve evidence, no retry/resume; no official score if any of 60 cells missing/invalid',
        quantiles='linear interpolation at (n-1)*q; descriptive distribution over ten case means',
        runner_sha256=sha(__file__)))
    print('CONTRACT_FROZEN 10 cases 42M operations 60 cells', flush=True)

def gates(p):
    require(sha(__file__) == p['runner_sha256'], 'runner changed')
    require(sha(DATA/'manifest.json') == p['manifest_sha256'], 'manifest changed')
    for name, digest in p['dependencies'].items(): require(sha(ROOT/name) == digest, 'dependency changed: '+name)
    for c in p['cases']:
        for field in ['audit', 'metadata']: require(sha(DATA/c[field]) == c[field+'_sha256'], field+' changed')
    require(not (O/'STOP_REQUESTED').exists(), 'stop requested')

def native_root():
    return Path.home()/'.local/share/codex_benchmarks'/('r81_stat_'+sha(O/'protocol.json')[:16])

def prepare():
    require(os.name == 'posix', 'WSL Linux required')
    p = load(O/'protocol.json'); gates(p)
    require(not (O/'prepare.json').exists(), 'prepare already attempted')
    start = time.monotonic(); n = native_root()
    require(not n.exists(), 'native root exists; no reuse')
    n.mkdir(parents=True); (n/'inputs').mkdir(); (n/'bin').mkdir()
    for c in p['cases']:
        src = DATA/c['input']; dst = n/'inputs'/Path(c['input']).name
        require(sha(src) == c['input_sha256'], 'source input SHA')
        shutil.copyfile(src, dst)
        require(sha(dst) == c['input_sha256'], 'native input SHA')
        dst.chmod(0o444)
    for m in p['methods']:
        require(sha(m['binary']) == m['binary_sha256'], 'producer ELF SHA')
        dst = n/'bin'/m['name']; shutil.copyfile(m['binary'], dst); dst.chmod(0o555)
        require(sha(dst) == m['binary_sha256'], 'native ELF SHA')
    gates(p)
    save(O/'prepare.json', dict(status='PASS', seconds=time.monotonic()-start, native_root=str(n),
         protocol_sha256=sha(O/'protocol.json'), input_sha_verified=10, elf_sha_verified=2))
    print(json.dumps(load(O/'prepare.json')), flush=True)

def selftest():
    parse = imported_function(PARSER, 'parse_metrics')
    good = 'Total_IO_Time: 1\nTotal_Decision_Time: 2\nHit_Count: 3\nMiss_Count: 1\nTotal_Score: 13\n'
    require(parse(good, {'penalty':10,'probe_count':4}, 'official-2026-10-26')['Total_Score']==13, 'parser valid')
    for bad in [good+'Hit_Count: 3\n', good.replace('Total_Score: 13','Total_Score: 12'),
                good.replace('Hit_Count: 3','Hit_Count: 2'), good.replace('Total_Decision_Time: 2','Total_Decision_Time: nan')]:
        try: parse(bad, {'penalty':10,'probe_count':4}, 'official-2026-10-26')
        except ValueError: pass
        else: raise RuntimeError('parser accepted invalid metrics')
    require(score(50,100)==5 and score(120,100)==0 and score(0,100)==0 and score(10,0)==0, 'score clipping')
    require((score(50,100)+score(200,100))/2==2.5, 'score before averaging')
    p=load(O/'protocol.json'); gates(p)
    require(len({x['cell_id'] for x in p['order']})==60, 'cell uniqueness')
    require(all(p['order'][i]['method'] != p['order'][i+1]['method'] for i in range(0,60,2)), 'pair order')
    save(O/'contract_tests.json', dict(status='PASS', tests=9, protocol_sha256=sha(O/'protocol.json')))
    print('CONTRACT_TESTS_PASS', flush=True)

def run():
    require(os.name=='posix', 'Linux required')
    p=load(O/'protocol.json'); prep=load(O/'prepare.json'); gates(p)
    require(prep['status']=='PASS' and prep['protocol_sha256']==sha(O/'protocol.json'), 'prepare identity')
    require(not (O/'controller.json').exists(), 'formal already attempted; retries forbidden')
    go=load(O/'GO.json')
    require(go['authorized'] is True and go['protocol_sha256']==sha(O/'protocol.json'), 'GO required')
    n=Path(prep['native_root']); start=time.monotonic(); rows=[]; error=None
    prior_prepare=load(O/'prepare.preflight_v1.json')['seconds'] if (O/'prepare.preflight_v1.json').exists() else 0
    budget=900-prep['seconds']-prior_prepare; require(budget>10, 'budget consumed')
    def cancel(signum, frame): raise TimeoutError('controller interrupted/deadline '+str(signum))
    signal.signal(signal.SIGALRM,cancel); signal.signal(signal.SIGTERM,cancel); signal.signal(signal.SIGINT,cancel)
    signal.setitimer(signal.ITIMER_REAL,budget-5)
    checked_run=imported_function(HELPER,'checked_run'); parse=imported_function(PARSER,'parse_metrics')
    save(O/'controller.json', dict(status='RUNNING', intended=60, protocol_sha256=sha(O/'protocol.json'), started_unix=time.time(), budget_seconds=budget))
    try:
        for c in p['cases']: require(sha(n/'inputs'/Path(c['input']).name)==c['input_sha256'], 'native startup input')
        for item in p['order']:
            require(sha(O/'protocol.json')==prep['protocol_sha256'], 'protocol changed')
            gates(p)
            c=next(c for c in p['cases'] if c['case_id']==item['case_id'])
            m=next(m for m in p['methods'] if m['name']==item['method'])
            inp=n/'inputs'/Path(c['input']).name; exe=n/'bin'/m['name']; folder=O/'cells'/item['cell_id']
            require(sha(exe)==m['binary_sha256'], 'native ELF changed')
            require(sha(inp)==c['input_sha256'], 'input changed before cell')
            remaining=budget-5-(time.monotonic()-start)
            require(remaining>2, 'budget exhausted')
            process=checked_run([str(exe),str(inp)],folder,min(60,remaining),cwd=n)
            row=dict(item, process=process, valid=False, metrics=None, input_sha256=c['input_sha256'],binary_sha256=m['binary_sha256'])
            rows.append(row); save(folder/'result.json',row)
            require(process['status']=='EXITED' and process['returncode']==0,'native failure '+item['cell_id'])
            require((folder/'stderr.txt').stat().st_size==0,'unexpected stderr '+item['cell_id'])
            metrics=parse((folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26')
            require(sha(inp)==c['input_sha256'] and sha(exe)==m['binary_sha256'],'cell identity changed')
            row.update(valid=True,metrics=metrics); save(folder/'result.json',row)
            save(O/'progress.json',dict(completed=len(rows),valid=sum(r['valid'] for r in rows),intended=60))
            print(json.dumps(dict(event='CELL',completed=len(rows),intended=60,case=c['case_id'],method=m['name'],wall=process['wall_seconds'])),flush=True)
        gates(p)
        for c in p['cases']:
            require(sha(DATA/c['input'])==c['input_sha256'],'producer input changed')
            require(sha(n/'inputs'/Path(c['input']).name)==c['input_sha256'],'native final input changed')
        for m in p['methods']: require(sha(m['binary'])==m['binary_sha256'],'producer ELF changed')
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        save(O/'error.json',error)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        active=[]
        for f in (O/'cells').glob('*/ownership.json'):
            owner=load(f)
            if not owner['cleaned']: active.append(owner['pid'])
        ok=error is None and len(rows)==60 and all(r['valid'] for r in rows) and not active
        save(O/'controller.json',dict(status='PASS' if ok else 'FAILED',intended=60,completed=len(rows),
            valid=sum(r['valid'] for r in rows),protocol_sha256=sha(O/'protocol.json'),
            seconds=time.monotonic()-start,prepare_seconds=prep['seconds'],prior_prepare_seconds=prior_prepare,
            global_seconds=time.monotonic()-start+prep['seconds']+prior_prepare,error=error))
        save(O/'cpu_released.json',dict(active_children=len(active),unresolved_pids=active,unix_seconds=time.time()))
    summarize()
    require(ok,'formal evaluation failed; evidence retained; no retry')

def distribution(values):
    a=sorted(values)
    def q(t):
        x=(len(a)-1)*t; lo=int(x); hi=min(lo+1,len(a)-1)
        return a[lo]+(a[hi]-a[lo])*(x-lo)
    return dict(mean=sum(a)/len(a),P50=q(.5),P90=q(.9),min=a[0],max=a[-1])

def summarize():
    p=load(O/'protocol.json'); ctl=load(O/'controller.json'); gates(p)
    rows=[]; missing=[]
    for item in p['order']:
        f=O/'cells'/item['cell_id']/'result.json'
        if not f.exists(): missing.append(item); continue
        r=load(f); folder=f.parent
        require(all(r[k]==v for k,v in item.items()), 'cell order identity')
        require(sha(folder/'stdout.txt')==r['process']['stdout_sha256'] and sha(folder/'stderr.txt')==r['process']['stderr_sha256'], 'output changed')
        rows.append(r)
    complete=ctl['status']=='PASS' and len(rows)==60 and all(r['valid'] for r in rows) and not missing and not (O/'error.json').exists()
    result=dict(status='PASS' if complete else 'INCOMPLETE_NO_OFFICIAL_SCORE',intended_cases=10,intended_cells=60,
        observed_cells=len(rows),missing_cells=missing,invalid_cells=[r['cell_id'] for r in rows if not r['valid']],
        official_score=None,protocol_sha256=sha(O/'protocol.json'),controller_sha256=sha(O/'controller.json'))
    if complete:
        cases=[]
        nondeterministic=[]
        for c in p['cases']:
            for name in ['Naive',R81]:
                samples=[r['metrics'] for r in rows if r['case_id']==c['case_id'] and r['method']==name]
                for key in ['Total_IO_Time','Hit_Count','Miss_Count']:
                    values=[v[key] for v in samples]
                    if len(set(values))!=1: nondeterministic.append(dict(case_id=c['case_id'],method=name,metric=key,values=values))
            pairs=[]
            for repeat in range(3):
                metrics={r['method']:r['metrics'] for r in rows if r['case_id']==c['case_id'] and r['repeat']==repeat}
                m={}
                for name,v in metrics.items():
                    physical=v['Total_IO_Time']+c['stats']['penalty']*v['Miss_Count']
                    m[name]=dict(cost=v['Total_Score'],reconstructed_cost=physical+v['Total_Decision_Time'],physical=physical,IO=v['Total_IO_Time'],hit=v['Hit_Count'],miss=v['Miss_Count'],D=v['Total_Decision_Time'])
                require(m[R81]['physical']>0 and m['Naive']['physical']>0,'nonpositive physical cost')
                pairs.append(dict(repeat=repeat,score=score(m[R81]['cost'],m['Naive']['cost']),
                    cost_multiplier=m['Naive']['cost']/m[R81]['cost'],physical_multiplier=m['Naive']['physical']/m[R81]['physical'],methods=m))
            row=dict(case_id=c['case_id'],family=c['family'],temporal=c['temporal'],phase=c['phase'],repeats=pairs)
            for k in ['score','cost_multiplier','physical_multiplier']: row[k]=sum(x[k] for x in pairs)/3
            row['methods']={name:{k:sum(x['methods'][name][k] for x in pairs)/3 for k in ['cost','reconstructed_cost','physical','IO','hit','miss','D']} for name in ['Naive',R81]}
            row['regression_repeats']=[x['repeat'] for x in pairs if x['methods'][R81]['cost']>x['methods']['Naive']['cost']]
            cases.append(row)
        result.update(official_score=sum(c['score'] for c in cases)/10,cases=cases,
            distributions={k:distribution([c[k] for c in cases]) for k in ['score','cost_multiplier','physical_multiplier']},
            method_distributions={name:{k:distribution([c['methods'][name][k] for c in cases]) for k in ['cost','physical','IO','miss','D']} for name in ['Naive',R81]},
            regression_cases=[c['case_id'] for c in cases if c['regression_repeats']],
            mean_cost_regression_cases=[c['case_id'] for c in cases if c['methods'][R81]['cost']>c['methods']['Naive']['cost']],
            worst_score=min(c['score'] for c in cases),worst_cost_multiplier=min(c['cost_multiplier'] for c in cases),
            nondeterministic=nondeterministic,
            note='Simulated IO and miss penalty plus measured decision time D; not real disk/end-to-end performance.')
        if nondeterministic:
            result.update(status='NONDETERMINISTIC_NO_OFFICIAL_SCORE',official_score=None)
    save(O/'summary.json',result)
    print(json.dumps(dict(event='SUMMARY',status=result['status'],score=result['official_score'])),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('phase',choices=['contract','selftest','prepare','run','summarize']); args=ap.parse_args()
    globals()[args.phase]()
