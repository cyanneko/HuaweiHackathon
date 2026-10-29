"""Exact small-state offline oracle for the saved action rules (I/O + miss only).
Enumerates every feasible resident mask at callbacks, including legal preloads.
Exponential: test-only; never linked into a submission or used as online features.
"""
import argparse
import json
from pathlib import Path
from replay import parse_input


def optimal(path):
    (k,p,m,w,r,penalty,n,b),ops=parse_input(path)
    count=k*p
    assert count<=8, 'Exponential oracle intentionally restricted to <=8 partitions'
    all_mask=(1<<count)-1;sizes=[0]*count;phase=[False]*k;counter=0
    dp={all_mask:0.0}
    transitions=0
    for entry in ops:
        typ,op=entry[:2]
        if typ=='SWITCH':phase[op]=True;continue
        bit_id=op*p+entry[2];bit=1<<bit_id
        sums=[0]*(1<<count)
        for mask in range(1,1<<count):
            low=mask&-mask;i=low.bit_length()-1;sums[mask]=sums[mask^low]+sizes[i]
        zero=sum(1<<i for i,z in enumerate(sizes) if z==0)
        loadable=sum(1<<i for i in range(count) if phase[i//p])
        nd={}
        def put(mask,cost):
            if cost<nd.get(mask,float('inf')):nd[mask]=cost
        if typ=='INSERT':
            z=entry[3]
            for mask,cost in dp.items():
                if not mask&bit:put(mask,cost+z/w)
                elif sums[mask]+z<=m:put(mask,cost)
                else:
                    sub=mask
                    while True:
                        if sub&bit and sub&zero==zero and sums[sub]+z<=m:
                            put(sub,cost+(sums[mask]-sums[sub])/w);transitions+=1
                        if not sub:break
                        sub=(sub-1)&mask
            sizes[bit_id]+=z
        else:
            feasible=[mask for mask in range(1<<count) if mask&bit and mask&zero==zero and sums[mask]<=m]
            for mask,cost in dp.items():
                if mask&bit:put(mask,cost)
                else:
                    for dest in feasible:
                        added=dest&~mask
                        if added&~loadable:continue
                        val=cost+sums[mask&~dest]/w+sums[added]/r+penalty
                        put(dest,val);transitions+=1
        dp=nd;assert dp, ('Infeasible input',entry)
        counter+=1
        if counter%b==0:
            zero=sum(1<<i for i,z in enumerate(sizes) if z==0)
            sums=[0]*(1<<count)
            for mask in range(1,1<<count):
                low=mask&-mask;sums[mask]=sums[mask^low]+sizes[low.bit_length()-1]
            feasible=[mask for mask in range(1<<count) if mask&zero==zero and sums[mask]<=m]
            nd={}
            for mask,cost in dp.items():
                for dest in feasible:
                    added=dest&~mask
                    if added&~loadable:continue
                    put(dest,cost+sums[mask&~dest]/w+sums[added]/r);transitions+=1
            dp=nd
    return {'optimal_io_plus_miss':min(dp.values()),'final_states':len(dp),'transitions':transitions,
            'scope':'exact saved legal callbacks, full future, no decision time, <=8 partitions'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);a=p.parse_args();print(json.dumps(optimal(a.input),indent=2))
