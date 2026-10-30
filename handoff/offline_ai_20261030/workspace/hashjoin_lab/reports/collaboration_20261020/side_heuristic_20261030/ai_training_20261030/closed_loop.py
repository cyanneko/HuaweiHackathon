"""Full explicit R70 development inputs; CPU Python quality, never formal D."""
import argparse
import json
from pathlib import Path
import time
import torch
from model import PlanRanker
from train import HERE, WS, old, dump, sha


def load_model(path):
    data=json.loads(Path(path).read_text())
    model=PlanRanker(data['hidden'],data['zero_columns'],data['base_skip'])
    with torch.no_grad():
        for layer,weights in zip(model.layers,data['layers']):
            layer.weight.copy_(torch.tensor(weights['weight']))
            layer.bias.copy_(torch.tensor(weights['bias']))
    return model.eval()


def run_case(case, mode, model, deadline):
    s=old.core.State(case);score_calls=0;min_margin=None
    while s.advance():
        if time.perf_counter()>deadline:raise TimeoutError('Shared closed-loop time budget exhausted')
        plans=old.core.pool(s)
        if len(plans)==1:a=plans[0]
        elif mode=='naive':
            kind,target,need=s.callback;left=max(0,need-(case.m-s.used))
            eligible=[i for i,z in enumerate(s.sizes) if s.mem[i] and z>0 and i!=target];a=[]
            while left>0:
                pick=max(eligible,key=lambda i:(s.sizes[i],-i));a.append(pick)
                left-=s.sizes[pick];eligible.remove(pick)
            a=tuple(sorted(a))
        elif mode=='r65':a=old.r65_choice(s)
        else:
            xs=old.features(s,plans)
            if model is None:scores=[x[13] for x in xs]
            else:
                scores=model(torch.tensor(xs,dtype=torch.float32)).tolist();score_calls+=1
            ordered=sorted(range(len(plans)),key=lambda j:(scores[j],old.tie(s,plans[j])))
            margin=scores[ordered[1]]-scores[ordered[0]]
            min_margin=margin if min_margin is None else min(min_margin,margin)
            a=plans[ordered[0]]
        assert a in plans
        s.apply(a)
    return s,{'multi_candidate_network_calls':score_calls,'minimum_score_margin':min_margin}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--models',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--seconds',type=float,default=180)
    args=ap.parse_args();assert not args.out.exists();args.out.mkdir(parents=True)
    torch.set_num_threads(1)
    cfg=json.loads((WS/'tmp/r70_inputs/config.json').read_text())
    cases=[r for r in cfg['cases'] if r['split']=='dev'];assert len(cases)==8
    model_names=[r['name'] for r in json.loads((HERE/'model_protocol.json').read_text())['models']]
    modes=['naive','zero_residual','r65']+model_names
    models={name:load_model(args.models/name/'model.json') for name in model_names}
    inputs=[]
    for meta in cases:
        path=WS/'tmp/r70_inputs/data/dev'/(meta['id']+'.txt')
        inputs.append({**meta,'path':str(path),'sha256':sha(path)})
    dump(args.out/'manifest.json',{'cases':inputs,'methods':modes,'model_hashes':{n:sha(args.models/n/'model.json') for n in model_names},
         'no_holdout_inputs_read':True,'development_selection_only':True,'total_budget_seconds':args.seconds})
    results=[];start=time.perf_counter();deadline=start+args.seconds
    with torch.inference_mode():
        for meta in inputs:
            case=old.core.Case.read(meta['path'])
            for mode in modes:
                t=time.perf_counter()
                state,extra=run_case(case,mode,models.get(mode),deadline)
                name=meta['id']+'_'+mode
                witness=args.out/(name+'.witness.json');dump(witness,state.path)
                row={'case_id':meta['id'],'family':meta['scenario'],'method':mode,'input_sha256':case.input_hash,
                     'G':state.g,'cost_without_D':state.g/(case.w*case.r),
                     'write_bytes':state.write,'read_bytes':state.read,'misses':state.miss,'hits':state.hit,
                     'callbacks':len(state.path),'witness_sha256':sha(witness),'python_wall_seconds':time.perf_counter()-t,
                     'formal_D':None,**extra}
                results.append(row);dump(args.out/'partial.json',results)
            print(json.dumps({'completed_case':meta['id'],'seconds':time.perf_counter()-start}),flush=True)
    summaries={}
    for mode in modes:
        ratios=[];scores=[];wins=losses=ties=0
        for meta in inputs:
            lookup={r['method']:r['cost_without_D'] for r in results if r['case_id']==meta['id']}
            value=lookup[mode];base=lookup['zero_residual']
            ratios.append(value/base);scores.append(max(0,min(10,10*(1-value/lookup['naive']))))
            wins+=value<base;losses+=value>base;ties+=value==base
        summaries[mode]={'mean_case_ratio_vs_zero_residual':sum(ratios)/len(ratios),'worst_case_ratio_vs_zero_residual':max(ratios),
                         'wins_losses_ties_vs_zero_residual':[wins,losses,ties],
                         'case_mean_formula_reference_naive_without_D':sum(scores)/len(scores)}
    dump(args.out/'report.json',{'status':'PYTHON_COMPLETE_DEV_CLOSED_LOOP','cases':len(inputs),'results':results,'summaries':summaries,
         'seconds':time.perf_counter()-start,'formal_D':None,'official_cpp_replay':'pending',
         'naive_baseline_limit':'Python naive uses deterministic partition-id ties; official std::sort equal-size ties may differ. Scores here use reference naive, not official Naive.',
         'meaning':'simulated IO+miss only, not real disk/end-to-end speed; development set, one training seed'})
    print(json.dumps(summaries),flush=True)


if __name__=='__main__':main()
