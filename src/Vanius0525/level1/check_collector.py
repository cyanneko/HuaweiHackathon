"""Confirm frozen legal feature extractor reproduces the original fit arrays."""
import hashlib
import json
import subprocess
import numpy as np
import sklearn
from build import ROOT,build
from workflow import experiment_lock

if __name__=='__main__':
    with experiment_lock():
        exe=build(ROOT/'collector_v1.cpp','collector_reproduction')
        cached=np.load(ROOT/'build/train_features.npz');all_rows=[];groups=[]
        for g,case in enumerate(sorted((ROOT/'build/data/train').glob('*.txt'))):
            p=subprocess.run([str(exe),str(case)],capture_output=True,text=True,check=True,timeout=60)
            for line in p.stderr.splitlines():
                if line.startswith('FEATURE '):all_rows.append(list(map(float,line.split()[4:])));groups.append(g)
        x=np.asarray(all_rows,dtype=np.float32);g=np.asarray(groups)
        assert np.array_equal(x,cached['x']) and np.array_equal(g,cached['groups'])
        report={'rows_exactly_reproduced':len(x),'all_features_bitwise_equal_after_float32_parse':True,'numpy':np.__version__,'sklearn':sklearn.__version__,
                'frozen_collector_sha256':hashlib.sha256((ROOT/'collector_v1.cpp').read_bytes()).hexdigest(),'scope':'original training feature arrays, legal callback input only; original labels unchanged'}
        (ROOT/'TRAINING_REPRO.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
