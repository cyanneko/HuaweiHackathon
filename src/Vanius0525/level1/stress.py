"""Maximum-N/K/P synthetic stress. Full framework unchanged; run without audit logs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from build import ROOT,build
from replay import parse_output
from workflow import experiment_lock


def generate(path,n=5000000,b=1,pattern='scan'):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():return
    # 512 one-MiB partitions; 64MiB memory, exact single-victim release.
    builds=512;probes=n-builds-8
    h=hashlib.sha256()
    with path.open('w') as f:
        def emit(line):f.write(line+'\n');h.update((line+'\n').encode())
        emit('8 64 67108864 10000 10000 1000');emit(f'{n} {b}')
        counts=[probes//8+int(o<probes%8) for o in range(8)]
        # Assign exact per-op totals for interleaving below.
        if pattern=='scan':
            counts=[0]*8
            cycles,rem=divmod(probes,512)
            for o in range(8):counts[o]=cycles*64+max(0,min(64,rem-o*64))
        for o in range(8):emit(f'{o} 64 {counts[o]}')
        for o in range(8):
            for pid in range(64):emit(f'INSERT {o} {pid} 1048576')
        for o in range(8):emit(f'SWITCH {o}')
        for j in range(probes):
            if pattern=='scan':o=(j//64)%8;pid=j%64
            else:o=j%8;pid=(j//8*17+13)%64
            emit(f'PROBE {o} {pid}')
    path.with_suffix('.meta.json').write_text(json.dumps({'n':n,'b':b,'pattern':pattern,'sha256':h.hexdigest(),'stress_only':True},indent=2)+'\n')

def main(n,bs,paths,out):
    results={'n':n,'runs':[]}
    exes={'naive':build()}
    exes.update({name:build(path,'stress_'+name) for name,path in paths.items()})
    for b in bs:
        case=ROOT/'build'/'stress'/f'scan_n{n}_b{b}.txt';generate(case,n,b)
        for name,exe in exes.items():
            start=time.perf_counter()
            try:
                proc=subprocess.run([str(exe),str(case)],capture_output=True,text=True,timeout=60)
                row={'name':name,'b':b,'wall_seconds':time.perf_counter()-start,'returncode':proc.returncode}
                if proc.returncode==0:row['metrics']=parse_output(proc.stdout)
                else:row['error']=proc.stderr[-1000:]
            except subprocess.TimeoutExpired:
                row={'name':name,'b':b,'wall_seconds':time.perf_counter()-start,'timeout':True}
            results['runs'].append(row);print(json.dumps(row),flush=True)
            out=Path(out);out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--n',type=int,default=5000000);p.add_argument('--b',type=int,nargs='+',default=[1,10000]);p.add_argument('--scheduler',action='append',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    with experiment_lock():main(a.n,a.b,dict(x.split('=',1) for x in a.scheduler),a.out)
