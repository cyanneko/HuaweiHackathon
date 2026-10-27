"""Human-readable deterministic counterexamples. These are regression tests, not holdout data."""
import json, subprocess
from retest import ROOT, MIB, dump, write_case, invoke, POLICIES

def chunks(pid,size):
    ops=[]
    while size:
        n=min(size,MIB);ops.append(('INSERT',0,pid,n));size-=n
    return ops

def main():
    run=ROOT/(ROOT/'current_run.txt').read_text('ascii').strip();m=64*MIB
    # At overflow, legacy compares a large cover with smaller single covers.
    # Equal-size tie picks partition 2. SWITCH hides the first Probe from next_op.
    build=chunks(0,32*MIB)+chunks(1,16*MIB)+chunks(2,16*MIB)+[('INSERT',0,3,1),('SWITCH',0)]
    specs=[('cold_large_hot_medium',(1,4,m,10000,1,1,10000),build+[('PROBE',0,2)]*4),
           ('hot_large_cold_medium',(1,4,m,10000,1,1,10000),build+[('PROBE',0,0)]*4)]
    # Slow writes: hard next-target protection can evict 63MiB instead of paying
    # two 1MiB writes and two cheap reads. The literal future A,B is known.
    build2=chunks(2,MIB)+chunks(1,MIB)+chunks(0,63*MIB)+[('SWITCH',0)]
    specs.append(('paid_next_protection',(1,4,m,1,10000,1,10000),build2+[('PROBE',0,2),('PROBE',0,1)]))
    # Two consecutive misses can fit together. Last LOAD remains the current target.
    build3=chunks(0,24*MIB)+chunks(1,24*MIB)+chunks(2,32*MIB)+chunks(3,32*MIB)+[('SWITCH',0)]
    specs.append(('adjacent_pair',(1,4,m,10000,10000,1000,10000),build3+[('PROBE',0,0),('PROBE',0,1)]))
    rows=[];results=[]
    for name,params,ops in specs:
        row=write_case(run,'targeted_'+name,params,ops,split='targeted',family=name,expected='feasible')
        rows.append(row);results.extend(invoke(run,row))
        for policy in ['naive','legacy','aggressive','prefix']:
            trace=run/'results'/f'{row["id"]}_{policy}_actions.csv'
            proc=subprocess.run([str(ROOT/'runner.exe'),str(run/row['file']),policy,'strict',str(trace)],capture_output=True,text=True)
            assert proc.returncode==0 and json.loads(proc.stdout)['ok']
    dump(run/'targeted_manifest.json',rows);dump(run/'results'/'targeted_results.json',results)
    lookup={(r['case'],r['policy']):r for r in results}
    for row in rows:
        a=lookup[row['id'],'naive']['score']
        print(row['id'],json.dumps({p:dict(score=lookup[row['id'],p]['score'],ratio=lookup[row['id'],p]['score']/a) for p in POLICIES if p in ['legacy','v2','protect','aggressive','prefix']},indent=2),flush=True)
    # Store the previously discovered 8317x case and its repaired replay explicitly.
    previous=ROOT/'run_20261018_183316_5cf96e'
    old=json.loads((previous/'manifest.json').read_text('utf8'))
    counter=next(r for r in old if r['id']=='extreme_057')
    counter['file']=str((previous/counter['file']).resolve())
    replay=invoke(run,counter,['naive','legacy','prefix'])
    dump(run/'results'/'previous_8317x_replay.json',dict(input=counter,results=replay))

if __name__=='__main__':main()
