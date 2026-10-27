"""Three exact 5,000,000-line official-range inputs, streamed to disk.
Run serially to make timing comparisons interpretable. Parsing time is reported
separately from the scheduler/replay time. Large runs audit the full resident-byte
ledger every 4096 effective operations; bounds are checked after every action.
"""
import argparse, collections, hashlib, json, os, subprocess, time
from pathlib import Path
from retest import ROOT, MIB, dump

def generate(run,kind):
    n=5_000_000;k=8;p=64;q=k*p
    if kind=='maxN_growth_4GiB':
        build=n-k-q;probes=q;m=4096*MIB;b=10000;w=r=10000;penalty=1000
    else:
        build=q;probes=n-k-build;m=64*MIB;b=1 if kind=='maxN_maxQ_B1_hits' else 1000
        w=10000;r=10000 if kind=='maxN_maxQ_B1_hits' else 100;penalty=1000
    def probe_id(i):
        if kind=='maxN_growth_4GiB':return i
        if kind=='maxN_maxQ_B1_hits':return i%q
        phase=(i//250000)%4
        if phase==0:return i%q
        if phase==1:return (i*17)%32
        if phase==2:return ((i//8192)*31+i%4)%q
        return 0 if i%5<4 else (i*13)%q
    bc=[0]*k;pc=[0]*k
    for x in range(q):bc[x//p]=bc[x//p]+build//q+(x<build%q)
    for i in range(probes):pc[probe_id(i)//p]+=1
    target=run/'cases'/f'{kind}.txt'
    with target.open('w',encoding='ascii',newline='\n') as f:
        f.write(f'{k} {p} {m} {w} {r} {penalty}\n{n} {b}\n')
        for o in range(k):f.write(f'{o} {bc[o]} {pc[o]}\n')
        for i in range(build):
            x=i%q
            if kind=='maxN_growth_4GiB':size=32768 if x==0 else 1024
            elif kind=='maxN_maxQ_B1_hits':size=MIB if x==0 else 32768
            else:size=MIB if x==0 else 262144+x%3
            f.write(f'INSERT {x//p} {x%p} {size}\n')
        for o in range(k):f.write(f'SWITCH {o}\n')
        for i in range(probes):
            x=probe_id(i);f.write(f'PROBE {x//p} {x%p}\n')
    sha=hashlib.sha256()
    with target.open('rb') as f:
        while block:=f.read(1<<20):sha.update(block)
    return dict(id=kind,file=str(target.relative_to(run)),K=k,P=p,M=m,W=w,R=r,penalty=penalty,B=b,N=n,build=build,probes=probes,sha256=sha.hexdigest())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-run');args=ap.parse_args()
    run=ROOT/(ROOT/'current_run.txt').read_text('ascii').strip()
    kinds=['maxN_maxQ_B1_hits','maxN_mixed_maxQ','maxN_growth_4GiB']
    manifest_path=run/'scale_manifest.json'
    if args.source_run:
        source=ROOT/args.source_run
        rows=json.loads((source/'scale_manifest.json').read_text('utf8'))
        rows=[{**r,'file':os.path.relpath(source/r['file'],run)} for r in rows]
        dump(manifest_path,rows)
    elif manifest_path.exists():rows=json.loads(manifest_path.read_text('utf8'))
    else:
        rows=[]
        for kind in kinds:
            rows.append(generate(run,kind));print('generated',kind,flush=True)
        dump(manifest_path,rows)
    results=[]
    output=run/'results'/'scale_results.json'
    for row in rows:
        for policy in ['naive','legacy','v2','prefix']:
            start=time.perf_counter()
            proc=subprocess.run([str(ROOT/'runner.exe'),str(run/row['file']),policy,'fast'],capture_output=True,text=True,timeout=240)
            if proc.returncode:raise RuntimeError(proc.stderr)
            r=dict(case=row['id'],**json.loads(proc.stdout),process_wall_s=time.perf_counter()-start)
            assert r['ok'],r
            assert r['hit']+r['miss']==row['probes']
            results.append(r);dump(output,results)
            print(json.dumps(r),flush=True)
    dump(run/'results'/'scale_verification.json',dict(full_ledger_audit_interval=4096,capacity_check='after every effective action and operation',
        complete_inputs=True,N_each=5_000_000,serial_runs=True,run_ms_excludes_input_parse=True,results=results))

if __name__=='__main__':main()
