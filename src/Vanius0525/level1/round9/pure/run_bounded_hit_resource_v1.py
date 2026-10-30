import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from run_diagnostic_v2 import sha, put, compile_text


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    names=['BOUNDED_HIT_RESOURCE_PLAN_V1.md','bounded_hit_v1.hpp','bounded_hit_resource_v1.cpp','run_bounded_hit_resource_v1.py']
    frozen=HERE/'BOUNDED_HIT_RESOURCE_FREEZE_V1.json'
    if args.freeze:
        assert not frozen.exists();put(frozen,{'files':{n:sha(HERE/n) for n in names},'no_scheduler_or_penalty':True});print('Independent kernel resource check frozen.');return
    f=json.loads(frozen.read_text())
    for n,h in f['files'].items():assert sha(HERE/n)==h,n
    folder=ROOT/'build/round9_pure_bounded_hit_resource_v1';folder.mkdir(parents=True,exist_ok=True)
    source=(HERE/'bounded_hit_resource_v1.cpp').read_text().replace('// RESOURCE_HEADER',(HERE/'bounded_hit_v1.hpp').read_text())
    rows=[]
    with experiment_lock():
        exe=compile_text(folder,'bounded_resource',source)
        process=subprocess.Popen([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        for line in process.stdout:
            row=json.loads(line);rows.append(row);print('resource',row['period'],row['repeat'],'cpu_us',row['process_cpu_us'],flush=True)
            put(folder/'progress.json',{'complete':False,'rows':rows})
        error=process.stderr.read();assert process.wait()==0,error
    assert len(rows)==6 and all(x['sizeof_estimator']<=65536 and x['max_blocks']<=256 for x in rows)
    assert all(x['probes']==4999480 and x['fits']<=1+x['probes']//1024 for x in rows)
    assert all(x['anonymous']==0 and x['em_fits']==0 for x in rows if x['period']==1)
    assert all(x['anonymous']>0 and x['em_fits']>0 for x in rows if x['period']==17)
    for n,h in f['files'].items():assert sha(HERE/n)==h
    result={'complete':True,'no_scheduler_or_penalty':True,'scope':'Independent statistical kernel resource check, no policy scores or 100-proxy closed-loop evidence.',
            'rows':rows,'median_by_period':{str(b):{'process_cpu_us':statistics.median(x['process_cpu_us'] for x in rows if x['period']==b),
                'wall_us':statistics.median(x['wall_us'] for x in rows if x['period']==b)} for b in (1,17)}}
    put(HERE/'BOUNDED_HIT_RESOURCE_RESULTS_V1.json',result);print(json.dumps(result['median_by_period']),flush=True)


if __name__=='__main__':main()
