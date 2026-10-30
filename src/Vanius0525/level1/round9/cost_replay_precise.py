"""Independent byte ledger derived from replay.py; no engine instrumentation."""
from pathlib import Path

import math
from fractions import Fraction

def precision_check(costs, write, read, sequential, additions):
    # Integer byte ledgers give an exact rational cost. Sequential floating
    # divisions/additions in the official engine have a finite rounding error.
    exact = (Fraction(costs['build_spill_bytes'] + costs['build_append_bytes'] +
                      costs['probe_spill_bytes'], write) +
             Fraction(costs['probe_read_bytes'], read))
    expected = float(exact)
    # Round-to-nearest unit roundoff; one division per nonnegative I/O term,
    # followed by additions. gamma_(additions+2) is a conservative bound.
    unit = 2.0 ** -53
    scaled = (additions + 2) * unit
    assert scaled < 1 and math.isfinite(expected)
    gamma = scaled / (1.0 - scaled)
    bound = gamma * expected + 4 * math.ulp(expected)
    difference = sequential - expected
    assert abs(difference) <= bound, (difference, bound, additions, expected)
    return {'sequential_io_us': sequential, 'exact_io_us': expected,
            'sequential_minus_exact_us': difference, 'roundoff_bound_us': bound,
            'io_additions': additions, 'exact_io_fraction': str(exact)}


def parse_input(path):
    lines=Path(path).read_text().splitlines()
    k,p,m,w,r,penalty=map(int,lines[0].split());n,b=map(int,lines[1].split())
    assert 1<=k<=8 and 2<=p<=64 and 64*(1<<20)<=m<=4*(1<<30)
    assert 1<=w<=10000 and 1<=r<=10000 and 1<=penalty<=1000 and 1<=b<=10000
    heads=[tuple(map(int,x.split())) for x in lines[2:2+k]]
    assert [x[0] for x in heads]==list(range(k))
    ops=[];build=[0]*k;probe=[0]*k;switched=[False]*k;sizes=[[0]*p for _ in range(k)]
    for line in lines[2+k:]:
        v=line.split();typ=v[0];op=int(v[1]);assert 0<=op<k
        if typ=='SWITCH':
            assert len(v)==2 and not switched[op];switched[op]=True;ops.append((typ,op))
        else:
            key=int(v[2]);assert 0<=key<=10**9;pid=key%p
            if typ=='INSERT':
                assert len(v)==4 and not switched[op]
                z=int(v[3]);assert 1<=z<=1<<20;build[op]+=1;sizes[op][pid]+=z
                assert sizes[op][pid]<=m
                ops.append((typ,op,pid,z))
            else:
                assert typ=='PROBE' and len(v)==3 and switched[op]
                probe[op]+=1;ops.append((typ,op,pid))
    assert len(ops)==n<=5000000
    assert all((build[i],probe[i])==heads[i][1:] for i in range(k))
    return (k,p,m,w,r,penalty,n,b),ops

def parse_output(stdout):
    result={}
    for line in stdout.splitlines():
        if ':' in line:
            key,value=line.split(':',1);assert key not in result
            result[key]=float(value.strip())
    assert set(result)=={'Total_IO_Time','Total_Decision_Time','Total_Score','Hit_Count','Miss_Count'}
    return result

def replay(path, stderr, stdout):
    (k,p,m,w,r,penalty,n,b),ops=parse_input(path)
    traces=[]
    for line in stderr.splitlines():
        if not line.startswith('TRACE '):continue
        x=line.split();tag=x[1];o,pid,z,count=map(int,x[2:6]);a=[]
        assert len(x)==6+3*count
        for j in range(count):
            off=6+3*j;a.append((x[off],int(x[off+1]),int(x[off+2])))
        traces.append((tag,o,pid,z,a))
    costs={k:0 for k in ("build_spill_bytes","build_append_bytes","probe_spill_bytes","probe_read_bytes")}
    sizes=[[0]*p for _ in range(k)];mem=[[True]*p for _ in range(k)];phase=[False]*k
    used=0;io=0.;io_additions=0;hits=misses=counter=t=action_count=0
    build_by_op=[0]*k
    def callback(tag,op=-1,pid=-1,z=0):
        nonlocal t,used,io,action_count,io_additions
        assert t<len(traces), ('Missing callback',t,tag)
        got=traces[t];t+=1;assert got[:4]==(tag,op,pid,z),(got[:4],(tag,op,pid,z))
        actions=got[4]
        if tag=='M':assert actions and actions[-1]==('L',op,pid)
        seen=set()
        for typ,o,pa in actions:
            assert 0<=o<k and 0<=pa<p and typ in ('S','L')
            assert (typ,o,pa) not in seen;seen.add((typ,o,pa));action_count+=1
            size=sizes[o][pa]
            if typ=='S':
                assert mem[o][pa] and size>0
                assert tag!='O' or (o,pa)!=(op,pid), 'Protected INSERT target spilled'
                costs['probe_spill_bytes' if phase[o] else 'build_spill_bytes']+=size
                if not phase[o]:build_by_op[o]+=size
                used-=size;mem[o][pa]=False;io+=size/w;io_additions+=1
            else:
                assert tag!='O' and phase[o] and not mem[o][pa]
                costs['probe_read_bytes']+=size
                used+=size;assert used<=m;mem[o][pa]=True;io+=size/r;io_additions+=1
            assert 0<=used<=m
        if tag=='O':assert used+z<=m
        if tag=='M':assert mem[op][pid]
    for entry in ops:
        typ,o=entry[:2]
        if typ=='SWITCH':
            assert build_by_op[o]==sum(sizes[o][pa] for pa in range(p) if not mem[o][pa]), 'BUILD byte identity'
            phase[o]=True;continue
        pid=entry[2]
        if typ=='INSERT':
            z=entry[3]
            if mem[o][pid]:
                if used+z>m:callback('O',o,pid,z)
                used+=z
            else:
                costs['build_append_bytes']+=z
                build_by_op[o]+=z
                io+=z/w;io_additions+=1
            sizes[o][pid]+=z
        else:
            if mem[o][pid]:hits+=1
            else:misses+=1;callback('M',o,pid)
        assert used<=m
        counter+=1
        if counter%b==0:callback('P')
    assert t==len(traces)
    result=parse_output(stdout)
    assert abs(result['Total_IO_Time']-io)<.011,(result['Total_IO_Time'],io)
    assert result['Hit_Count']==hits and result['Miss_Count']==misses
    assert abs(result['Total_Score']-(result['Total_IO_Time']+penalty*misses+result['Total_Decision_Time']))<.021
    costs.update(build_write_us=(costs['build_spill_bytes']+costs['build_append_bytes'])/w,
                 probe_write_us=costs['probe_spill_bytes']/w,probe_read_us=costs['probe_read_bytes']/r,miss_us=penalty*misses)
    precision = precision_check(costs,w,r,io,io_additions)
    return {'precision':precision,'costs':costs,'callbacks':t,'actions':action_count,'hits':hits,'misses':misses,'io':io}
