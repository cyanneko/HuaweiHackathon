"""Small-state legality, integration, counterexamples, and complete 5M traces."""
from __future__ import annotations
import argparse,json,math,re,subprocess,time
from pathlib import Path
from train_and_evaluate import ROOT,OUT,OLD,DEV,dump,sha,invoke_rows,loadlines

def one(path,policy,fast=False):
    cmd=[str(ROOT/'benchmark.exe'),str(path),policy]
    if fast:cmd.append('fast')
    begin=time.perf_counter();p=subprocess.run(cmd,capture_output=True,text=True,timeout=65)
    wall=time.perf_counter()-begin
    if p.returncode:raise RuntimeError(p.stderr)
    result=json.loads(p.stdout);assert result['ok'],result
    result['whole_process_wall_s']=wall
    return result

def small():
    manifest=json.loads((DEV/'manifest.json').read_text('utf8'))
    tiny=[{**r,'file':str((DEV/r['file']).resolve())} for r in manifest if r['split']=='tiny']
    invoke_rows(tiny,['baseline','recommended','score_first','learned','old_prior32','prefix_prior1'],OUT/'tiny_legality.jsonl')
    bounds={r['case']:r['lower_bound'] for r in json.loads((DEV/'results/offline_bounds.json').read_text('utf8'))}
    path_to_meta={str(Path(r['file']).resolve()):r for r in tiny}
    for result in loadlines(OUT/'tiny_legality.jsonl'):
        row=path_to_meta[str(Path(result['input']).resolve())]
        assert result['score']+1e-7>=bounds[row['id']]
        assert result['hit']+result['miss']==row['probes']
        assert 0<=result['peak']<=row['M']
    regress=json.loads((DEV/'targeted_manifest.json').read_text('utf8'))
    regress=[{**r,'file':str((DEV/r['file']).resolve())} for r in regress]
    # Previously found failures are regressions, never treated as fresh holdout cases.
    first=ROOT/'holdout_20261026_104546_fb7d01'
    for name in ['capacity_cycle_15','capacity_cycle_18','corner_107']:
        row=next(r for r in json.loads((first/'manifest.json').read_text('utf8')) if r['id']==name)
        regress.append(row)
    invoke_rows(regress,['baseline','recommended','score_first','learned','old_prior32','prefix_prior1','4','6'],OUT/'regression_results.jsonl',repetitions=3)
    # Counterfactual change of the HIDDEN input penalty must not change actions.
    # Check full observable outcome: hit/miss, byte counts, action counts, mode.
    invariance=[];temp=OUT/'penalty_check.txt'
    for row in regress[:4]:
        original=Path(row['file']).read_text('ascii').splitlines();records=[]
        for penalty in [1,1000]:
            fields=original[0].split();fields[5]=str(penalty)
            temp.write_text(' '.join(fields)+'\n'+'\n'.join(original[1:])+'\n','ascii')
            records.append(one(temp,'recommended'))
        keys=['hit','miss','write_bytes','read_bytes','spills','loads','selected_mode','thrashing_detected']
        assert all(records[0][key]==records[1][key] for key in keys)
        invariance.append(dict(case=row['id'],same_decisions_under_penalty_change=True,outcomes=records))
    dump(OUT/'hidden_penalty_invariance.json',invariance)
    # Execute the actual published HashJoinEngine, with only the allowed class substitution.
    integration=[]
    inputs=[Path(r['file']) for r in regress[:4]]+[ROOT.parent/'sample_corrected.txt',ROOT.parent/'examples/prefix_walkthrough.txt']
    for path in inputs:
        actual=subprocess.run([str(ROOT/'submission_check.exe'),str(path)],capture_output=True,text=True,check=True)
        values={k:float(v) for k,v in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([\d.eE+-]+)',actual.stdout)}
        expected=one(path,'recommended')
        assert abs(values['Total_IO_Time']-expected['io'])<=.011
        assert values['Hit_Count']==expected['hit'] and values['Miss_Count']==expected['miss']
        header=path.read_text('ascii').splitlines()[0].split();penalty=int(header[5])
        assert abs(values['Total_Score']-(values['Total_IO_Time']+values['Total_Decision_Time']+penalty*values['Miss_Count']))<=.03
        integration.append(dict(input=str(path),published_engine=values,replay=expected,non_timing_metrics_match=True))
    dump(OUT/'integration_checks.json',integration)
    dump(OUT/'small_checks_summary.json',dict(toy_inputs=len(tiny),toy_replays=len(tiny)*6,all_above_exact_offline_bounds=True,
        regression_inputs=len(regress),integration_checks=len(integration),hidden_penalty_invariance=len(invariance),all_passed=True))
    print('Small, integration, counterexample and hidden-penalty checks passed.',flush=True)

def scale():
    rows=json.loads((DEV/'scale_manifest.json').read_text('utf8'))
    results=[]
    for row in rows:
        path=(DEV/row['file']).resolve()
        for policy in ['baseline','recommended','score_first','old_prior32','prefix_prior1']:
            result=one(path,policy,fast=True);result['case']=row['id']
            assert result['whole_process_wall_s']<60
            assert result['hit']+result['miss']==row['probes']
            expected=result['write_bytes']/row['W']+result['read_bytes']/row['R']+row['penalty']*result['miss']+result['decision_us']
            assert math.isclose(result['score'],expected,rel_tol=1e-8,abs_tol=1e-4)
            results.append(result);dump(OUT/'scale_results.json',results)
            print(json.dumps({k:result[k] for k in ['case','policy','score','decision_us','miss','wall_s','whole_process_wall_s','rss','selected_mode','thrashing_detected']}),flush=True)
    dump(OUT/'scale_manifest.json',[{**r,'file':str((DEV/r['file']).resolve())} for r in rows])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['small','scale']);args=ap.parse_args();globals()[args.action]()
if __name__=='__main__':main()
