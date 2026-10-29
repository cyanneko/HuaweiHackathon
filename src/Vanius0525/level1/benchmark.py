"""Serial, paired uninstrumented timing; separate independent action audit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import time
from build import build,ROOT
from replay import parse_input,parse_output,replay


def run(exe,case):
    start=time.perf_counter();p=subprocess.run([str(exe),str(case)],capture_output=True,text=True,timeout=60)
    wall=time.perf_counter()-start
    if p.returncode:raise RuntimeError(f'{exe.name} {case.name}: {p.returncode}: {p.stderr[:2000]}')
    return parse_output(p.stdout),wall,p

def benchmark(data,schedulers,repeats=3,audit=True,out=None):
    cases=sorted(Path(data).glob('*.txt'));assert cases
    parsed={case.name:parse_input(case)[0] for case in cases}
    executables={'naive':build()}
    for name,path in schedulers.items():executables[name]=build(path,name)
    audit_exe={name:build(path,name,audit=True) for name,path in schedulers.items()} if audit else {}
    record={'benchmark_schema':2,'score_repetition_order':'per case per repetition clamp, then sum/cap each repetition, then average', 'platform':platform.platform(),'cpu':platform.processor(),'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
            'repeats':repeats,'protocol':'saved-2026-10-20-reference','cases':[],'scheduler_sha256':{n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in schedulers.items()}}
    rng=random.Random(290029)
    for i,case in enumerate(cases):
        c={'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'penalty':parsed[case.name][5],'runs':{n:[] for n in executables},'audit':{}}
        for name,exe in audit_exe.items():
            res,wall,proc=run(exe,case);c['audit'][name]=replay(case,proc.stderr,proc.stdout)
        for repeat in range(repeats):
            order=list(executables);rng.shuffle(order)
            for name in order:
                res,wall,_=run(executables[name],case);res['wall_seconds']=wall;c['runs'][name].append(res)
        record['cases'].append(c)
        if i%8==0: print(f'completed {i+1}/{len(cases)}',flush=True)
    summary={}
    for name in executables:
        scores=[];env_scores=[];ratios=[];worst=[];repeat_sums=[0.0]*repeats;miss=io=decision=cost=0
        for c in record['cases']:
            val=statistics.mean(x['Total_Score'] for x in c['runs'][name]);base=statistics.mean(x['Total_Score'] for x in c['runs']['naive'])
            rs=[]
            for rep in range(repeats):
                rv=c['runs'][name][rep]['Total_Score'];rb=c['runs']['naive'][rep]['Total_Score']
                sc=max(0,min(10,10*(1-rv/rb))) if rb and rv else 0
                rs.append(sc);repeat_sums[rep]+=sc
            score=statistics.mean(rs)
            ve=statistics.mean(x['Total_IO_Time']+c['penalty']*x['Miss_Count'] for x in c['runs'][name])
            be=statistics.mean(x['Total_IO_Time']+c['penalty']*x['Miss_Count'] for x in c['runs']['naive'])
            env_scores.append(max(0,min(10,10*(1-ve/be))) if be else 0)
            scores.append(score);ratios.append(val/base if base else 1)
            worst.append((val/base if base else 1,c['file']))
            miss+=statistics.mean(x['Miss_Count'] for x in c['runs'][name]);io+=statistics.mean(x['Total_IO_Time'] for x in c['runs'][name]);decision+=statistics.mean(x['Total_Decision_Time'] for x in c['runs'][name]);cost+=val
        summary[name]={'cases':len(cases),'mean_single_score':statistics.mean(scores),'capped_sum_score':statistics.mean(min(50,x) for x in repeat_sums),
                       'mean_io_miss_score_diagnostic':statistics.mean(env_scores),'io_miss_diagnostic_excludes_decision':True,
                       'mean_cost_ratio':statistics.mean(ratios),'wins':sum(x<1 for x in ratios),'regressions_gt_1pct':sum(x>1.01 for x in ratios),
                       'misses':miss,'io':io,'decision':decision,'total_cost':cost,'worst_cost_ratios':sorted(worst,reverse=True)[:6]}
    record['summary']=summary
    if out:
        out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--scheduler',action='append',required=True,help='name=path')
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--no-audit',action='store_true');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    from workflow import experiment_lock
    with experiment_lock():
        benchmark(a.data,dict(x.split('=',1) for x in a.scheduler),a.repeats,not a.no_audit,a.out)
