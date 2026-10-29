"""Reproducible edge cases, exact oracle checks and sanitizers; no engine edits."""
import argparse
import json
from pathlib import Path
import random
import subprocess
from build import ROOT,build
from replay import parse_input,parse_output,replay
from oracle import optimal

MIB=1<<20

def write(name,k,p,m,ops,b=1,w=1000,r=1000,penalty=1000):
    heads=[]
    for o in range(k):
        heads.append((o,sum(x[0]=='INSERT' and x[1]==o for x in ops),sum(x[0]=='PROBE' and x[1]==o for x in ops)))
    lines=[f'{k} {p} {m} {w} {r} {penalty}',f'{len(ops)} {b}']
    lines+=[' '.join(map(str,x)) for x in heads+ops]
    out=ROOT/'build'/'edges';out.mkdir(exist_ok=True)
    path=out/(name+'.txt');data='\n'.join(lines)+'\n'
    if path.exists():assert path.read_text()==data
    else:path.write_text(data)
    parse_input(path);return path

def cases():
    out=[]
    # Exactly fitting capacity, empty partitions, repeated key, terminal periodic.
    out.append(write('all_empty',1,4,64*MIB,[('SWITCH',0)]+[('PROBE',0,2)]*10))
    out.append(write('end_insert',1,2,64*MIB,[('INSERT',0,0,MIB)]*64,b=1))
    # 64-bit M and accumulated bytes; resident total far above 32-bit if spilled.
    ops=[('INSERT',o,pid,MIB) for o in range(2) for pid in range(4) for j in range(513)]
    ops+=[('SWITCH',0),('SWITCH',1)]+[('PROBE',o,pid) for o in range(2) for pid in range(4)]*4
    out.append(write('int64',2,4,3*(1<<30),ops,b=8))
    # Protected target close to M; spilling another partition is essential.
    ops=[('INSERT',0,1,MIB)]*16+[('INSERT',0,0,MIB)]*60+[('SWITCH',0)]+[('PROBE',0,i%2) for i in range(20)]
    out.append(write('protected_target',1,2,64*MIB,ops,b=7))
    # Mixed BUILD/PROBE, disk append, SWITCH as next, no periodic until end.
    ops=[('INSERT',0,0,MIB)]*40+[('INSERT',1,1,MIB)]*40+[('SWITCH',0)]
    ops+=[('PROBE',0,0),('INSERT',1,1,MIB)]*12+[('SWITCH',1)]+[('PROBE',1,1),('PROBE',0,0)]*8
    out.append(write('mixed_phases',2,2,64*MIB,ops,b=10000))
    # Accurate one-step prefetch can lose the next lookahead at the later miss.
    ops=[('INSERT',0,pid,MIB) for pid in [0,1,2] for _ in range(32)]
    ops += [('SWITCH',0)]+[('PROBE',0,1)]*32+[('PROBE',0,0),('PROBE',0,1)]
    out.append(write('opaque_hit_prefetch',1,3,64*MIB,ops,b=32))
    rng=random.Random(290029)
    for seed in range(12):
        ops=[]
        for pid in range(4):ops += [('INSERT',0,pid,MIB)]*rng.choice([12,20,28])
        rng.shuffle(ops);ops += [('SWITCH',0)]
        seq=([i%4 for i in range(20)] if seed%3==0 else [rng.randrange(4) for _ in range(20)])
        ops += [('PROBE',0,pid) for pid in seq]
        out.append(write(f'oracle_{seed:02}',1,4,64*MIB,ops,b=[1,3,10000][seed%3]))
    return out

def main(schedulers,sanitize=False):
    report={'cases':[],'sanitizers':sanitize}
    # Compile one variant at a time, then run all cases with a fresh instance.
    inputs=cases()
    for name,path in schedulers.items():
        exe=build(path,name,audit=True,sanitize=sanitize)
        for case in inputs:
            proc=subprocess.run([str(exe),str(case)],capture_output=True,text=True,timeout=60)
            assert proc.returncode==0,(name,case.name,proc.stderr[-3000:])
            audit=replay(case,proc.stderr,proc.stdout);res=parse_output(proc.stdout)
            row={'scheduler':name,'case':case.name,'audit':audit}
            if case.name.startswith('oracle_'):
                opt=optimal(case);actual=res['Total_IO_Time']+parse_input(case)[0][5]*res['Miss_Count']
                assert actual+.011>=opt['optimal_io_plus_miss'],(actual,opt)
                row['oracle']=opt;row['cost_excluding_decision']=actual
            report['cases'].append(row)
    target=ROOT/'results'/('edges_sanitize.json' if sanitize else 'edges.json');target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'runs':len(report['cases']),'all_passed':True,'sanitizers':sanitize}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scheduler',action='append',required=True);p.add_argument('--sanitize',action='store_true');a=p.parse_args();main(dict(x.split('=',1) for x in a.scheduler),a.sanitize)
