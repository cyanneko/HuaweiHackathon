"""Expanded fixed-label diagnostics: distinguish all-tie rows and real G gaps."""
import json
import torch
from train import HERE,WS,load_explicit,dump,old
from closed_loop import load_model


def describe(rows,model):
    groups={'all':[],'non_tie':[],'all_tie':[]}
    with torch.inference_mode():
        for row in rows:
            ps=row['plans'];xs=torch.tensor([p['x'] for p in ps])
            scores=model(xs).tolist() if model else xs[:,13].tolist()
            j=min(range(len(ps)),key=lambda i:(scores[i],ps[i]['tie']))
            item={'case_id':row['case_id'],'anchor':row['anchor_snapshot_sha256'],
                  'best_set_hit':ps[j]['regret_integer']==0,'normalized_regret':ps[j]['target'],
                  'G_regret':ps[j]['regret_integer'],'selected_action':ps[j]['action_key']}
            groups['all'].append(item);groups['non_tie' if row['integer_gap_scale'] else 'all_tie'].append(item)
    summary={}
    for name,items in groups.items():
        n=len(items);summary[name]={'count':n,'best_set_hits':sum(x['best_set_hit'] for x in items),
          'mean_normalized_regret':sum(x['normalized_regret'] for x in items)/n if n else None,
          'mean_G_regret':sum(x['G_regret'] for x in items)/n if n else None}
    return {'summary':summary,'rows':groups['all']}


def main():
    torch.set_num_threads(1)
    inv=json.loads((HERE/'train_inventory.json').read_text())
    bounds=json.loads((WS/'tmp/handler_support/data_contract/split_boundaries.json').read_text())
    train=load_explicit(inv['cases'],'train');dev=load_explicit(bounds['r70_labeled_dev_cases'],'dev')
    # Read only explicit train and labeled dev headers to establish G units.
    scales={}
    for split,rows in [('train',train),('dev',dev)]:
        for case_id in sorted({r['case_id'] for r in rows}):
            path=WS/'tmp/r70_inputs/data'/split/(case_id+'.txt')
            with path.open() as stream:header=list(map(int,stream.readline().split()))
            # Case.read convention: K P M W R penalty period.
            scales[case_id]=header[3]*header[4]
    models=['zero_residual']+[s['name'] for s in json.loads((HERE/'model_protocol.json').read_text())['models']]
    result={}
    for name in models:
        model=None if name=='zero_residual' else load_model(HERE/'gpu_fixed_v1'/name/'model.json')
        item={split:describe(rows,model) for split,rows in [('train',train),('dev',dev)]}
        for split in item:
            for r in item[split]['rows']:r['regret_us']=r['G_regret']/scales[r['case_id']]
            rows2=item[split]['rows'];bycase={}
            for r in rows2:bycase.setdefault(r['case_id'],[]).append(r['regret_us'])
            item[split]['mean_case_regret_us']=sum(sum(v)/len(v) for v in bycase.values())/len(bycase)
        result[name]=item
    dump(HERE/'gpu_fixed_v1/expanded_label_metrics.json',{'units':'simulated IO+miss microseconds, excluding D','G_scales':scales,'methods':result})


if __name__=='__main__':main()
