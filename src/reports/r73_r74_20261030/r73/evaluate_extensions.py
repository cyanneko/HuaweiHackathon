"""Run standalone scheduler variants against the fixed R73 diagnostic set."""
import argparse
import hashlib
import json
import pathlib
import statistics
import subprocess
import sys

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import experiment as exp

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--policy',action='append',required=True,help='NAME=path')
    ap.add_argument('--output',required=True)
    ap.add_argument('--cases',default=str(exp.HERE/'cases.json'))
    ap.add_argument('--baseline-results',default=str(exp.HERE/'results.json'))
    args=ap.parse_args()
    target=pathlib.Path(args.output).resolve();target.mkdir(parents=True,exist_ok=True)
    cases=json.loads(pathlib.Path(args.cases).read_text())['cases']
    baseline=json.loads(pathlib.Path(args.baseline_results).read_text())
    by_case={r['case_id']:r['metrics'] for r in baseline if r['name']=='VanBest_p1'}
    original=(exp.SOURCES/'VanBest.policy.cpp').read_text()
    framework=(exp.SOURCES/'VanBest.cpp').read_text()
    assert framework.count(original)==1
    records=[];builds=[]
    for entry in args.policy:
        name,source=entry.split('=',1)
        assert name.replace('_','').isalnum()
        path=pathlib.Path(source).resolve();policy=path.read_text()
        for bad in ['int main(', 'class HashJoinEngine', 's.miss_penalty','state.miss_penalty',
                    'op_lines','getenv(', 'ifstream', 'std::cin', 'fopen(', 'freopen(']:
            assert bad not in policy,(name,bad)
        tp=target/(name+'.cpp');tp.write_text(framework.replace(original,policy))
        binary=target/name
        subprocess.run(['g++','-std=c++14','-O2',str(tp),'-o',str(binary)],check=True,capture_output=True)
        builds.append(dict(name=name,source=str(path),source_sha256=exp.digest(path),
            binary_sha256=exp.digest(binary),framework_skeleton_sha256=hashlib.sha256(framework.replace(original,'<SCHEDULER>').encode()).hexdigest()))
    (target/'build_manifest.json').write_text(json.dumps(builds,indent=2))
    # Reuse the runner while keeping all new artifacts isolated.
    old_here=exp.HERE
    exp.HERE=target
    (target/'raw').mkdir(exist_ok=True)
    (target/'build').mkdir(exist_ok=True)
    for b in builds:
        link=target/'build'/b['name']
        if not link.exists(): link.symlink_to(target/b['name'])
    for i,case in enumerate(cases):
        assert exp.digest(pathlib.Path(case['path']))==case['sha256']
        for b in (builds if i%2==0 else list(reversed(builds))):
            records.append(exp.run_one(b['name'],case))
        (target/'progress.json').write_text(json.dumps(dict(completed=len(records),total=len(cases)*len(builds),last=case['id'])))
    (target/'results.json').write_text(json.dumps(records,indent=2))
    for r in records:
        if r['name']=='VanBest_p1': by_case[r['case_id']]=r['metrics']
    summary={}
    for b in builds:
        name=b['name'];summary[name]={}
        for group in sorted(set(c['group'] for c in cases)):
            rows=[]
            for r in records:
                if r['name']!=name or r['group']!=group: continue
                a=r['metrics'];base=by_case[r['case_id']]
                ratios=[(a['Total_IO_Time']+p*a['Miss_Count'])/(base['Total_IO_Time']+p*base['Miss_Count']) for p in exp.PENALTIES]
                rows.append(dict(case=r['case_id'],ratios=ratios))
            flat=[v for r in rows for v in r['ratios']]
            summary[name][group]=dict(mean_ratio=statistics.mean(flat),median=statistics.median(flat),worst=max(flat),
                wins=sum(x<1-1e-10 for x in flat),losses=sum(x>1+1e-10 for x in flat),
                by_penalty=[statistics.mean(r['ratios'][j] for r in rows) for j in range(4)],cases=rows)
        print(name,{g:{k:round(v[k],6) for k in ['mean_ratio','worst']} for g,v in summary[name].items()},flush=True)
    (target/'summary.json').write_text(json.dumps(summary,indent=2))
    (target/'complete.json').write_text(json.dumps(dict(valid=len(records),expected=len(cases)*len(builds),
        physical_comparison_only=True,formal_D=False,active_children=0),indent=2))
    exp.HERE=old_here

if __name__=='__main__': main()
