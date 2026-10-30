"""Explicit train-only CUDA experiment; no discovery of holdout files."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import numpy as np
import torch
from model import PlanRanker, ranking_loss

HERE = Path(__file__).resolve().parent
WS = HERE.parents[4]
sys.path.insert(0, str(WS/'tmp/r70_nn_pipeline'))
import pipeline as old


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n', encoding='utf8')


def load_explicit(cases, split, validate_states=False):
    rows=[]; seen=set()
    for meta in cases:
        assert meta['split']==split
        path=Path(meta['label_path_windows'])
        assert sha(path)==meta['label_sha256']
        case=None
        if validate_states:
            assert sha(meta['input_path_windows'])==meta['input_sha256']
            case=old.core.Case.read(meta['input_path_windows'])
        for line in path.read_text(encoding='utf8').splitlines():
            row=json.loads(line)
            assert row['split']==split and row['case_id']==meta['case_id']
            assert row['input_sha256']==meta['input_sha256']
            assert row['modulo_operation_sha256']==meta['modulo_operation_sha256']
            assert row['feature_version']==old.FEATURE_VERSION and row['feature_names']==old.FEATURE_NAMES
            assert old.digest(row['anchor_snapshot'])==row['anchor_snapshot_sha256']
            key=(row['case_id'],row['anchor_snapshot_sha256'])
            assert key not in seen;seen.add(key)
            plans=row['plans'];assert 2<=len(plans)<=8
            # Paired experiment only uses full rows; never silently substitute missing costs.
            assert all(p['valid_cost'] and p['cost']['status']=='complete' for p in plans)
            costs=[p['cost']['G_delta'] for p in plans]
            assert all(type(v) is int and v>=0 for v in costs)
            gap=max(costs)-min(costs);assert gap==row['integer_gap_scale']
            for p,g in zip(plans,costs):
                assert p['regret_integer']==g-min(costs)
                assert p['target']==((g-min(costs))/gap if gap else 0.)
            if case is not None:
                state=old.core.State.from_snapshot(case,row['anchor_snapshot'])
                actions=old.core.pool(state);features=old.features(state,actions)
                assert len(actions)==len(plans)
                assert list(old.core.next_public(state))==row['public_next_op']
                for a,x,p in zip(actions,features,plans):
                    assert list(a)==p['spill'] and old.bits(x)==old.bits(p['x'])
                    assert p['tie']==[len(a),sum(state.sizes[i] for i in a),list(a)]
                    cost=p['cost']
                    assert cost['G_delta']==cost['write_bytes']*case.r+cost['read_bytes']*case.w+case.penalty*cost['misses']*case.w*case.r
                    old.core.State.from_snapshot(case,row['anchor_snapshot']).apply(a)
            rows.append(row)
    return rows


def tensors(rows, device):
    counts=Counter(r['case_id'] for r in rows if r['integer_gap_scale']>0)
    x=np.zeros((len(rows),8,32),np.float32)
    y=np.zeros((len(rows),8),np.float32);valid=np.zeros((len(rows),8),bool)
    for i,row in enumerate(rows):
        for j,p in enumerate(row['plans']):
            x[i,j]=p['x'];y[i,j]=p['target'];valid[i,j]=True
    weights=np.array([1/counts[r['case_id']] if r['integer_gap_scale']>0 else 0 for r in rows],np.float32)
    assert weights.sum()>0;weights/=weights.sum()
    assert np.isfinite(x).all() and np.isfinite(y).all()
    return tuple(torch.as_tensor(v,device=device) for v in (x,y,valid,weights))


def label_diagnostics(model, rows):
    x,_,_,_=tensors(rows,'cpu')
    with torch.inference_mode():scores=model.cpu()(x).tolist()
    cases={};best=0;norm=[]
    for row,ss in zip(rows,scores):
        ps=row['plans'];idx=min(range(len(ps)),key=lambda j:(ss[j],ps[j]['tie']))
        delta=ps[idx]['regret_integer'];best+=delta==0;norm.append(ps[idx]['target'])
        cases.setdefault(row['case_id'],[]).append(delta)
    return {'rows':len(rows),'known_best_count':best,'mean_normalized_regret':sum(norm)/len(norm),
            'mean_integer_G_regret_by_case':{k:sum(v)/len(v) for k,v in cases.items()},
            'meaning':'fixed-continuation same-state labels; not closed-loop policy performance'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--validate-only',action='store_true');args=ap.parse_args()
    assert not args.out.exists(),'immutable experiment output already exists'
    args.out.mkdir(parents=True)
    protocol=json.loads((HERE/'model_protocol.json').read_text())
    inventory=json.loads((HERE/'train_inventory.json').read_text())
    boundaries=json.loads((WS/'tmp/handler_support/data_contract/split_boundaries.json').read_text())
    rows=load_explicit(inventory['cases'],'train',True)
    dev=load_explicit(boundaries['r70_labeled_dev_cases'],'dev')
    assert not {r['case_id'] for r in rows}&{r['case_id'] for r in dev}
    gate={'passed':True,'train_cases':24,'train_rows':len(rows),'dev_rows':len(dev),
          'train_inventory_sha256':sha(HERE/'train_inventory.json'),'protocol_sha256':sha(HERE/'model_protocol.json'),
          'label_source':'fixed R70 labels_v3 only; no portfolio substitution',
          'every_suffix_independently_official_replayed':False,'holdout_read':False}
    dump(args.out/'gate.json',gate)
    if args.validate_only:print(json.dumps(gate));return
    if not torch.cuda.is_available():raise RuntimeError('Actual training requires CUDA')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False
    x,y,valid,weights=tensors(rows,'cuda');all_reports=[]
    deadline=time.perf_counter()+300
    for spec in protocol['models']:
        seed=protocol['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        model=PlanRanker(spec['hidden'],spec['zero_columns'],spec['base_skip']).cuda()
        opt=torch.optim.Adam(model.parameters(),lr=protocol['learning_rate'],weight_decay=protocol['weight_decay'])
        observable=model.observable(x);losses=[]
        torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
        for epoch in range(protocol['epochs']):
            if time.perf_counter()>=deadline:
                dump(args.out/'budget_stop.json',{'status':'INCOMPLETE','current_model':spec['name'],'completed_epochs':epoch,'completed_models':[r['name'] for r in all_reports]})
                raise TimeoutError('Shared 300 second training budget exhausted; no automatic retry')
            opt.zero_grad(set_to_none=True)
            loss=ranking_loss(model(x),y,valid,observable,weights)
            if not torch.isfinite(loss):raise ValueError('nonfinite training loss')
            loss.backward();opt.step();losses.append(float(loss.detach()))
        torch.cuda.synchronize();seconds=time.perf_counter()-start
        out=args.out/spec['name'];out.mkdir()
        exported=model.export();exported.update(feature_version=old.FEATURE_VERSION,protocol_sha256=sha(HERE/'model_protocol.json'))
        dump(out/'model.json',exported);torch.save(model.cpu().state_dict(),out/'weights.pt')
        with torch.inference_mode():
            dx,dy,dv,dw=tensors(dev,'cpu')
            dev_loss=float(ranking_loss(model(dx),dy,dv,model.observable(dx),dw))
            tx,ty,tv,tw=tensors(rows,'cpu')
            final_train_loss=float(ranking_loss(model(tx),ty,tv,model.observable(tx),tw))
        report={'name':spec['name'],'status':'CUDA_TRAINED_PENDING_CLOSED_LOOP',
                'seconds':seconds,'epochs':protocol['epochs'],'seed':seed,'losses':losses,
                'parameters':exported['parameters'],'macs_per_plan':exported['macs_per_plan'],
                'device':torch.cuda.get_device_name(0),'torch_version':torch.__version__,
                'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                'model_sha256':sha(out/'model.json'),'formal_D':None,
                'final_train_loss':final_train_loss,'final_dev_loss':dev_loss,
                'train':label_diagnostics(model,rows),'dev':label_diagnostics(model,dev)}
        dump(out/'training_report.json',report);all_reports.append(report)
        print(json.dumps({k:report[k] for k in ('name','seconds','parameters','train','dev')}),flush=True)
    dump(args.out/'summary.json',{'gate':gate,'runs':all_reports,'training_sources':
         {p.name:sha(p) for p in (HERE/'train.py',HERE/'model.py',HERE/'model_protocol.json')}})


if __name__=='__main__':main()
