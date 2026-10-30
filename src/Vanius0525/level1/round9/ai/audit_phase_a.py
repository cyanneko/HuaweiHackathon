"""Independent request-identity/pressure ledger, no policy decisions or labels."""
import hashlib,json,math
from collections import Counter
MASK=(1<<64)-1
def mix(z):
    z=(z+0x9e3779b97f4a7c15)&MASK;z=((z^(z>>30))*0xbf58476d1ce4e5b9)&MASK;z=((z^(z>>27))*0x94d049bb133111eb)&MASK
    return z^(z>>31)
def key(seed,q,diff):return mix(seed^q^(0xd1ff3e5a7b9c2046 if diff else 0xa110ca7e5319bdf2))
def bucket(q):return 0 if q<1024 else 1 if q<16384 else 2 if q<262144 else 3
def trace_digest(path):
    h=hashlib.sha256();count=0
    with path.open('rb') as f:
        for line in f:
            if line.startswith(b'TRACE '):h.update(line);count+=1
    return {'sha256':h.hexdigest(),'callbacks':count}
def lines(path,prefix):
    with path.open() as f:
        for line in f:
            if line.startswith(prefix):yield line
def close(x,y):assert math.isclose(x,y,rel_tol=2e-10,abs_tol=2e-8),(x,y)

