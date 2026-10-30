# Derived by make_return_risk_deploy_v1.py; original scale audit retained.
# Generated solely by make_return_risk_scale_v1.py; original three-model checks retained.
"""Independent input/TRACE reconstruction, NumPy risk statistics, no solver."""
import io
import json
import math
import numpy as np
from return_risk_scale_metrics_v1 import ScaleAttribution


def close(a, b, where=''):
    assert np.allclose(a, b, rtol=2e-9, atol=2e-8), (where, np.max(np.abs(np.asarray(a)-np.asarray(b))))


def audit_deploy(path, stderr, final):
    attribution=ScaleAttribution()
    numeric={"global_pairs":0,"global_abs_error_max":0.,"global_scaled_error_max":0.}
    lines = iter(io.StringIO(stderr)); tail = []
    def callback_record():
        pairs, snapshots = [], []
        global_row=None
        for line in lines:
            if line.startswith('RR_GLOBAL '): global_row=json.loads(line[10:])
            elif line.startswith('RR_PAIR '):
                row=json.loads(line[8:]);assert global_row is not None;row['deploy_global']=global_row;pairs.append(row);global_row=None
            elif line.startswith('RR_SNAPSHOT '): snapshots.append(json.loads(line[12:]))
            elif line.startswith('TRACE '):
                x=line.split(); acts=[(x[6+3*j],int(x[7+3*j]),int(x[8+3*j])) for j in range(int(x[5]))]
                return x[1],acts,pairs,snapshots
        raise AssertionError('missing callback')
    with path.open() as stream:
        k,p,m,w,r,penalty=map(int,next(stream).split()); count,b=map(int,next(stream).split())
        for _ in range(k): next(stream)
        n=k*p; group=np.arange(n)//p
        sizes=np.zeros(n,dtype=np.int64);resident=np.ones(n,dtype=bool);phase=[False]*k
        d=np.zeros(n);z=np.zeros(n);mass=np.zeros(n);total=squares=0.;decay_q=-1;sample_q=-1
        op_d=np.zeros(n,dtype=bool);own=np.zeros(n,dtype=bool);born=np.full(n,-1,dtype=np.int64);disk_start=np.zeros(n,dtype=np.int64)
        loss=np.zeros((4,k,7)); fields=['event','nonevent','events','nonevents','event_inf','nonevent_inf','clipped_trials']
        real=[dict.fromkeys(['starts','initial','demand','known_demand','unknown_demand','prefetch','prefetch_confirmed','other_load','own_returns','own_wait_sum','own_wait_max','disk_exposure_closed','spill_bytes','read_bytes'],0) for _ in range(k)]
        names=['callbacks','epochs','mixed','intervals','known_positions','unknown_positions','known_hits','known_misses','duplicates','unknown_events','unknown_trials','fast_intervals','pressure','pairs','pool_changed','flat_changed','base_alt','pool_alt','flat_alt']
        counters=dict.fromkeys(names,0);lastq=lasth=lastm=statq=0;live=liveq=-1;pending=-1;pendingborn=-1;pendingown=False
        initialized=False;committed=False;hits=misses=counter=used=0;loga=math.log(.5)/2048;snaps=pair_count=0
        sum_h_min=float('inf');sum_h_max=0.
        def probs(): return (mass+64/n)/(total+64)
        def advance(q):
            nonlocal statq,d,z
            assert q>=statq
            scale=math.exp(loga*(q-statq));d*=scale;z*=scale;statq=q
        def pred(base):
            gd=np.bincount(group,weights=d,minlength=k);gz=np.bincount(group,weights=z,minlength=k)
            rg=(1+np.maximum(0,gd[group]-d))/(1+np.maximum(0,gz[group]-z))
            g_all=(1+float(d.sum()))/(1+float(z.sum()))
            return np.stack((base,np.minimum(1,base*(rg+d)/(1+z)),np.minimum(1,base*(1+d)/(1+z)),np.minimum(1,base*g_all)))
        def close_disk(i,q):
            assert op_d[i];real[i//p]['disk_exposure_closed']+=int(q-disk_start[i]);op_d[i]=False
        def complete(i,q):
            if own[i]:
                x=real[i//p];wait=int(q-born[i]);x['own_returns']+=1;x['own_wait_sum']+=wait;x['own_wait_max']=max(x['own_wait_max'],wait)
        def snapshot(row):
            nonlocal snaps
            assert row['cb']==counters['callbacks'] and row['q']==lastq
            advance(lastq);close(row['d'],d,'D');close(row['z'],z,'Z');close(row['p'],probs(),'p');snaps+=1
        def callback(tag,current,pending_op):
            nonlocal lastq,lasth,lastm,statq,live,liveq,pending,pendingborn,pendingown,initialized,committed,hits,misses,used,d,z,mass,total,squares,decay_q,sample_q,pair_count,sum_h_min,sum_h_max
            counters['callbacks']+=1;cb=counters['callbacks'];got,actions,pairs,snapshots=callback_record();assert got==tag
            q=hits+misses;all_probe=all(phase);known=False;kid=kq=-1
            if not all_probe:
                counters['mixed']+=1;initialized=committed=False
            else:
                if not initialized:
                    counters['epochs']+=1;initialized=True;committed=False;d[:]=z[:]=0;op_d[:]=own[:]=False;born[:]=-1;live=liveq=pending=-1;statq=q
                    for i in np.flatnonzero(~resident):op_d[i]=True;disk_start[i]=q;real[i//p]['initial']+=1
                if committed:
                    L=q-lastq;known=live>=0 and lastq<liveq<=q;kid,kq=live,liveq
                    assert L>=0 and misses-lastm==int(tag=='M') and hits>=lasth
                    if known:
                        counters['known_positions']+=1
                        if resident[kid]:counters['known_hits']+=1
                        else:counters['known_misses']+=1;assert tag=='M' and q==kq and current==kid
                        if pending>=0:
                            assert pending==kid;x=real[pending//p];x['prefetch_confirmed']+=1
                            if pendingown:
                                wait=kq-pendingborn;x['own_returns']+=1;x['own_wait_sum']+=wait;x['own_wait_max']=max(x['own_wait_max'],wait)
                            pending=-1
                    U=L-int(known);event=tag=='M' and not(known and kq==q);assert U>=0
                    if L:counters['intervals']+=1;counters['unknown_positions']+=U
                    if U:
                        advance(lastq);base=probs();hs=pred(base);disk=np.flatnonzero(~resident);is_event=disk==current if event else np.zeros(len(disk),dtype=bool)
                        attribution.forecast((1+float(d.sum()))/(1+float(z.sum())),U,disk,hs)
                        for model in range(4):
                            hh=hs[model,disk];nn=U-is_event.astype(int);g=group[disk]
                            finite=hh<1
                            vals=np.zeros(len(disk));vals[finite]=-nn[finite]*np.log1p(-hh[finite])
                            loss[model,:,1]+=np.bincount(g,weights=vals,minlength=k)
                            loss[model,:,3]+=np.bincount(g,weights=nn,minlength=k)
                            loss[model,:,5]+=np.bincount(g,weights=nn*(~finite),minlength=k)
                            loss[model,:,6]+=np.bincount(g,weights=U*(~finite),minlength=k)
                            if event:
                                i=current;h=hs[model,i];loss[model,i//p,2]+=1
                                if h==0:loss[model,i//p,4]+=1
                                else:loss[model,i//p,0]-=math.log(h)
                        # Independent vectorized integration; explicitly summed for short intervals.
                        if L<=32:weight=sum(math.exp(loga*(q-u)) for u in range(lastq+1,q+1) if not(known and u==kq))
                        else:weight=math.expm1(loga*L)/math.expm1(loga)-(math.exp(loga*(q-kq)) if known else 0)
                        advance(q);z[disk]+=base[disk]*weight
                        counters['unknown_trials']+=len(disk)*U
                        if event:assert not resident[current];d[current]+=1;counters['unknown_events']+=1
                    else:
                        if L:counters['fast_intervals']+=1
                        assert not event
                    if known:live=liveq=-1
                if tag=='M':
                    assert not resident[current] and op_d[current];x=real[current//p];x['demand']+=1
                    x['known_demand' if known and kq==q else 'unknown_demand']+=1;complete(current,q);close_disk(current,q)
                    if sizes[current]>m-used:counters['pressure']+=1
                nxt=pending_op[1]*p+pending_op[2]%p if pending_op[0]=='PROBE' else -1
                if nxt>=0:
                    if live>=0:assert live==nxt and liveq==q+1;counters['duplicates']+=1
                    else:live,liveq=nxt,q+1
                else:assert live<0
                lastq,lasth,lastm=q,hits,misses
            # Inner paired sampling happens AFTER observer.before, including mixed-phase callbacks.
            if tag in ('M','P') and pending_op[0]=='PROBE':
                nq=q+1;ni=pending_op[1]*p+pending_op[2]%p
                if decay_q<0:decay_q=nq
                if nq-decay_q>=256:
                    scale=2**(-(nq-decay_q)/2048);mass*=scale;total*=scale;squares*=scale*scale;decay_q=nq
                if nq!=sample_q:mass[ni]+=1;total+=1;squares+=1;sample_q=nq
            assert len(pairs)<=1
            for row in pairs:
                assert all_probe and row['cb']==cb and row['q']==q
                advance(q);base=probs();hs=pred(base);sgn=np.zeros(n)
                for i,sign in row['sign']:sgn[i]=sign;assert resident[i]
                coef=sgn*(sizes/r+sizes/w+100);mean=float(np.dot(base,coef));effective=total*total/squares if squares else 0
                risk=128*math.sqrt(max(0,float(np.dot(base,coef*coef))-mean*mean)/(effective+1))
                I=float(np.dot(sgn,sizes/w))
                if pending_op[0]=='PROBE':
                    ni=pending_op[1]*p+pending_op[2]%p;I+=sgn[ni]*(sizes[ni]/r+100)
                fs=[64*float(np.dot(h,coef)) for h in hs];choose=[int(I+f+risk<0) for f in fs]
                close(row['I'],I,'I');close(row['risk'],risk,'risk');close(row['F'],fs[:3],'F');assert row['choose']==choose[:3]
                gg=row['deploy_global'];assert gg['cb']==cb and gg['q']==q
                close(gg['F'],fs[3],'C++ global future');assert gg['choose']==choose[3]
                numeric['global_pairs']+=1
                numeric['global_abs_error_max']=max(numeric['global_abs_error_max'],abs(gg['F']-fs[3]))
                numeric['global_scaled_error_max']=max(numeric['global_scaled_error_max'],abs(gg['F']-fs[3])/max(1.,abs(fs[3])))
                selected={op*p+pid for typ,op,pid in actions if typ=='S'}
                positive=set(np.flatnonzero(sgn>0));negative=set(np.flatnonzero(sgn<0))
                if choose[0]:dyn=selected;hist=(dyn-positive)|negative
                else:hist=selected;dyn=(hist-negative)|positive
                assert positive==dyn-hist and negative==hist-dyn
                freed=[sum(int(sizes[i]) for i in hist),sum(int(sizes[i]) for i in dyn)];assert row['freed']==freed
                close(row['write_delta'],(freed[1]-freed[0])/w,'write_delta')
                target=current if tag=='M' else pending_op[1]*p+pending_op[2]%p
                need=max(0,int(sizes[target])-(m-used))
                attribution.pair((1+float(d.sum()))/(1+float(z.sum())),choose,freed,[len(hist),len(dyn)],need,w)
                counters['pairs']+=1;counters['base_alt']+=choose[0];counters['pool_alt']+=choose[1];counters['flat_alt']+=choose[2]
                counters['pool_changed']+=choose[1]!=choose[0];counters['flat_changed']+=choose[2]!=choose[0];pair_count+=1
                totalh=float(hs[1].sum());sum_h_min=min(sum_h_min,totalh);sum_h_max=max(sum_h_max,totalh)
            for typ,op,pid in actions:
                i=op*p+pid
                if typ=='S':
                    assert resident[i];resident[i]=False;used-=int(sizes[i])
                    if all_probe:assert not op_d[i];op_d[i]=own[i]=True;born[i]=disk_start[i]=q;real[op]['starts']+=1;real[op]['spill_bytes']+=int(sizes[i])
                else:
                    assert not resident[i];resident[i]=True;used+=int(sizes[i])
                    if all_probe:
                        real[op]['read_bytes']+=int(sizes[i])
                        if tag=='M' and i==current:assert not op_d[i]
                        elif i==live:
                            assert pending<0;real[op]['prefetch']+=1;pending,pendingborn,pendingown=i,int(born[i]),bool(own[i]);close_disk(i,q)
                        else:real[op]['other_load']+=1;close_disk(i,q)
                assert 0<=used<=m
            if all_probe:committed=True
            for row in snapshots:snapshot(row)
        def parse(line):
            x=line.split();return (x[0],)+tuple(map(int,x[1:])) if x else ('',-1,0)
        current_line=next(stream,'');operation_count=0
        while current_line:
            next_line=next(stream,'');op=parse(current_line);following=parse(next_line);operation_count+=1
            typ,oid=op[:2]
            if typ=='SWITCH':phase[oid]=True
            else:
                i=oid*p+op[2]%p
                if typ=='INSERT':
                    if resident[i]:
                        if used+op[3]>m:callback('O',i,following)
                        used+=op[3]
                    sizes[i]+=op[3]
                else:
                    if resident[i]:hits+=1
                    else:misses+=1;callback('M',i,following)
                counter+=1
                if counter%b==0:callback('P',-1,following)
            current_line=next_line
        assert operation_count==count
    for line in lines:
        if line.startswith('RR_SNAPSHOT '):snapshot(json.loads(line[12:]))
        elif line.startswith('RR_STATS '):assert json.loads(line[9:])==final
        else:assert not line.startswith(('TRACE ','RR_PAIR '))
    for name,value in counters.items():assert final[name]==value,(name,final[name],value)
    assert final['q']==lastq and final['pending']==pending
    assert final['pairs']<=final['checks']<=final['pressure']
    if pair_count:close(final['sum_h_min'],sum_h_min);close(final['sum_h_max'],sum_h_max)
    for model in range(3):
        for op in range(k):
            for j,key in enumerate(fields):
                if j<2:close(final['loss'][model][op][key],loss[model,op,j],key)
                else:assert final['loss'][model][op][key]==int(loss[model,op,j]),key
    for op in range(k):
        ids=np.arange(op*p,(op+1)*p);open_ids=ids[op_d[ids]];own_ids=ids[op_d[ids]&own[ids]]
        real[op].update(disk_exposure_open=int(np.sum(lastq-disk_start[open_ids])),own_censored_count=len(own_ids),own_censored_age=int(np.sum(lastq-born[own_ids])))
        assert real[op]==final['real'][op],(op,real[op],final['real'][op])
    return {'deploy_numeric':numeric,'scale_attribution':attribution.export(loss,fields),'all_observer_counters_match':True,'all_real_episode_ledgers_match':True,'all_sequential_losses_match':True,'all_pair_comparisons_match':True,'pair_comparisons':pair_count,'numeric_snapshots':snaps,'probes':hits+misses,'unobserved_tail_probes':hits+misses-lastq,'unknown_trials':counters['unknown_trials'],'unknown_returns':counters['unknown_events'],'b1_all_known':b==1 and counters['unknown_trials']==0,'full_reference_actions_unchanged':True}
