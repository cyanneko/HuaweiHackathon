"""Paired A/B/C full development trajectories with frozen zero-residual control."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import torch
from train import HERE,old,dump,sha
from closed_loop import load_model,run_case


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--models',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();args.out.mkdir(parents=True)
    torch.set_num_threads(1)
    frozen=json.loads((HERE/'closed_loop_v1/manifest.json').read_text())
    modes=['zero_residual','A_old','B_student_fixed','C_student_portfolio']
    models={name:load_model(args.models/name/'model.json') for name in modes[1:]}
    dump(args.out/'manifest.json',{'cases':frozen['cases'],'methods':modes,
         'model_hashes':{n:sha(args.models/n/'model.json') for n in modes[1:]},
         'same_dev_as_first_round':True,'budget_seconds':60,'formal_D':None})
    rows=[];start=time.perf_counter();deadline=start+60
    with torch.inference_mode():
        for meta in frozen['cases']:
            assert sha(meta['path'])==meta['sha256']
            case=old.core.Case.read(meta['path'])
            for name in modes:
                t=time.perf_counter();state,extra=run_case(case,name,models.get(name),deadline)
                witness=args.out/(meta['id']+'_'+name+'.witness.json');dump(witness,state.path)
                rows.append({'case_id':meta['id'],'family':meta['scenario'],'method':name,'input_sha256':case.input_hash,
                    'G':state.g,'cost_without_D':state.g/(case.w*case.r),'write_bytes':state.write,
                    'read_bytes':state.read,'misses':state.miss,'hits':state.hit,'callbacks':len(state.path),
                    'witness_sha256':sha(witness),'python_wall_seconds':time.perf_counter()-t,'formal_D':None,**extra})
                dump(args.out/'partial.json',rows)
            print(json.dumps({'completed_case':meta['id'],'seconds':time.perf_counter()-start}),flush=True)
    prior=json.loads((HERE/'closed_loop_v1/report.json').read_text())['results'];summary={}
    for name in modes:
        ratios=[];cases=[]
        for meta in frozen['cases']:
            lookup={r['method']:r for r in rows if r['case_id']==meta['id']}
            current=lookup[name];base=lookup['zero_residual'];ratio=current['G']/base['G']
            ratios.append(ratio);cases.append({'case_id':meta['id'],'ratio':ratio,'cost_delta_us':current['cost_without_D']-base['cost_without_D']})
            if name in ('zero_residual','A_old'):
                oldname='large_no_score_inputs' if name=='A_old' else name
                oldrow=next(r for r in prior if r['case_id']==meta['id'] and r['method']==oldname)
                for field in ('G','write_bytes','read_bytes','misses','hits','witness_sha256'):assert current[field]==oldrow[field],(name,meta['id'],field)
        summary[name]={'mean_ratio':float(np.mean(ratios)),'p50_ratio':float(np.quantile(ratios,.5)),
                       'p90_ratio':float(np.quantile(ratios,.9)),'worst_ratio':max(ratios),
                       'wins_losses_ties':[sum(r<1 for r in ratios),sum(r>1 for r in ratios),sum(r==1 for r in ratios)],'per_case':cases}
    dump(args.out/'report.json',{'status':'COMPLETE','results':rows,'summaries':summary,'seconds':time.perf_counter()-start,
         'original_A_and_zero_trajectories_exactly_reproduced':True,'quantiles':'numpy linear interpolation on 8 case ratios',
         'units':'simulated IO+miss, no D; developer-selected models on viewed dev; no holdout or generalization claim','formal_D':None})
    dump(args.out/'cpu_released.json',{'status':'RELEASED','seconds':time.perf_counter()-start})
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
