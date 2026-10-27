"""Cost-sensitive policy distillation, with strict observable-only deployment.
Only synthetic historical development data are used for fitting. A fresh test
batch is generated AFTER the chosen source/model is frozen. No test-score oracle
or workload file is present in the submitted scheduler.
"""
from __future__ import annotations
import argparse, collections, hashlib, itertools, json, math, os, random, re
import secrets, statistics, subprocess, sys, time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'stress20'
DEV=OLD/'run_20261018_183734_1b7713'
sys.path.insert(0,str(OLD))
from retest import make_workload,write_case,seed_for,FAMILIES,MIB
OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
FEATURES=['read_write_bandwidth_ratio','write_bandwidth','read_bandwidth','memory_MiB','partitions',
    'largest_partition_fraction','nonempty_fraction','size_skew','inserting_target_fraction',
    'probe_resident_fraction','used_fraction','next_probe_size_fraction_or_minus_one','global_hit_fraction','build_operator_fraction','operators','partitions_per_operator']
MODES=[str(i) for i in range(7)]

def dump(path,x):path.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def loadlines(path):return [json.loads(l) for l in path.read_text('utf8').splitlines() if l.strip()]
def invoke_rows(rows,policies,dest,repetitions=1,fast=False):
    start=time.perf_counter()
    with dest.open('w',encoding='utf8') as out:
        for rep in range(repetitions):
            names=list(policies)
            # Rotate order to reduce systematic cold-start timing bias.
            if rep%2:names.reverse()
            for begin in range(0,len(rows),64):
                chunk=rows[begin:begin+64]
                listfile=OUT/'active_inputs.txt';listfile.write_text('\n'.join(str(Path(r['file']).resolve()) for r in chunk)+'\n',encoding='ascii')
                cmd=[str(ROOT/'benchmark.exe'),'--batch',str(listfile),','.join(names)]
                if fast:cmd.append('fast')
                proc=subprocess.run(cmd,capture_output=True,text=True,timeout=720)
                if proc.returncode:raise RuntimeError(proc.stderr[-3000:])
                for line in proc.stdout.splitlines():
                    result=json.loads(line);result['repeat']=rep
                    if not result['ok']:raise RuntimeError(json.dumps(result))
                    out.write(json.dumps(result)+'\n')
                out.flush()
                print(f'{dest.stem} repeat {rep+1}/{repetitions}: {min(begin+64,len(rows))}/{len(rows)} cases, {time.perf_counter()-start:.1f}s',flush=True)

def historical_rows():
    rows=json.loads((DEV/'manifest.json').read_text('utf8'))+json.loads((DEV/'targeted_manifest.json').read_text('utf8'))
    result=[]
    for row in rows:
        if row.get('formal_range') and row.get('expected')=='feasible':
            row={**row,'file':str((DEV/row['file']).resolve())}
            group=f'seed:{row["seed"]}' if 'seed' in row else row['id']
            row['group']=group;result.append(row)
    return result

def collect():
    rows=historical_rows();dump(OUT/'development_manifest.json',rows)
    invoke_rows(rows,['baseline']+MODES+['old_prior32','prefix_prior1'],OUT/'development_rollouts.jsonl')

def matrix(rows,data):
    penalties={str(Path(row['file']).resolve()):row['penalty'] for row in rows}
    index=collections.defaultdict(list)
    for r in data:index[(str(Path(r['input']).resolve()),r['policy'])].append(r)
    lookup={}
    for key,values in index.items():
        # IO, misses and action outcome are deterministic. Timing is not.
        for v in values:
            assert v['ok'] and v['hit']+v['miss']>=0
            assert v['io']==values[0]['io'] and v['miss']==values[0]['miss']
        chosen=dict(values[0]);chosen['decision_us']=statistics.median(x['decision_us'] for x in values)
        chosen['score']=chosen['io']+penalties[key[0]]*chosen['miss']+chosen['decision_us']
        chosen['wall_s']=statistics.median(x['wall_s'] for x in values);lookup[key]=chosen
    return lookup