def audit(path,stderr,seed):
    samples=[];summary=None;size_line=None
    for line in lines(stderr,'PA_'):
        if line.startswith('PA_SAMPLE '):samples.append(json.loads(line[len('PA_SAMPLE '):]))
        elif line.startswith('PA_SUMMARY '):assert summary is None;summary=json.loads(line[len('PA_SUMMARY '):])
        elif line.startswith('PA_SIZES '):assert size_line is None;size_line=list(map(int,line.split()[1:]))
    assert summary is not None
    sample_by_q={}
    for s in samples:sample_by_q.setdefault(s['q'],[]).append(s)
    traces=iter(lines(stderr,'TRACE '));gates=iter(lines(stderr,'PA_GATE '));pressure=[0]*4;eligible=[0]*4;different=[0]*4;chosen=[0]*4
    margins=[[] for _ in range(4)];reservoirs={(j,d):[] for j in range(4) for d in (False,True)}
    with path.open() as f:
        k,p,m,w,r,penalty=map(int,f.readline().split());n,b=map(int,f.readline().split())
        for _ in range(k):f.readline()
        size=[0]*(k*p);mem=[True]*(k*p);phase=[False]*k;used=0;q=hits=misses=counter=callback_count=0
        start=None;exact=anonymous=known_hit=prefetch_hit=0;bits=[0]*8;op_exact=[0]*8
        last_q=last_exact=last_anon=0;last_cov=None;pending={};sample_count=[0.]*(k*p);mass=squares=0.;sample_q=decay_q=-1;sample_sources=0
        sampled_positions={};matched_samples=0
        def op_parse(line):
            if not line:return None
            t=line.split();o=int(t[1]);return (t[0],o,int(t[2])%p if len(t)>2 else -1,int(t[3]) if len(t)>3 else 0)
        current=op_parse(f.readline());next_op=op_parse(f.readline())
        def callback(tag,op=-1,pid=-1,z=0,raw_index=-1):
            nonlocal start,last_q,last_exact,last_anon,last_cov,sample_q,decay_q,sample_sources,mass,squares,used,callback_count,matched_samples
            t=next(traces).split();assert t[:2]==['TRACE',tag];assert list(map(int,t[2:5]))==[op,pid,z]
            count=int(t[5]);assert len(t)==6+3*count;actions=[[t[6+3*j],int(t[7+3*j]),int(t[8+3*j])] for j in range(count)]
            all_probe=all(phase);next_id=next_op[1]*p+next_op[2] if next_op and next_op[0]=='PROBE' else -1
            if tag in ('M','P') and next_id>=0:
                sq=q+1;source=1 if tag=='P' else 2
                if decay_q<0:decay_q=sq
                if sq-decay_q>=256:
                    decay=math.pow(.5,(sq-decay_q)/2048.);sample_count[:]=[x*decay for x in sample_count];mass*=decay;squares*=decay*decay;decay_q=sq
                if sq!=sample_q:sample_q=sq;sample_sources=0
                if not sample_sources&source:
                    if not sample_sources:sample_count[next_id]+=1;mass+=1;squares+=1
                    sample_sources|=source
            cov=None
            if all_probe:
                if start is None:
                    start=q;last_q=q;last_exact=exact;last_anon=anonymous
                    assert size_line==[k,p]+size
                cov={'start_q':start,'last_q':q,'span':q-start,'exact':exact,'anonymous':anonymous,'known_hit':known_hit,
                     'periodic_prefetch_hit':prefetch_hit,'last_dq':q-last_q,'last_exact':exact-last_exact,'last_anonymous':anonymous-last_anon,
                     'source_bits':bits.copy(),'op_exact':op_exact.copy()}
                assert exact+anonymous==q-start
                last_cov=cov
                last_q=q;last_exact=exact;last_anon=anonymous
                if next_id>=0:
                    if q+1 not in pending:pending[q+1]=[next_id,0,False]
                    assert pending[q+1][0]==next_id;pending[q+1][1]|=1 if tag=='P' else 2
            if tag=='M' and all_probe and size[op*p+pid]>m-used:
                gt=next(gates).split();gq,j,e,d,c,reason=map(int,gt[1:7]);margin=float(gt[7]);assert gq==q and j==bucket(q)
                pressure[j]+=1;eligible[j]+=e;different[j]+=d;chosen[j]+=c
                assert not d or e;assert not c or d
                if d:assert bool(c)==(margin<0);margins[j].append(margin)
                for dd in (False,True):
                    if dd and not d:continue
                    slot=reservoirs[j,dd];slot.append((key(seed,q,dd),q));slot.sort();del slot[4 if dd else 2:]
                for s in sample_by_q.get(q,[]):
                    matched_samples+=1;assert s['coverage']==cov;assert s['callback_index']==callback_count
                    assert [s['memory'],s['used'],s['target_size'],s['op'],s['pid'],s['next_id']]==[m,used,size[op*p+pid],op,pid,next_id]
                    assert [s['eligible'],s['different'],s['chosen_dynamic'],s['reason']]==[e,d,c,reason]
                    assert s['actual']==actions and actions[-1]==['L',op,pid]
                    assert s['key']==key(seed,q,s['kind']=='different') and s['stratum']==j
                    hist=s['history'];dyn=s['dynamic'];need=size[op*p+pid]-(m-used)
                    for proposal in (hist,dyn):
                        if not e:assert not proposal;continue
                        ids=[]
                        for a,o,pa in proposal:assert a=='S' and mem[o*p+pa] and size[o*p+pa]>0 and (o,pa)!=(op,pid);ids.append(o*p+pa)
                        assert len(set(ids))==len(ids) and sum(size[i] for i in ids)>=need
                    if e:
                        assert set(tuple(a) for a in hist)!=set(tuple(a) for a in dyn) if d else set(tuple(a) for a in hist)==set(tuple(a) for a in dyn)
                        assert actions==(dyn if c else hist)+[['L',op,pid]]
                        sg=Counter()
                        for _,o,pa in hist:sg[o*p+pa]-=1
                        for _,o,pa in dyn:sg[o*p+pa]+=1
                        immediate=mu=second=0.
                        for i in sorted(sg):
                            sign=sg[i]
                            if not sign:continue
                            coeff=sign*(size[i]/r+size[i]/w+100)
                            immediate+=sign*size[i]/w
                            if i==next_id:immediate+=sign*(size[i]/r+100)
                            prob=(sample_count[i]+64/(k*p))/(mass+64);mu+=prob*coeff;second+=prob*coeff*coeff
                        for i,prob in s['probabilities']:close(prob,(sample_count[i]+64/(k*p))/(mass+64))
                        if d:
                            neff=mass*mass/squares if squares else 0.;sd=64*math.sqrt(max(0.,second-mu*mu)/(neff+1))
                            for field,value in [('immediate',immediate),('mean',mu),('sd',sd),('effective',neff),('margin',immediate+64*mu+2*sd)]:close(s[field],value)
                    sampled_positions[str(q)]=raw_index
            for a,o,pa in actions:
                i=o*p+pa
                if a=='S':assert mem[i];mem[i]=False;used-=size[i]
                else:
                    assert not mem[i];mem[i]=True;used+=size[i]
                    if all_probe and tag=='P' and q+1 in pending and pending[q+1][0]==i:pending[q+1][2]=True
                assert 0<=used<=m
            callback_count+=1
        index=0
        while current is not None:
            typ,o,pid,z=current;i=o*p+pid
            if typ=='SWITCH':phase[o]=True
            else:
                if typ=='INSERT':
                    if mem[i]:
                        if used+z>m:callback('O',o,pid,z,index)
                        used+=z
                    size[i]+=z
                else:
                    q+=1;hit=mem[i]
                    if hit:hits+=1
                    else:misses+=1
                    if start is not None:
                        known=pending.pop(q,None)
                        if known is not None:
                            ident,source,prefetched=known;assert ident==i;source|=0 if hit else 4;exact+=1;bits[source]+=1;op_exact[o]+=1;known_hit+=hit;prefetch_hit+=hit and prefetched
                        elif not hit:exact+=1;bits[4]+=1;op_exact[o]+=1
                        else:anonymous+=1
                    if not hit:callback('M',o,pid,0,index)
                counter+=1
                if counter%b==0:callback('P',raw_index=index)
            index+=1;current=next_op;next_op=op_parse(f.readline())
        assert index==n and next(traces,None) is None and next(gates,None) is None
        # Silent tail requests are audit-visible only; observer cannot add them.
        reported=summary['coverage'];assert summary['callbacks']==callback_count
        tail=q-reported['last_q'];assert tail>=0
        # Compare the exact last callback boundary; never add the silent tail.
        assert reported==last_cov,(reported,last_cov)
        assert reported['span']==reported['last_q']-reported['start_q'] and reported['exact']+reported['anonymous']==reported['span']
        assert matched_samples==len(samples)
        for j in range(4):
            got=summary['bins'][j];assert [got['pressure'],got['eligible'],got['different'],got['chosen_dynamic']]==[pressure[j],eligible[j],different[j],chosen[j]]
            assert got['negative_margin']==sum(x<0 for x in margins[j]) and got['nonnegative_margin']==sum(x>=0 for x in margins[j])
            close(got['margin_sum'],sum(margins[j]));close(got['margin_min'],min(margins[j],default=0));close(got['margin_max'],max(margins[j],default=0))
            for dd in (False,True):assert sorted((s['key'],s['q']) for s in samples if s['stratum']==j and (s['kind']=='different')==dd)==reservoirs[j,dd]
        return {'summary':summary,'samples':samples,'sample_raw_operation_indices':sampled_positions,'unobserved_tail_probes':tail,
                'independent_pressure_counts':pressure,'independent_sample_formula_checks':len(samples),'input_operations':n,
                'hits':hits,'misses':misses,'callback_count':callback_count,'coverage_not_per_operator_hit_rate':True}
