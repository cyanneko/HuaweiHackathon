"""Preserve original wall timings; add process CPU timing in a separate version."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,statistics,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));from workflow import experiment_lock

def put(p,s):
    if p.exists():assert p.read_text()==s,p
    else:p.write_text(s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original=HERE/'finite_estimator_bench.cpp';source=original.read_text()
    source=source.replace('#include <cstdint>','#include <cstdint>\n#include <ctime>')
    source=source.replace('struct Trial {double total_us=0,','struct Trial {double process_cpu_us=0,total_us=0,')
    source=source.replace('    const auto start=Clock::now();','    const std::clock_t cpu_start=std::clock();\n    const auto start=Clock::now();')
    source=source.replace('    result.total_us=micros(start,Clock::now());','    result.total_us=micros(start,Clock::now());\n    result.process_cpu_us=1e6*static_cast<double>(std::clock()-cpu_start)/CLOCKS_PER_SEC;')
    old="<<result.bytes<<' '<<result.groups<<'\\n';"
    new="<<result.bytes<<' '<<result.groups<<' '<<result.process_cpu_us<<'\\n';"
    assert source.count(old)==1;source=source.replace(old,new)
    src=HERE/'finite_estimator_bench_process_v3.cpp';put(src,source)
    previous=HERE/'FINITE_BASELINE_RESULTS_SKEW_V2.json';data=json.loads(previous.read_text())
    plan={'previous_results_sha256':sha(previous),'original_kernel_sha256':sha(original),'new_kernel_sha256':sha(src),
          'change':'Add std::clock process CPU total; preserve original steady_clock wall timing and statistical calculations.',
          'background':'Coordinator reported another datasets worktree generating 2.1 inputs outside experiment_lock. No host-wide exclusive window claimed, no other task stopped.',
          'limitations':'Process CPU excludes descheduling but not frequency/cache/memory contention. Short timings have clock overhead/granularity. Precise deployment timing needs a clean window.',
          'protocol':'same six skew legal traces, one warmup, three measured repeats, rotated method order; no HashJoin engine reruns or uniform/test evaluation'}
    put(HERE/'FINITE_TIMING_CORRECTION_V3_PLAN.json',json.dumps(plan,indent=2)+'\n')
    build=HERE/'build';exe=build/'finite_estimator_bench_process_v3';records=[]
    with experiment_lock():
        if not exe.exists():subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra',str(src),'-o',str(exe)],check=True,capture_output=True,text=True)
    for flow in data['rows']:
        with experiment_lock():
            path=build/(flow['id']+'.events');output=build/(flow['id']+'.process_v3.out')
            if not output.exists():
                run=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=180);put(output,run.stdout)
            original_rows=[s for s in (build/(flow['id']+'.out')).read_text().splitlines() if s.startswith('ROW ')]
            new_rows=[s for s in output.read_text().splitlines() if s.startswith('ROW ')]
            assert original_rows==new_rows
            timings={m:[] for m in data['methods']}
            for line in output.read_text().splitlines():
                t=line.split()
                if t[0]=='TIME':timings[t[1]].append({'repeat':int(t[2]),'wall_total_us':float(t[3]),'wall_update_us':float(t[4]),'wall_query_us':float(t[5]),'process_cpu_total_us':float(t[8])})
            records.append({'id':flow['id'],'predictions_identical_to_original':True,
                            'timing':{m:{'raw':v,'median_wall_total_us':statistics.median(x['wall_total_us'] for x in v),'median_process_cpu_total_us':statistics.median(x['process_cpu_total_us'] for x in v)} for m,v in timings.items()}})
    result={'rows':records,'all_predictions_identical':True,'host_exclusive':False,'limitations':plan['limitations']}
    put(HERE/'FINITE_TIMING_CORRECTION_V3_RESULTS.json',json.dumps(result,indent=2)+'\n');print({'cases':len(records),'all_predictions_identical':True,'host_exclusive':False})
if __name__=='__main__':main()