def tree_fit(x,loss,max_depth,min_leaf,indices=None):
    if indices is None:indices=np.arange(len(x))
    costs=loss[indices].sum(axis=0);mode=int(costs.argmin());node={'mode':mode,'count':len(indices),'cost':float(costs[mode])}
    if max_depth==0 or len(indices)<2*min_leaf:return node
    best=None
    for f in range(x.shape[1]):
        values=x[indices,f];unique=np.unique(values)
        if len(unique)<2:continue
        if len(unique)>25:thresholds=np.unique(np.quantile(values,np.linspace(.04,.96,23)))
        else:thresholds=(unique[:-1]+unique[1:])/2
        for threshold in thresholds:
            mask=values<=threshold;left=indices[mask];right=indices[~mask]
            if len(left)<min_leaf or len(right)<min_leaf:continue
            c=float(loss[left].sum(axis=0).min()+loss[right].sum(axis=0).min())
            if best is None or c<best[0]:best=(c,f,float(threshold),left,right)
    if best is None or best[0]>=node['cost']-1e-4:return node
    _,f,t,left,right=best
    node.update(feature=f,threshold=t,left=tree_fit(x,loss,max_depth-1,min_leaf,left),right=tree_fit(x,loss,max_depth-1,min_leaf,right))
    return node
def predict(tree,x):
    while 'feature' in tree:tree=tree['left'] if x[tree['feature']]<=tree['threshold'] else tree['right']
    return tree['mode']
def nodes(tree):return 1 if 'feature' not in tree else 1+nodes(tree['left'])+nodes(tree['right'])
def cpp_tree(tree,indent='        '):
    if 'feature' not in tree:return indent+f'return {tree["mode"]};'
    return indent+f'if(f[{tree["feature"]}] <= {tree["threshold"]:.17g}) {{\n'+cpp_tree(tree['left'],indent+'    ')+'\n'+indent+'} else {\n'+cpp_tree(tree['right'],indent+'    ')+'\n'+indent+'}'

def train():
    robust='--robust' in sys.argv
    if not robust:raise ValueError('Deferred routing requires --robust: eligible experts share the same BUILD policy.')
    rows=json.loads((OUT/'development_manifest.json').read_text('utf8'));data=loadlines(OUT/'development_rollouts.jsonl');lookup=matrix(rows,data)
    # Group related key-alias / ID-transform samples together, avoiding train/validation leakage.
    groups=sorted({r['group'] for r in rows});random.Random(20261026).shuffle(groups);ntrain=int(.8*len(groups));train_groups=set(groups[:ntrain])
    x=[];ratios=[];fit_rows=[]
    for row in rows:
        path=str(Path(row['file']).resolve());base=lookup[path,'baseline']['score']
        candidate=[lookup[path,p] for p in MODES]
        if not candidate[0]['has_features'] or base<=0:continue
        assert all(candidate[j]['features']==candidate[0]['features'] for j in [0,3,4,6]),'First Miss observables differ among same-BUILD experts'
        x.append(candidate[0]['features']);ratios.append([c['score']/base for c in candidate]);fit_rows.append(row)
    x=np.array(x);ratios=np.array(ratios);trainmask=np.array([r['group'] in train_groups for r in fit_rows]);valmask=~trainmask
    print('fit rows',len(x),'train',sum(trainmask),'validation',sum(valmask),flush=True)
    candidates=[]
    for risk in [0.0,.02,.1,.3]:
        loss=np.minimum(ratios,1.0)+risk*np.minimum(np.maximum(ratios-1,0),8.0)
        if robust:loss[:,[1,2,5]]=1e6
        for depth in [0,1,2,3,4]:
            for leaf in [24,48,80]:
                tree=tree_fit(x[trainmask],loss[trainmask],depth,leaf)
                selected=np.array([predict(tree,row) for row in x[valmask]])
                rr=ratios[valmask][np.arange(sum(valmask)),selected]
                reward=float(np.maximum(0,1-rr).mean());regret=float(np.minimum(np.maximum(rr-1,0),8).mean())
                # A fixed validation risk penalty prefers robust ties; it is not tuned on final tests.
                objective=reward-.1*regret-.0002*nodes(tree)
                candidates.append(dict(risk=risk,depth=depth,min_leaf=leaf,nodes=nodes(tree),validation_reward=reward,validation_clipped_regret=regret,objective=objective,tree=tree))
    candidates.sort(key=lambda c:c['objective'],reverse=True);best=candidates[0]
    report=dict(features=FEATURES,modes=MODES,allowed_modes=[0,3,4,6] if robust else list(range(7)),train_groups=sorted(train_groups),validation_groups=sorted(set(groups)-train_groups),
        train_cases=int(sum(trainmask)),validation_cases=int(sum(valmask)),
        objective='mean(max(0,1-Score/BASE)) - 0.1*mean(min(max(Score/BASE-1,0),8)) - 0.0002*nodes',
        validation_fixed_modes={p:dict(reward=float(np.maximum(0,1-ratios[valmask,j]).mean()),geomean=float(np.exp(np.log(ratios[valmask,j]).mean())),worst=float(ratios[valmask,j].max())) for j,p in enumerate(MODES)},
        selected=best,candidates=[{k:v for k,v in c.items() if k!='tree'} for c in candidates])
    dump(OUT/'training_report.json',report)
    path=ROOT/'MySpillScheduler.cpp';source=path.read_text('utf8')
    code='// MODEL_BEGIN: generated exclusively from development data.\n'+cpp_tree(best['tree'])+'\n        // MODEL_END'
    source=re.sub(r'// MODEL_BEGIN:.*?// MODEL_END',lambda m:code,source,flags=re.S)
    path.write_text(source,encoding='utf8')
    dump(OUT/'policy_freeze.json',dict(date='2026-10-26',model=best,source_sha256=sha(path),training_manifest_sha256=sha(OUT/'development_manifest.json'),
        benchmark_sha256=sha(ROOT/'benchmark.cpp'),features_only_from_SystemState=True,actual_penalty_not_available=True,no_future_read_at_inference=True))
    print(json.dumps({k:v for k,v in best.items() if k!='tree'},indent=2),flush=True)

