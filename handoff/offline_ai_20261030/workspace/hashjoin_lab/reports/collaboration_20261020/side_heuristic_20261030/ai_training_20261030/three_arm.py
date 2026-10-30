"""Predeclared student-state and continuation-label experiment, same network."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
import numpy as np
import torch
from model import PlanRanker,ranking_loss
from train import HERE,WS,old,sha,dump,load_explicit,tensors,label_diagnostics


def new_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines()]


def identity(row):return row['case_id'],row['anchor_snapshot_sha256']


def tensor_hash(value):
    value=value.detach().cpu().contiguous()
    header=json.dumps({'shape':list(value.shape),'dtype':str(value.dtype)},sort_keys=True).encode()
    return hashlib.sha256(header+value.numpy().tobytes()).hexdigest()


def check_new(fixed,portfolio,selection,inventory):
    selected={identity(row):(row,case) for case in selection['cases'] for row in case['anchors']}
    assert len(selected)==selection['rows']
    f={identity(r):r for r in fixed};p={identity(r):r for r in portfolio}
    assert len(f)==len(fixed) and len(p)==len(portfolio) and f.keys()==p.keys()
    assert f.keys()<=selected.keys()
    originals={c['case_id']:c for c in inventory['cases']};loaded={}
    for key in f:
        frozen,meta=selected[key];case_meta=originals[key[0]]
        assert meta['input_sha256']==case_meta['input_sha256']
        if key[0] not in loaded:loaded[key[0]]=old.core.Case.read(meta['input_path'])
        case=loaded[key[0]];state=old.core.State.from_snapshot(case,frozen['anchor_snapshot'])
        plans=old.core.pool(state);xs=old.features(state,plans)
        for row in (f[key],p[key]):
            assert row['paired_matrix_complete'] is True
            assert row['label_protocol_version']=='handler-student48-paired-v1'
            assert row['split']=='train' and row['feature_version']==old.FEATURE_VERSION
            assert row['feature_names']==old.FEATURE_NAMES
            assert row['input_sha256']==case.input_hash and row['anchor_snapshot']==frozen['anchor_snapshot']
            assert row['candidate_pool_version']==old.core.POOL_VERSION and len(row['plans'])==len(plans)
            costs=[]
            for a,x,q,z in zip(plans,xs,row['plans'],frozen['plans']):
                assert q['legal'] and q['valid_cost'] and q['cost']['status']=='complete'
                assert list(a)==q['spill']==z['spill'] and q['tie']==z['tie']
                assert old.bits(x)==old.bits(q['x'])==old.bits(z['x'])
                cost=q['cost'];g=cost['G_delta'];assert type(g) is int and g>=0
                assert g==cost['write_bytes']*case.r+cost['read_bytes']*case.w+case.penalty*cost['misses']*case.w*case.r
                costs.append(g)
            gap=max(costs)-min(costs);assert gap==row['integer_gap_scale']
            for q,g in zip(row['plans'],costs):
                assert q['regret_integer']==g-min(costs) and q['target']==((g-min(costs))/gap if gap else 0.)
        for a,b in zip(f[key]['plans'],p[key]['plans']):assert b['cost']['G_delta']<=a['cost']['G_delta']
        assert f[key]['continuation']==meta['fixed_method']==case_meta['teacher_method']
    return sorted(f.values(),key=identity),sorted(p.values(),key=identity)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fixed',type=Path,required=True);ap.add_argument('--portfolio',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists();args.out.mkdir(parents=True)
    assert args.fixed.parent.resolve()==args.portfolio.parent.resolve()
    audit_path=args.fixed.parent/'artifact_audit.json';audit=json.loads(audit_path.read_text())
    assert audit['status']=='paired_label_artifact_audit_passed'
    assert sha(args.fixed)==audit['fixed_labels_sha256'] and sha(args.portfolio)==audit['portfolio_labels_sha256']
    assert sha(args.fixed.parent/'report.json')==audit['report_sha256']
    assert json.loads((args.fixed.parent/'cpu_released.json').read_text())['status']=='RELEASED'
    selection=json.loads((HERE/'student48/selection.json').read_text())
    provenance=json.loads((HERE/'student48/source_provenance.json').read_text())
    for relative,expected in provenance['dependencies'].items():assert sha(WS/relative)==expected
    for relative,expected in provenance['local_sources'].items():assert sha(HERE/relative)==expected
    inv=json.loads((HERE/'train_inventory.json').read_text());base=load_explicit(inv['cases'],'train')
    bounds=json.loads((WS/'tmp/handler_support/data_contract/split_boundaries.json').read_text())
    dev=load_explicit(bounds['r70_labeled_dev_cases'],'dev')
    fixed,portfolio=check_new(new_rows(args.fixed),new_rows(args.portfolio),selection,inv)
    assert not ({identity(r) for r in base}&{identity(r) for r in fixed})
    assert len(fixed)>0
    gate={'old_rows':len(base),'new_common_complete_rows':len(fixed),'selected_rows':selection['rows'],
          'excluded_new_rows':selection['rows']-len(fixed),'train_cases':24,'dev_rows':len(dev),
          'fixed_labels_sha256':sha(args.fixed),'portfolio_labels_sha256':sha(args.portfolio),
          'teacher_artifact_audit_sha256':sha(audit_path),
          'selection_sha256':sha(HERE/'student48/selection.json'),'protocol_sha256':sha(HERE/'student48/protocol.json'),
          'B_C_same_anchor_identities':True,'row_missing_fill':False,'holdout_read':False}
    gate['training_source_sha256']=sha(Path(__file__))
    gate['model_source_sha256']=sha(HERE/'model.py')
    dump(args.out/'gate.json',gate)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
    assert torch.cuda.is_available()
    reports=[];deadline=time.perf_counter()+300;initial_hashes=[]
    for name,rows in [('A_old',base),('B_student_fixed',base+fixed),('C_student_portfolio',base+portfolio)]:
        seed=20261030;random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        x,y,valid,weights=tensors(rows,'cuda');model=PlanRanker([256,128],[13,28,30,31],True).cuda()
        initial={key:tensor_hash(value) for key,value in model.state_dict().items()}
        initial_hashes.append(initial)
        assert all(item==initial for item in initial_hashes)
        data_hashes={key:tensor_hash(value) for key,value in zip(('x','targets','valid','case_weights'),(x,y,valid,weights))}
        case_weight_sums={}
        for row,weight in zip(rows,weights.detach().cpu().tolist()):
            case_weight_sums[row['case_id']]=case_weight_sums.get(row['case_id'],0.)+weight
        assert len(case_weight_sums)==24 and max(case_weight_sums.values())-min(case_weight_sums.values())<1e-6
        opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=0);obs=model.observable(x);losses=[]
        torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
        for epoch in range(200):
            if time.perf_counter()>deadline:raise TimeoutError('Shared 300 second GPU budget')
            opt.zero_grad(set_to_none=True);loss=ranking_loss(model(x),y,valid,obs,weights)
            assert torch.isfinite(loss);loss.backward();opt.step();losses.append(float(loss.detach()))
        torch.cuda.synchronize();seconds=time.perf_counter()-start
        data=model.export();data.update(feature_version=old.FEATURE_VERSION,protocol_sha256=gate['protocol_sha256'])
        out=args.out/name;out.mkdir();dump(out/'model.json',data);torch.save(model.cpu().state_dict(),out/'weights.pt')
        if name=='A_old':
            oldmodel=json.loads((HERE/'gpu_fixed_v1/large_no_score_inputs/model.json').read_text())
            assert data['layers']==oldmodel['layers'],'A failed exact original control reproduction'
        with torch.inference_mode():
            tx,ty,tv,tw=tensors(rows,'cpu');dx,dy,dv,dw=tensors(dev,'cpu')
            train_loss=float(ranking_loss(model(tx),ty,tv,model.observable(tx),tw))
            dev_loss=float(ranking_loss(model(dx),dy,dv,model.observable(dx),dw))
        report={'name':name,'status':'CUDA_TRAINED_CLOSED_LOOP_PENDING','rows':len(rows),'seed':seed,'epochs':200,
                'informative_rows':sum(r['integer_gap_scale']>0 for r in rows),'all_tie_rows':sum(r['integer_gap_scale']==0 for r in rows),
                'seconds':seconds,'losses':losses,'train_loss':train_loss,'dev_loss':dev_loss,
                'parameters':data['parameters'],'macs_per_plan':data['macs_per_plan'],
                'device':torch.cuda.get_device_name(0),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                'initial_parameter_tensor_hashes':initial,'training_tensor_hashes':data_hashes,'case_weight_sums':case_weight_sums,
                'model_sha256':sha(out/'model.json'),'train':label_diagnostics(model,rows),'dev':label_diagnostics(model,dev),
                'formal_D':None,'case_weighting':'equal original informative cases, within-case inverse informative-row count'}
        dump(out/'training_report.json',report);reports.append(report)
        print(json.dumps({'name':name,'rows':len(rows),'seconds':seconds,'train_loss':train_loss,'dev_loss':dev_loss}),flush=True)
    dump(args.out/'summary.json',{'gate':gate,'runs':reports,'A_exact_original_weights_reproduced':True,'all_initial_parameter_tensors_identical':True})


if __name__=='__main__':main()
