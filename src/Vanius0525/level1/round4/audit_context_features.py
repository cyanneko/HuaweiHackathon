"""Audit derived training features against exact float32 arithmetic used at runtime."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import sys,json,hashlib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
with experiment_lock():
    output={}
    reports=[('front','context_train','CONTEXT_TRAINING.json'),('strat','context_stratified_train','CONTEXT_STRAT_TRAINING.json')]
    for label,folder,reportname in reports:
        report=json.loads((ROOT/'round4'/reportname).read_text());old=np.load(ROOT/'build/round4'/folder/'rows.npz');xx=[];yy=[];gg=[]
        cases=sorted((ROOT/'build/data/train').glob('*.txt'))
        for d in ['fresh','ood']:cases+=sorted((ROOT/'build/round4/context_train'/d).glob('*.txt'))
        for group,case in enumerate(cases):
            assert hashlib.sha256(case.read_bytes()).hexdigest()==report['sources'][group]['sha256']
            header=list(map(int,case.open().readline().split()));norm=header[2]*(1/header[3]+1/header[4])
            path=ROOT/'build/round4'/folder/(f'{group:03}_'+case.stem+'.rows')
            for line in path.read_text().splitlines():
                if not line.startswith('ROW '):continue
                vals=np.asarray(list(map(float,line.split()[2:])),np.float64);assert len(vals)==48
                context=vals[:12].astype(np.float32);loss=vals[12:16];af=vals[16:].astype(np.float32).reshape(4,8)
                for mode in [2,3]:
                    if np.array_equal(af[mode],af[0]):continue
                    xx.append(np.concatenate([context,af[mode],af[mode]-af[0],[np.log2(header[4]/header[3])/14.,np.log2(header[3])/14.]]));yy.append(np.clip((loss[mode]-loss[0])/max(1.,norm),-20,20));gg.append(group)
        x=np.asarray(xx,np.float32);y=np.asarray(yy,np.float32);g=np.asarray(gg)
        assert x.shape==old['x'].shape and np.array_equal(y,old['y']) and np.array_equal(g,old['groups'])
        changed=x.view(np.uint32)!=old['x'].view(np.uint32)
        diff=np.abs(x.astype(np.float64)-old['x'].astype(np.float64))
        output[label]={'rows':len(x),'rows_with_bit_difference':int(changed.any(1).sum()),'entries_different':int(changed.sum()),'different_per_feature':changed.sum(0).tolist(),'max_abs_difference':float(diff.max()),'labels_and_groups_identical':True,'corrected_feature_sha256':hashlib.sha256(x.tobytes()).hexdigest()}
        np.savez_compressed(ROOT/'build/round4'/folder/'rows_exact_features.npz',x=x,y=y,groups=g)
    output['scope']='Restoring logged float32 inputs before subtraction matches C++ float arithmetic. This quantifies feature differences, not whether any learned tree decision changes.'
    (ROOT/'round4/CONTEXT_FEATURE_PARITY.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