def permute_ops(params,ops,rng):
    k,p,*_=params;opmap=list(range(k));rng.shuffle(opmap);maps=[]
    for _ in range(k):a=list(range(p));rng.shuffle(a);maps.append(a)
    result=[]
    for t,o,*args in ops:
        if t=='SWITCH':result.append((t,opmap[o]));continue
        key=args[0];key=maps[o][key%p]+p*(key//p)
        result.append((t,opmap[o],key,*args[1:]))
    return result

def generate_test():
    freeze=json.loads((OUT/'policy_freeze.json').read_text('utf8'));assert freeze['source_sha256']==sha(ROOT/'MySpillScheduler.cpp')
    run=ROOT/('holdout_'+time.strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3));(run/'cases').mkdir(parents=True)
    master=secrets.token_hex(32);rows=[]
    for family in FAMILIES:
        for j in range(24):
            seed=seed_for(master,f'{family}/{j}');params,ops=make_workload(seed,family)
            renamed=j%2==1
            if renamed:ops=permute_ops(params,ops,random.Random(seed^0x46A1))
            row=write_case(run,f'{family}_{j:02}',params,ops,split='fresh_holdout',family=family,seed=seed,renamed=renamed,expected='feasible')
            row['file']=str((run/row['file']).resolve());rows.append(row)
    # OOD corner matrix uses new seeds; every binary corner is covered.
    for j,values in enumerate(itertools.product([1,8],[2,64],[64*MIB,4096*MIB],[1,10000],[1,10000],[1,1000],[1,10000])):
        seed=seed_for(master,f'corners/{j}');k,p,m,w,r,penalty,b=values
        params,ops=make_workload(seed,'interleaved_phases' if k>1 else 'hot_plus_scan',values,length=512)
        ops=permute_ops(params,ops,random.Random(seed^0xCD))
        row=write_case(run,f'corner_{j:03}',params,ops,split='fresh_corners',family='parameter_corners',seed=seed,renamed=True,expected='feasible')
        row['file']=str((run/row['file']).resolve());rows.append(row)
    dump(run/'manifest.json',rows);dump(run/'protocol.json',dict(master=master,freeze=freeze,generated_after_model_freeze=True,description='480 fresh workloads + 128 new-seed corners; 50% of family inputs and all corners randomly relabel IDs.'))
    (ROOT/'current_holdout.txt').write_text(run.name,'ascii');print('holdout',run.name,'cases',len(rows),flush=True)

