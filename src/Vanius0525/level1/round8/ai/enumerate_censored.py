"""Exhaustive finite IID observation-likelihood check, no policy optimization."""
import itertools,json,math,sys
from collections import defaultdict
from make_policy import HERE,ROOT,put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock

def transcript(seq,period,prefetch,prob):
    # Analytical toy: three equal objects, capacity two, all PROBE. Initial
    # periodic callback exposes request 1 and can prefetch it. Final callback
    # exists because the six-request horizon is divisible by B.
    cache={0};hits=misses=0;oldq=oldh=0;oldcache=set(cache);pending=None
    exact={};anonymous=[];trace=[];known_hits=0
    def expose(q,i):
        if q in exact:assert exact[q]==i
        else:exact[q]=i
    def callback(tag,q,current=None):
        nonlocal oldq,oldh,oldcache,pending,known_hits
        assert cache==oldcache
        nxt=seq[q] if q<len(seq) else None
        known_hit=pending is not None and pending[0]>oldq and pending[0]<=q and pending[1] in oldcache
        h=hits-oldh-int(known_hit);assert h>=0
        if h:anonymous.append((tuple(sorted(oldcache)),h))
        known_hits+=int(known_hit)
        if current is not None:expose(q,current)
        if nxt is not None:expose(q+1,nxt)
        before=tuple(sorted(cache))
        target=current if tag=='M' else (nxt if prefetch else None)
        actions=[]
        if target is not None and target not in cache:
            if len(cache)==2:
                candidates=sorted(cache-{nxt}) or sorted(cache)
                victim=candidates[0];cache.remove(victim);actions.append(('S',victim))
            cache.add(target);actions.append(('L',target))
        trace.append((tag,q,hits,misses,current,nxt,before,tuple(actions)))
        oldq=q;oldh=hits;oldcache=set(cache);pending=(q+1,nxt) if nxt is not None else None
    callback('P',0)
    for q,i in enumerate(seq,1):
        if i in cache:hits+=1
        else:misses+=1;callback('M',q,i)
        if q%period==0:callback('P',q)
    assert oldq==len(seq) and len(exact)+sum(h for _,h in anonymous)==len(seq)
    likelihood=math.prod(prob[i] for i in exact.values())
    for members,h in anonymous:likelihood*=sum(prob[i] for i in members)**h
    # Explicitly demonstrate the incorrect count that treats exposed next-Hit
    # as another anonymous Hit. Its likelihood need not normalize.
    naive=likelihood
    # Reconstruct the redundant likelihood factors on the genuine known-hit
    # intervals from trace; the resident set is before current actions.
    last_hit=0;last_q=0;last_next=None;last_after={0}
    for tag,q,hh,mm,current,nxt,before,actions in trace:
        if last_next is not None and q>last_q and last_next in last_after:
            naive*=sum(prob[i] for i in last_after)
        last_after=set(before)
        for a,i in actions:
            if a=='S':last_after.remove(i)
            else:last_after.add(i)
        last_hit=hh;last_q=q;last_next=nxt
    return tuple(trace),likelihood,naive,known_hits

def main():
    prob=[.2,.3,.5];results=[]
    with experiment_lock():
        for period in [2,3]:
            for prefetch in [False,True]:
                masses=defaultdict(float);derived={};naive={};known=0
                for seq in itertools.product(range(3),repeat=6):
                    key,likelihood,bad,count=transcript(seq,period,prefetch,prob)
                    masses[key]+=math.prod(prob[i] for i in seq)
                    if key in derived:assert abs(derived[key]-likelihood)<1e-14
                    derived[key]=likelihood;naive[key]=bad;known+=count
                error=max(abs(masses[k]-derived[k]) for k in masses)
                assert error<1e-13 and abs(sum(derived.values())-1)<1e-12
                assert abs(sum(naive.values())-1)>.01
                results.append({'period':period,'next_dependent_prefetch':prefetch,'enumerated_sequences':729,'distinct_observation_traces':len(masses),
                                'maximum_probability_error':error,'derived_total_probability':sum(derived.values()),
                                'naive_double_count_total_probability':sum(naive.values()),'known_next_hit_events_across_sequences':known})
    out={'all_passed':True,'probabilities':prob,'cases':results,
         'scope':'Analytical finite toy with all-PROBE equal objects. No performance result or general proof; IID only. Exhaustive hidden-path sum includes adaptive actions depending on already exposed next.'}
    put(HERE/'CENSORED_ENUMERATION_RESULTS.json',json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
