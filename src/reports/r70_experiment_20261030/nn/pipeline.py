"""R70: causal 32-feature plans, exact-ledger complete suffix labels, tiny CPU fit.

OFFLINE label generation may inspect future; features() does not. No holdout labels.
All relative costs are fixed-continuation outcomes, not optimal Q values.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import sys
import time

ROOT = Path(__file__).resolve().parent
WS = ROOT.parents[1]
R66 = WS/'hashjoin_lab/reports/collaboration_20261020/round66_offline_oracle'
R67 = WS/'hashjoin_lab/reports/collaboration_20261020/round67_offline_quality'
R70 = WS/'hashjoin_lab/reports/collaboration_20261020/round70_offline_optimization'
sys.path[:0] = [str(R66), str(R67), str(R70)]
import core
from future_rollouts import FutureIndex, choose_spills, check_time, RolloutTimeout
from teacher_portfolio import Context

FEATURE_VERSION = 'r70-causal32-v2-sequential-sums'
FEATURE_NAMES = ['miss','free_M','need_M','deficit_M','resident_probe_M','visible_miss_fraction',
 'released_M','excess_M','count_squash','probe_released_M','next_probe_victim','max_size_M',
 'heat_bytes_squash','base_cost_squash','write_bandwidth_fraction','next_insert_victim',
 'min_size_M','mean_size_M','std_size_M','size_square_sum_M2','max_heat_squash',
 'mean_heat_squash','byte_weighted_heat_squash','hot_victim_fraction','probe_victim_fraction',
 'recent_reward_fraction','reward_recency_mean','next_operator_victim_fraction',
 'base_cost_rank','write_bytes_rank','cost_density_rank','r65_current_choice']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def dump(p,v): Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
def f32(v): return struct.unpack('<f',struct.pack('<f',float(v)))[0]
def sequential_sum(values):
    # CPython >=3.12 sum(float) compensates; deployment C++ loops do not.
    total=0.
    for value in values:total+=value
    return total
def bits(x): return struct.pack('<'+'f'*len(x),*x).hex()
def tie(s,a): return (len(a),sum(s.sizes[i] for i in a),tuple(a))

def r65_choice(s):
    kind,t,need=s.callback
    left=max(0,need-(s.c.m-s.used))
    if kind=='P' or not left:return ()
    eligible=[i for i,z in enumerate(s.sizes) if s.mem[i] and z>0 and i!=t]
    singles=[i for i in eligible if s.sizes[i]>=left]
    if singles:return (min(singles,key=lambda i:(core.victim_cost(s,i),s.sizes[i],i)),)
    chosen=[]
    while left>0:
        enough=[i for i in eligible if s.sizes[i]>=left]
        pick=min(enough,key=lambda i:(s.sizes[i],i)) if enough else max(eligible,key=lambda i:(s.sizes[i],-i))
        chosen.append(pick);left-=s.sizes[pick];eligible.remove(pick)
    return tuple(sorted(chosen))

def features(s,plans=None):
    """Pure causal read: uses current state, R65 confirmed history, physical next_op.

    No future index, input penalty, raw index, N, seed, filename, or expert label.
    Ranks use only strict online-computable scores; tied scores share a rank.
    """
    plans=core.pool(s) if plans is None else plans
    before=digest(s.h.__dict__)
    costs=[sequential_sum(core.victim_cost(s,i) for i in a) for a in plans]
    sizes=[sum(s.sizes[i] for i in a) for a in plans]
    densities=[c/b if b else 0. for c,b in zip(costs,sizes)]
    r65=r65_choice(s);next_op=core.next_public(s)
    owner=next_op[1] if next_op[0] in ('INSERT','PROBE','SWITCH') else -1
    rank=lambda values,j:sum(v<values[j] for v in values)/max(1,len(values)-1)
    out=[]
    for j,a in enumerate(plans):
        bs=[s.sizes[i]/s.c.m for i in a];n=len(a);mean=sequential_sum(bs)/n if n else 0.
        heats=[s.h.effective(s,i) for i in a]
        hm=sum(heats)/n if n else 0.;hx=max(heats,default=0)
        hw=sum(s.h.effective(s,i)*s.sizes[i] for i in a)/sizes[j] if sizes[j] else 0.
        recent=[]
        for i in a:
            slot=s.h.slots[i];age=s.h.clock-slot[4]
            recent.append((65-age)/65 if slot[0]==s.sizes[i] and slot[4]>=0 and 0<=age<=64 else 0.)
        extra=[min(bs,default=0.),mean,math.sqrt(sequential_sum((b-mean)*(b-mean) for b in bs)/n) if n else 0.,
               sequential_sum(b*b for b in bs),hx/(1+hx),hm/(1+hm),hw/(1+hw),
               sum(h>0 for h in heats)/n if n else 0.,sum(s.phase[i//s.c.p] for i in a)/n if n else 0.,
               sum(v>0 for v in recent)/n if n else 0.,sequential_sum(recent)/n if n else 0.,
               sum(i//s.c.p==owner for i in a)/n if n else 0.,
               rank(costs,j),rank(sizes,j),rank(densities,j),float(tuple(a)==r65)]
        x=core.features(s,a)+[f32(v) for v in extra]
        T=s.c.m*(1/s.c.w+1/s.c.r);x[13]=f32(costs[j]/(T+costs[j]))
        assert len(x)==32 and all(math.isfinite(v) for v in x)
        out.append(x)
    assert digest(s.h.__dict__)==before,'feature proposal mutated history'
    return out

def inventory():
    base=WS/'tmp/r70_inputs';cfg=json.loads((base/'config.json').read_text())
    recipe={r['id']:r for r in cfg['cases']};seen=[{}, {}, {}];out={}
    for split in ('train','dev','holdout'):
        manifest=json.loads((base/'manifests'/f'{split}.generated.json').read_text())
        for r in manifest['cases']:
            meta=recipe[r['case_id']]
            assert meta['split']==split
            for mapping,key in zip(seen,[meta['seed'],r['sha256'],r['modulo_operation_sha256']]):
                if key in mapping and mapping[key]!=split:raise ValueError('cross-split seed/input/modulo lineage')
                mapping[key]=split
            p=base/r['input'];assert sha(p)==r['sha256']
            out[r['case_id']]={**r,**meta,'path':str(p),'split':split}
    return out

def rollout_anchors(c,chooser,limit,seed,deadline):
    """Reservoir across actual multi-choice callbacks, then ordered by raw position."""
    s=core.State(c);rng=random.Random(seed);sample=[];seen=0
    while s.advance():
        check_time(deadline)
        if s.callback[0]!='P' and len(core.pool(s))>1:
            seen+=1
            if len(sample)<limit:sample.append(s.snapshot())
            else:
                j=rng.randrange(seen)
                if j<limit:sample[j]=s.snapshot()
        s.apply(chooser(s))
    return sorted(sample,key=lambda a:(a['raw'],a['stage'])),s,seen

def suffix(c,anchor,a,chooser,deadline):
    s=core.State.from_snapshot(c,anchor);initial=(s.write,s.read,s.miss,s.g)
    s.apply(a)
    while s.advance():
        check_time(deadline);s.apply(chooser(s))
    check_time(deadline)
    assert s.raw==len(c.ops) and s.callback is None
    return dict(status='complete',G_delta=s.g-initial[3],write_bytes=s.write-initial[0],
                read_bytes=s.read-initial[1],misses=s.miss-initial[2],suffix_sha256=digest(s.path),
                final_snapshot_sha256=digest(s.snapshot()),callbacks=len(s.path),
                verification='reference_State.apply_legality_and_complete_EOF',official_verified=False)

def label_case(meta,out,anchors=16,seconds=45,teacher_path=None,external_anchors=None,continuation_method='cost_aware_greedy'):
    started=time.perf_counter();deadline=started+seconds;c=core.Case.read(meta['path']);context=Context(c,deadline)
    continuation=context.chooser(continuation_method,deadline)
    half=anchors//2;paths=[];rollins={};error=None
    if teacher_path:
        witness=json.loads(Path(teacher_path).read_text());index=[0]
        def offline(s):
            row=witness[index[0]];index[0]+=1
            assert (s.raw,s.stage,s.callback[0])==(row['raw'],row['stage'],row['kind'])
            return tuple(row['spill'])
    else:offline=continuation
    try:
        for name,chooser,n in [('offline',offline,half),('r65',r65_choice,anchors-half)]:
            selected,done,count=rollout_anchors(c,chooser,n,meta['seed']+(name=='r65'),deadline)
            if name=='offline' and teacher_path:assert index[0]==len(witness),'unconsumed teacher witness'
            rollins[name]=dict(G=done.g,callbacks=len(done.path),multi_choice=count,selected_anchors=len(selected),
                              witness_sha256=digest(done.path),method='provided_complete_witness' if teacher_path and name=='offline' else ('cost_aware_greedy' if name=='offline' else 'r65_causal'))
            paths.extend((name,s) for s in selected)
        if external_anchors:
            external=json.loads(Path(external_anchors).read_text())
            # Replace at most four R65 anchors, preserving the total cap.
            external=[r for r in external if r['input_sha256']==meta['sha256']]
            take=min(4,len(external),anchors-half)
            paths=[p for p in paths if p[0]!='r65']+[p for p in paths if p[0]=='r65'][:anchors-half-take]
            paths += [('vanbest_actual',external[i*len(external)//take]['snapshot']) for i in range(take)]
    except RolloutTimeout:error='rollin_timeout'
    rows=[];branch_status=Counter();alias_conflicts=0;duplicate=set()
    for name,anchor in paths:
        if time.perf_counter()>=deadline:break
        s=core.State.from_snapshot(c,anchor);anchor_hash=digest(anchor)
        if anchor_hash in duplicate:continue
        duplicate.add(anchor_hash)
        plans=core.pool(s);xs=features(s,plans);items=[]
        for a,x in zip(plans,xs):
            try:cost=suffix(c,anchor,a,continuation,deadline)
            except RolloutTimeout:cost=dict(status='missing_timeout')
            branch_status[cost['status']]+=1
            items.append(dict(action_key=core.action_key(s,a),spill=list(a),x=x,tie=list(tie(s,a)),legal=True,cost=cost))
        available=[p['cost']['G_delta'] for p in items if p['cost']['status']=='complete']
        if len(available)<2:continue
        low=min(available);scale=max(available)-low
        groups={}
        for p in items:
            g=p['cost'].get('G_delta')
            p['valid_cost']=g is not None
            p['regret_integer']=g-low if g is not None else None
            p['target']=((g-low)/scale if scale else 0.) if g is not None else None
            if g is not None:groups.setdefault(bits(p['x']),set()).add(g)
        conflicts=sum(len(gs)>1 for gs in groups.values());alias_conflicts+=conflicts
        rows.append(dict(schema_version=1,case_id=meta['case_id'],split=meta['split'],seed=meta['seed'],family=meta['scenario'],
                         input_sha256=meta['sha256'],modulo_operation_sha256=meta['modulo_operation_sha256'],
                         rollin=name,anchor_snapshot=anchor,anchor_snapshot_sha256=anchor_hash,
                         public_next_op=list(core.next_public(s)),feature_version=FEATURE_VERSION,feature_names=FEATURE_NAMES,
                         candidate_pool_version=core.POOL_VERSION,label_kind='fixed_complete_suffix_cost',
                         continuation=continuation_method,continuation_source_sha256=sha(R70/'teacher_portfolio.py'),
                         interval_source_sha256=sha(WS/'tmp/r70_interval/interval_teacher.py'),
                         label_protocol_version='r70-winner-suffix-v1',objective='integer_G=write*R+read*W+penalty*miss*W*R',
                         anchor_miss_already_counted=s.callback[0]=='M',cost_scope='current_action_plus_complete_remaining_suffix',
                         normalization='subtract_integer_G_first_then_divide_state_maxgap',integer_gap_scale=scale,
                         conflicting_identical_feature_groups=conflicts,plans=items))
    out.mkdir(parents=True,exist_ok=True)
    target=out/(meta['case_id']+'.jsonl')
    if target.exists():raise FileExistsError(target)
    target.write_text(''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows),encoding='utf8')
    report=dict(case_id=meta['case_id'],split=meta['split'],rows=len(rows),branches=dict(branch_status),
                alias_conflict_groups=alias_conflicts,rollins=rollins,elapsed_seconds=time.perf_counter()-started,
                timeout=time.perf_counter()>=deadline,error=error,labels_sha256=sha(target),teacher_optimality_claim=False)
    dump(out/(meta['case_id']+'.report.json'),report);return report

def batch(out,seconds=45):
    cases=inventory()
    teacher_path=WS/'tmp/r70/teacher_manifest.json'
    manifest=json.loads(teacher_path.read_text());teachers={r['case_id']:r for r in manifest['teachers']}
    assert manifest['complete_verified_count']==24 and len(teachers)==24
    expert_path=WS/'tmp/r70_expert_rollin/manifest.json'
    expert=json.loads(expert_path.read_text());experts={r['case_id']:r for r in expert['cases']}
    reports=[]
    # All train; four predeclared dev cases, one per family. No holdout labels.
    dev_selected={}
    for meta in sorted(cases.values(),key=lambda r:r['case_id']):
        if meta['split']=='dev':dev_selected.setdefault(meta['scenario'],meta['case_id'])
    for meta in sorted(cases.values(),key=lambda r:r['case_id']):
        if meta['split']=='holdout' or meta['split']=='dev' and meta['case_id'] not in dev_selected.values():continue
        destination=out/(meta['case_id']+'.report.json')
        if destination.exists():reports.append(json.loads(destination.read_text()));continue
        witness=None;anchors=None;source={}
        if meta['split']=='train':
            t=teachers[meta['case_id']]
            assert t['input_sha256']==meta['sha256'] and t['replay_verified'] and t['legal_complete_witness']
            witness=Path(t['witness_path']);witness=witness if witness.is_absolute() else WS/witness
            assert sha(witness)==t['witness_raw_sha256']
            source['teacher']=t
            e=experts.get(meta['case_id'])
            if e and not e['nonempty_periodic']:
                assert e['input_sha256']==meta['sha256'] and e['reference_replay_verified'] and e['all_callbacks_consumed']
                anchors=Path(e['anchors_path']);anchors=anchors if anchors.is_absolute() else WS/anchors
                assert sha(anchors)==e['anchors_sha256']
                source['vanbest']=e
        method=t['teacher_method'] if meta['split']=='train' else 'cost_aware_greedy'
        report=label_case(meta,out,16 if meta['split']=='train' else 4,seconds,witness,anchors,method)
        if witness and 'offline' in report['rollins']:assert report['rollins']['offline']['G']==t['cost']['G']
        report['source_provenance']=source
        dump(destination,report);reports.append(report)
        print(json.dumps({k:report[k] for k in ('case_id','rows','branches','elapsed_seconds','timeout','error')}),flush=True)
    dump(out/'batch_report.json',dict(status='complete_label_batch',reports=reports,
          teacher_manifest_sha256=sha(teacher_path),expert_manifest_sha256=sha(expert_path),
          dev_case_ids=list(dev_selected.values()),holdout_labels=0,feature_version=FEATURE_VERSION))

def read_rows(folder,split):
    rows=[]
    for p in sorted(Path(folder).glob('*.jsonl')):
        for line in p.read_text().splitlines():
            r=json.loads(line)
            if r['split']==split:rows.append(r)
    return rows

def gate(folder):
    cases=inventory();loaded={};counts=Counter();roles=Counter();conflicts=0;all_ties=0;seen=set();rows=[]
    teachers={r['case_id']:r for r in json.loads((WS/'tmp/r70/teacher_manifest.json').read_text())['teachers']}
    for path in Path(folder).glob('*.jsonl'):
        report=json.loads(path.with_suffix('.report.json').read_text())
        assert sha(path)==report['labels_sha256'],'label file changed since generation'
        if report['split']=='train':
            saved=report['source_provenance']['teacher'];current=teachers[report['case_id']]
            assert saved==current and sha(saved['witness_path'])==saved['witness_raw_sha256']
            assert saved['replay_verified'] and saved['legal_complete_witness']
            expert=report['source_provenance'].get('vanbest')
            if expert:assert expert['reference_replay_verified'] and not expert['nonempty_periodic'] and sha(expert['anchors_path'])==expert['anchors_sha256']
    for split in ('train','dev'):
        for row in read_rows(folder,split):
            meta=cases[row['case_id']]
            assert meta['split']==split and row['input_sha256']==meta['sha256'] and row['seed']==meta['seed']
            assert row['modulo_operation_sha256']==meta['modulo_operation_sha256']
            assert row['feature_version']==FEATURE_VERSION and row['feature_names']==FEATURE_NAMES
            assert row['label_protocol_version']=='r70-winner-suffix-v1'
            assert row['continuation']==(teachers[row['case_id']]['teacher_method'] if split=='train' else 'cost_aware_greedy')
            c=loaded.setdefault(row['case_id'],None)
            if c is None:c=core.Case.read(meta['path']);loaded[row['case_id']]=c
            anchor=row['anchor_snapshot'];assert digest(anchor)==row['anchor_snapshot_sha256']
            identity=(row['case_id'],row['anchor_snapshot_sha256']);assert identity not in seen;seen.add(identity)
            s=core.State.from_snapshot(c,anchor);plans=core.pool(s);xs=features(s,plans)
            assert list(core.next_public(s))==row['public_next_op'] and len(plans)==len(row['plans'])<=8
            measured=[]
            for a,x,p in zip(plans,xs,row['plans']):
                assert p['legal'] is True and p['spill']==list(a) and p['action_key']==core.action_key(s,a)
                assert bits(x)==bits(p['x']) and p['tie']==[len(a),sum(s.sizes[i] for i in a),list(a)]
                z=core.State.from_snapshot(c,anchor);z.apply(a)
                cost=p['cost'];valid=cost['status']=='complete';assert p['valid_cost']==valid
                if valid:
                    assert all(type(cost[k]) is int and cost[k]>=0 for k in ('G_delta','write_bytes','read_bytes','misses'))
                    assert cost['G_delta']==cost['write_bytes']*c.r+cost['read_bytes']*c.w+c.penalty*cost['misses']*c.w*c.r
                    assert len(cost['suffix_sha256'])==len(cost['final_snapshot_sha256'])==64
                    measured.append(cost['G_delta'])
                else:assert p['target'] is None and p['regret_integer'] is None
            assert len(measured)>=2
            lo=min(measured);gap=max(measured)-lo;assert gap==row['integer_gap_scale']
            for p in row['plans']:
                if p['valid_cost']:
                    delta=p['cost']['G_delta']-lo
                    assert p['regret_integer']==delta and p['target']==(delta/gap if gap else 0.)
            counts[split]+=1;roles[row['rollin']]+=1;conflicts+=row['conflicting_identical_feature_groups'];all_ties+=gap==0;rows.append(row)
    if not counts['train']:raise ValueError('no qualified train labels')
    result=dict(passed=True,row_counts=dict(counts),rollin_counts=dict(roles),cases=len(loaded),
                all_cost_tie_states=all_ties,identical_feature_different_cost_groups=conflicts,
                teacher_and_expert_provenance_in_per_case_reports=True,holdout_labels=0,
                validation_scope='identity_split_current_features_actions_integer_ledger_complete_suffix_metadata',
                every_suffix_independently_official_replayed=False)
    dump(Path(folder)/'gate_report.json',result);return result

def score_python(model,x):
    z=f32(model['b2']);x=[f32(v) for v in x]
    for j in range(16):
        h=f32(model['b1'][j])
        for i in range(32):h=f32(h+f32(model['w1'][j][i]*x[i]))
        z=f32(z+f32(model['w2'][j]*max(0.,h)))
    return f32(x[13]+max(-1.,min(1.,z)))

def evaluate_rows(model,rows):
    result={}
    for mode in ('zero_residual','neural'):
        regrets=[];correct=0;missing=0;bycase={}
        for r in rows:
            plans=r['plans'];scores=[p['x'][13] if mode=='zero_residual' else score_python(model,p['x']) for p in plans]
            j=min(range(len(plans)),key=lambda j:(scores[j],plans[j]['tie']))
            if not plans[j]['valid_cost']:missing+=1;continue
            delta=plans[j]['regret_integer'];correct+=delta==0;regrets.append(plans[j]['target'])
            bycase.setdefault(r['case_id'],[]).append(delta)
        result[mode]=dict(states=len(rows),selected_missing_cost=missing,known_best_count=correct,
                          mean_normalized_regret=sum(regrets)/len(regrets) if regrets else None,
                          mean_integer_G_regret_by_case={k:sum(v)/len(v) for k,v in bycase.items()})
    return result

def cpp_export(model):
    fmt=lambda v:format(float(v),'.9g')+('f' if '.' in format(float(v),'.9g') or 'e' in format(float(v),'.9g') else '.0f')
    flat=lambda a:', '.join(fmt(v) for v in a)
    rows=',\n'.join('{'+flat(r)+'}' for r in model['w1'])
    return '''#pragma once
#include <cmath>
#include <limits>
inline float r70_score(const float x[32]) {
 static const float w1[16][32]={%s};
 static const float b1[16]={%s};
 static const float w2[16]={%s};
 float z=%s;
 for(int i=0;i<32;++i)if(!std::isfinite(x[i]))return std::numeric_limits<float>::infinity();
 for(int j=0;j<16;++j){float h=b1[j];for(int i=0;i<32;++i)h+=w1[j][i]*x[i];z+=w2[j]*(h>0?h:0);}
 z=x[13]+(z<-1?-1:(z>1?1:z));return std::isfinite(z)?z:std::numeric_limits<float>::infinity();
}
'''%(rows,flat(model['b1']),flat(model['w2']),fmt(model['b2']))

def train(folder,out,epochs=32):
    validation=gate(folder)
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.manual_seed(20261030)
    rows=read_rows(folder,'train');dev=read_rows(folder,'dev')
    if not rows:raise ValueError('no train labels')
    if {r['case_id'] for r in rows}&{r['case_id'] for r in dev}:raise ValueError('case split overlap')
    counts=Counter(r['case_id'] for r in rows if r['integer_gap_scale']>0)
    x=np.zeros((len(rows),8,32),np.float32);y=np.zeros((len(rows),8),np.float32);valid=np.zeros((len(rows),8),bool)
    for i,r in enumerate(rows):
        assert r['feature_version']==FEATURE_VERSION and len(r['plans'])<=8
        for j,p in enumerate(r['plans']):
            x[i,j]=p['x'];valid[i,j]=p['valid_cost'];y[i,j]=p['target'] if p['valid_cost'] else 0.
    assert np.isfinite(x).all() and np.isfinite(y).all()
    xt=torch.from_numpy(x);yt=torch.from_numpy(y);mask=torch.from_numpy(valid)
    weights=torch.tensor([1/counts[r['case_id']] if r['integer_gap_scale']>0 else 0. for r in rows]);weights/=weights.sum()
    if not torch.isfinite(weights).all():raise ValueError('no non-tie train signal')
    w1=torch.nn.Parameter(torch.empty(16,32).uniform_(-.1,.1));b1=torch.nn.Parameter(torch.full((16,),.05))
    w2=torch.nn.Parameter(torch.zeros(1,16));b2=torch.nn.Parameter(torch.zeros(1))
    opt=torch.optim.Adam([w1,b1,w2,b2],lr=.01)
    # Real observed non-tie pairs only. Padding, missing costs, and cost ties have no pair target.
    diff=yt[:,:,None]-yt[:,None,:]
    pair=mask[:,:,None]&mask[:,None,:]&(diff.abs()>0)&torch.triu(torch.ones(8,8,dtype=torch.bool),diagonal=1)
    same=(xt[:,:,None,:]==xt[:,None,:,:]).all(-1)
    unlearnable_pairs=int((pair&same).sum());pair&=~same
    losses=[];start=time.perf_counter()
    for epoch in range(epochs):
        score=xt[:,:,13]+torch.nn.functional.linear(torch.relu(torch.nn.functional.linear(xt,w1,b1)),w2,b2).squeeze(-1).clamp(-1,1)
        value=(torch.nn.functional.smooth_l1_loss(score,yt,reduction='none')*mask).sum(1)/mask.sum(1).clamp_min(1)
        element=torch.nn.functional.softplus(-(score[:,:,None]-score[:,None,:])*diff.sign()/.25)
        ranking=(element*pair*diff.abs()).sum((1,2))/pair.sum((1,2)).clamp_min(1)
        loss=((value+.25*ranking)*weights).sum()
        if not torch.isfinite(loss):raise ValueError('nonfinite loss')
        opt.zero_grad();loss.backward();opt.step();losses.append(float(loss.detach()))
    model=dict(schema_version=1,feature_version=FEATURE_VERSION,dimensions=[32,16,1],mode='residual',base_feature_index=13,
               residual_clip=[-1,1],w1=w1.detach().numpy().tolist(),b1=b1.detach().numpy().tolist(),
               w2=w2.detach().numpy()[0].tolist(),b2=float(b2.detach()[0]))
    out.mkdir(parents=True,exist_ok=True)
    if (out/'model.json').exists():raise FileExistsError('model output already exists')
    dump(out/'model.json',model);(out/'tiny_score.hpp').write_text(cpp_export(model),encoding='utf8')
    import shutil
    shutil.copyfile(ROOT/'policy.hpp',out/'policy.hpp');shutil.copyfile(R66/'shared_pool.hpp',out/'shared_pool.hpp')
    vectors=[]
    for r in (dev+rows):
        for p in r['plans']:
            if len(vectors)<128:vectors.append(dict(case_id=r['case_id'],x=p['x'],score=score_python(model,p['x'])))
    dump(out/'score_vectors.json',vectors)
    dump(out/'dev_label_diagnostics.json',evaluate_rows(model,dev))
    report=dict(status='trained_not_official_CPU_validated',train_rows=len(rows),train_cases=len(counts),dev_rows=len(dev),
                epochs=epochs,seed=20261030,threads=1,loss_first=losses[0],loss_last=losses[-1],losses=losses,
                seconds=time.perf_counter()-start,parameters=545,macs_per_plan=528,model_sha256=sha(out/'model.json'),
                objective='same_state_observed_complete_suffix_normalized_regret_Huber_plus_gap_weighted_pair',
                case_weighting='equal_total_weight_per_informative_train_case; all-cost-tie states zero weight',
                identical_feature_non_tie_pairs_excluded=unlearnable_pairs,gate=validation,test_labels=0,formal_D=None)
    dump(out/'training_report.json',report);print(json.dumps(report),flush=True)

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('label');q.add_argument('--split',choices=['train','dev'],required=True);q.add_argument('--case')
    q.add_argument('--out',type=Path,required=True);q.add_argument('--anchors',type=int);q.add_argument('--seconds',type=float,default=45)
    q.add_argument('--teacher-witness');q.add_argument('--external-anchors')
    q=sub.add_parser('train');q.add_argument('--labels',type=Path,required=True);q.add_argument('--out',type=Path,required=True);q.add_argument('--epochs',type=int,default=32)
    q=sub.add_parser('batch');q.add_argument('--out',type=Path,required=True);q.add_argument('--seconds',type=float,default=45)
    q=sub.add_parser('gate');q.add_argument('--labels',type=Path,required=True)
    a=p.parse_args()
    if a.command=='batch':batch(a.out,a.seconds);return
    if a.command=='gate':print(json.dumps(gate(a.labels)),flush=True);return
    if a.command=='train':
        if not 1<=a.epochs<=64:raise ValueError('bounded epochs 1..64')
        train(a.labels,a.out,a.epochs);return
    for meta in inventory().values():
        if meta['split']!=a.split or a.case and meta['case_id']!=a.case:continue
        if (a.out/(meta['case_id']+'.jsonl')).exists():continue
        print(json.dumps(label_case(meta,a.out,a.anchors or (16 if a.split=='train' else 4),a.seconds,a.teacher_witness,a.external_anchors)),flush=True)

if __name__=='__main__':main()