def test():
    run=ROOT/(ROOT/'current_holdout.txt').read_text('ascii').strip();rows=json.loads((run/'manifest.json').read_text('utf8'))
    freeze=json.loads((OUT/'policy_freeze.json').read_text('utf8'));assert freeze['source_sha256']==sha(ROOT/'MySpillScheduler.cpp')
    invoke_rows(rows,['baseline','recommended','score_first','learned','0','1','2','3','4','5','6','old_prior32','prefix_prior1'],run/'rollouts.jsonl',repetitions=3)
    summarize(run,rows,loadlines(run/'rollouts.jsonl'))

def summarize(run,rows,data):
    lookup=matrix(rows,data);policies=sorted({r['policy'] for r in data},key=lambda p:(p!='baseline',p));summary={}
    for policy in policies:
        all_selected=[(row,lookup[str(Path(row['file']).resolve()),policy],lookup[str(Path(row['file']).resolve()),'baseline']) for row in rows]
        selected=[t for t in all_selected if t[2]['score']>0 and t[1]['score']>0]
        ratios=[r['score']/b['score'] for _,r,b in selected]
        savings=[max(0,1-x) for x in ratios]
        # Do not present the 50-point cap on hundreds of synthetic cases as an official score.
        wins=sum(x<.999999 for x in ratios);losses=sum(x>1.000001 for x in ratios)
        summary[policy]=dict(cases=len(rows),ratio_cases=len(ratios),geometric_ratio=math.exp(statistics.mean(map(math.log,ratios))),median_ratio=statistics.median(ratios),
            mean_clamped_reduction=statistics.mean(savings),wins=wins,losses=losses,ties=len(ratios)-wins-losses,
            p95_ratio=sorted(ratios)[int(.95*len(ratios))],worst_ratio=max(ratios),
            sum_decision_us=sum(r['decision_us'] for _,r,_ in all_selected),sum_io_us=sum(r['io'] for _,r,_ in all_selected),
            total_misses=sum(r['miss'] for _,r,_ in all_selected),max_wall_s=max(r['wall_s'] for _,r,_ in all_selected),
            selected_modes=dict(collections.Counter(r['selected_mode'] for _,r,_ in all_selected)),
            worst_cases=[dict(id=row['id'],family=row['family'],ratio=r['score']/b['score'],candidate=r,baseline=b) for row,r,b in sorted(selected,key=lambda z:z[1]['score']/z[2]['score'],reverse=True)[:8]])
    report=dict(date='2026-10-26',case_count=len(rows),repetitions=3,source_sha256=sha(ROOT/'MySpillScheduler.cpp'),summary=summary,
        limitation='Synthetic validation, local machine, not official hidden-score evidence. Decision timing uses the published lambda region, including the state snapshot.')
    dump(run/'summary.json',report)
    # Family and renamed-ID analyses reveal distribution and tie-break sensitivity.
    groups={}
    for group in sorted({r['family'] for r in rows}):
        ids=[r for r in rows if r['family']==group];groups[group]={}
        for policy in [p for p in ['recommended','score_first','learned','0','4','old_prior32','prefix_prior1'] if p in policies]:
            ratios=[lookup[str(Path(row['file']).resolve()),policy]['score']/lookup[str(Path(row['file']).resolve()),'baseline']['score'] for row in ids if lookup[str(Path(row['file']).resolve()),'baseline']['score']>0]
            groups[group][policy]=dict(geometric_ratio=math.exp(statistics.mean(map(math.log,ratios))),mean_clamped_reduction=statistics.mean(max(0,1-x) for x in ratios),worst=max(ratios))
    dump(run/'by_family.json',groups)
    print(json.dumps({k:{a:b for a,b in v.items() if a!='worst_cases'} for k,v in summary.items()},indent=2),flush=True)

def summarize_only():
    run=ROOT/(ROOT/'current_holdout.txt').read_text('ascii').strip();summarize(run,json.loads((run/'manifest.json').read_text('utf8')),loadlines(run/'rollouts.jsonl'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['collect','train','generate_test','test','summarize_only']);ap.add_argument('--robust',action='store_true');args=ap.parse_args()
    globals()[args.action]()
if __name__=='__main__':main()
