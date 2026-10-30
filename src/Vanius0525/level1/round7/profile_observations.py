"""Offline audit of sampling histograms; identities are never passed to scheduler."""
import collections,hashlib,json,statistics,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from round7.cost_replay import parse_input, replay
from round6.prepare import DATA,manifest,put
from workflow import experiment_lock

def histograms(path,stderr):
    params,ops=parse_input(path);k,p=params[:2];n=k*p
    true=[0]*n
    for x in ops:
        if x[0]=='PROBE':true[x[1]*p+x[2]]+=1
    traces=iter(x.split() for x in stderr.splitlines() if x.startswith('TRACE '))
    counts={s:[0]*n for s in ['periodic','after_miss','next_union','miss_target','visible_union']}
    seen=collections.defaultdict(set)
    def add(source,idx):
        if idx>=len(ops) or ops[idx][0]!='PROBE' or idx in seen[source]:return
        seen[source].add(idx);x=ops[idx];counts[source][x[1]*p+x[2]]+=1
    # Audit log is already legality checked in the primary run. Walk matching callbacks
    # in order; overflow/miss are at current operation, periodic is after it.
    pending=next(traces,None)
    # Reconstruct residency with exact logged actions to locate each callback.
    sizes=[[0]*p for _ in range(k)];mem=[[True]*p for _ in range(k)];used=counter=0
    def cb(tag,i):
        nonlocal pending,used
        assert pending is not None and pending[1]==tag
        if tag=='P':add('periodic',i+1)
        if tag=='M':add('after_miss',i+1);add('miss_target',i);add('visible_union',i)
        if tag in ['M','P']:add('next_union',i+1)
        add('visible_union',i+1)
        for j in range(int(pending[5])):
            typ,o,pa=pending[6+3*j:9+3*j];o=int(o);pa=int(pa)
            if typ=='S':mem[o][pa]=False;used-=sizes[o][pa]
            else:mem[o][pa]=True;used+=sizes[o][pa]
        pending=next(traces,None)
    for i,x in enumerate(ops):
        if x[0]=='SWITCH':continue
        o,pa=x[1:3]
        if x[0]=='INSERT':
            z=x[3]
            if mem[o][pa]:
                if used+z>params[2]:cb('O',i)
                used+=z
            sizes[o][pa]+=z
        elif not mem[o][pa]:cb('M',i)
        counter+=1
        if counter%params[7]==0:cb('P',i)
    assert pending is None
    total=sum(true)
    result={}
    for source,cs in counts.items():
        count=sum(cs)
        # TV: half L1 distance to full-stream empirical PROBE distribution.
        # It is a descriptive histogram discrepancy, not error to unknown true p.
        tv=.5*sum(abs((c+64/n)/(count+64)-t/max(1,total)) for c,t in zip(cs,true)) if total else None
        result[source]={'n':count,'smoothed_tv':tv}
    return result

def main():
    out=ROOT/'build/round7/observation_profile';out.mkdir(parents=True,exist_ok=True)
    rows=json.loads((ROOT/'round7/BEST_RESULTS.json').read_text())['rows'];index={Path(x['path']).name:x for x in manifest()['cases']}
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';before=hashlib.sha256(ledger.read_bytes()).hexdigest()
    results=[]
    with experiment_lock():
        exe=build(ROOT/'MySpillSchedulerBest.cpp','round7_profile',audit=True)
        for r in rows:
            record=index[r['file']];assert record['split']=='train'
            path=DATA/record['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==r['input_sha256']
            cache=out/(path.stem+'.json')
            if cache.exists():
                item=json.loads(cache.read_text())
                assert item['input_sha256']==r['input_sha256'] and item['independent_replay_matches_baseline']
            else:
                run=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=120)
                audit=replay(path,run.stderr,run.stdout)
                assert audit==r['audit']
                item={'file':path.name,'family':record['family'],'histograms':histograms(path,run.stderr),'input_sha256':r['input_sha256'],'independent_replay_matches_baseline':True}
                put(cache,(json.dumps(item,indent=2)+'\n').encode())
            results.append(item)
        assert before==hashlib.sha256(ledger.read_bytes()).hexdigest()
    summary={s:{'mean_smoothed_tv':statistics.mean(x['histograms'][s]['smoothed_tv'] for x in results if x['histograms'][s]['smoothed_tv'] is not None),'median_samples':statistics.median(x['histograms'][s]['n'] for x in results)} for s in results[0]['histograms']}
    put(ROOT/'round7/OBSERVATION_PROFILE.json',(json.dumps({'summary':summary,'rows':results,'limitations':'Full-stream empirical histogram; no true-p or causal guarantee. Baseline callback trajectory only. visible_union includes overflow next.','test_ledger_unchanged':True},indent=2)+'\n').encode())
    print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
