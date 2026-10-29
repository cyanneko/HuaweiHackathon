"""Validate a 100%-accurate prefetch counterexample caused by lost lookahead."""
import json
from pathlib import Path
import subprocess
from build import ROOT,build
from check_edges import cases
from replay import parse_input,parse_output,replay
from oracle import optimal
from workflow import experiment_lock


def main():
    case=next(x for x in cases() if x.name=='opaque_hit_prefetch.txt')
    fixtures=ROOT/'test_cases';fixtures.mkdir(exist_ok=True)
    fixture=fixtures/case.name
    if fixture.exists():assert fixture.read_bytes()==case.read_bytes()
    else:fixture.write_bytes(case.read_bytes())
    penalty=parse_input(case)[0][5];result={'case':case.name,'penalty':penalty,'runs':{}}
    for name,path in [('always',ROOT/'pure_cycle_fast.cpp'),('adaptive',ROOT/'MySpillScheduler.cpp')]:
        exe=build(path,'counterexample_'+name,True)
        proc=subprocess.run([str(exe),str(case)],capture_output=True,text=True,check=True)
        audit=replay(case,proc.stderr,proc.stdout);res=parse_output(proc.stdout)
        result['runs'][name]={'io_plus_miss':res['Total_IO_Time']+penalty*res['Miss_Count'],'io':res['Total_IO_Time'],'misses':res['Miss_Count'],'audit':audit}
    result['oracle']=optimal(case)
    gap=result['runs']['always']['io_plus_miss']-result['runs']['adaptive']['io_plus_miss']
    expected=2*32*(1<<20)/1000
    assert abs(gap-expected)<.02,(gap,expected)
    result['extra_cost']=gap;result['expected_extra_roundtrip']=expected
    result['mechanism']='At periodic: next=C; waiting until C miss exposes next=A. Prefetching C early loses that extra lookahead and spills A rather than B.'
    (ROOT/'results'/'prefetch_counterexample.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    with experiment_lock():main()
