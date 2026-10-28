"""Recompute published R57 numbers. Standard library only; never launches a solver."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

METHODS=('best_fit_fast','next_guard_fast','single_fit_phase')
METRICS=('Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score')
ROLES=('candidate','paired_naive')


def require(condition,message):
    if not condition:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()


def object_hash(value):
    return digest(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8'))


def single_score(value,baseline):
    return max(0.0,min(10.0,10*(1-value/baseline))) if value>0 and baseline>0 else 0.0


def average(values):return math.fsum(x/len(values) for x in values)


def compute(records,case_info,data):
    cases={(r['member'],r['case']):r for r in case_info['cases']}
    require(len(cases)==len(case_info['cases']),'duplicate input identity')
    identities=[]
    catalog={}
    for d in data['datasets']:
        identity={k:d[k] for k in ('member','version','files')}
        require(object_hash(identity)==d['sha256'],'dataset fingerprint mismatch')
        identities.append({k:d[k] for k in ('member','version','sha256')})
        catalog.update({(d['member'],r['path']):r['sha256'] for r in d['files'] if r['path'].endswith('.txt')})
    require(set(cases)==set(catalog),'case catalog differs from dataset identity')
    require(object_hash(sorted(identities,key=lambda x:x['member']))==data['suite_id'],'suite fingerprint mismatch')
    by_key={}
    for r in records:
        key=(r['method'],r['member'],r['case'],r['repeat'],r['role'])
        require(key not in by_key,'duplicate measurement')
        require(r['method'] in METHODS and r['role'] in ROLES and r['repeat'] in (1,2,3),'measurement scope')
        require((r['member'],r['case']) in cases,'unknown case')
        info=cases[r['member'],r['case']]
        require(r['input_sha256']==info['sha256']==catalog[r['member'],r['case']],'input fingerprint mismatch')
        require(r['status']=='complete' and r['returncode']==0,'measurement did not complete')
        metrics=r['metrics'];require(set(metrics)==set(METRICS),'five metrics required')
        for name,value in metrics.items():
            require(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0,'invalid metric')
            if name.endswith('_Count'):require(type(value) is int,'counts must be integers')
        require(metrics['Hit_Count']+metrics['Miss_Count']==info['probe_count'],'probe count mismatch')
        expected=metrics['Total_IO_Time']+info['penalty']*metrics['Miss_Count']+metrics['Total_Decision_Time']
        require(abs(expected-metrics['Total_Score'])<=0.015001,'cost formula mismatch')
        parsed={}
        for line in r['stdout'].splitlines():
            if not line.strip():continue
            name,separator,value=line.partition(':');name=name.strip()
            require(separator and name in METRICS and name not in parsed,'invalid stdout metric line')
            parsed[name]=int(value.strip()) if name.endswith('_Count') else float(value.strip())
        require(parsed==metrics,'stdout and numeric metrics differ')
        by_key[key]=r
    expected_keys={(m,member,case,repeat,role) for m in METHODS for member,case in cases
                   for repeat in (1,2,3) for role in ROLES}
    require(set(by_key)==expected_keys,'missing or extra measurements')
    pair_rows=[];case_rows=[];methods={}
    for method in METHODS:
        scores={};ratios=[];totals={role:{metric:0.0 for metric in METRICS} for role in ROLES}
        for member,case in sorted(cases):
            pairs=[]
            for repeat in (1,2,3):
                a=by_key[method,member,case,repeat,'candidate'];b=by_key[method,member,case,repeat,'paired_naive']
                score=single_score(a['metrics']['Total_Score'],b['metrics']['Total_Score'])
                scores[member,case,repeat]=score;pairs.append((a,b,score))
                row={'method':method,'member':member,'case':case,'repeat':repeat,'single_score':score}
                for label,r in [('candidate',a),('paired_naive',b)]:
                    row.update({label+'_'+metric:r['metrics'][metric] for metric in METRICS})
                    row[label+'_wall_seconds']=r['wall_seconds']
                pair_rows.append(row)
            means={role:{metric:average([pair[i]['metrics'][metric] for pair in pairs]) for metric in METRICS}
                   for i,role in enumerate(ROLES)}
            base=means['paired_naive']['Total_Score'];require(base>0,'ratio denominator must be positive')
            ratio=means['candidate']['Total_Score']/base;ratios.append(ratio)
            row={'method':method,'member':member,'case':case,'mean_single_score':average([pair[2] for pair in pairs]),'cost_ratio':ratio}
            for role in ROLES:
                row.update({role+'_'+metric:value for metric,value in means[role].items()})
                for metric,value in means[role].items():totals[role][metric]+=value
            case_rows.append(row)
        dataset_scores=[]
        for d in data['datasets']:
            per_repeat=[{'repeat':r,'level1_estimate':min(50.0,math.fsum(value for (member,case,repeat),value in scores.items() if member==d['member'] and repeat==r))} for r in (1,2,3)]
            dataset_scores.append({k:d[k] for k in ('member','version','sha256','case_count')})
            dataset_scores[-1].update({'per_repeat':per_repeat,'level1_estimate':average([r['level1_estimate'] for r in per_repeat])})
        ordered=sorted(ratios)
        methods[method]={'status':'complete','candidate_measurements':len(cases)*3,'paired_naive_measurements':len(cases)*3,
                         'per_dataset':dataset_scores,'average_score':average([d['level1_estimate'] for d in dataset_scores]),
                         'case_cost_ratios':{'mean':average(ratios),'p50':statistics.median(ratios),
                                             'p90':ordered[math.ceil(.9*len(ordered))-1],'worst':ordered[-1]},
                         'wins':sum(x<1 for x in ratios),'ties':sum(x==1 for x in ratios),'losses':sum(x>1 for x in ratios),
                         'aggregate_mean_metrics':totals,'total_cost_ratio':totals['candidate']['Total_Score']/totals['paired_naive']['Total_Score']}
    summary={'complete':True,'suite_id':data['suite_id'],'case_count':len(cases),'available_dataset_count':len(data['datasets']),
             'candidate_methods':3,'candidate_repeats':3,'candidate_measurements':len(records)//2,
             'paired_naive_measurements':len(records)//2,'total_measurements':len(records),'failures':0,'timeouts':0,
             'methods':methods,'skipped_members':data['skipped_members'],
             'tail_definition':'ratio of three-repeat candidate mean cost to its paired Naive mean cost; P50 median; P90 nearest-rank22 of24',
             'latency_scope':'original direct schedulers; not ID103 adapter or trained gating tree'}
    return summary,pair_rows,case_rows


def csv_text(rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows);return stream.getvalue()


def same_tree(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(same_tree(a[k],b[k]) for k in a)
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(same_tree(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and not isinstance(a,bool):return isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
    return a==b


def validate_bundle(folder):
    folder=Path(folder).resolve()
    manifest=json.loads((folder/'artifact_manifest.json').read_text(encoding='utf8'))
    for relative,expected in manifest['files'].items():
        path=(folder/relative).resolve();require(path.is_relative_to(folder),'artifact outside package')
        require(digest(path.read_bytes())==expected,'artifact hash mismatch: '+relative)
    records=[json.loads(line) for line in (folder/'measurements.jsonl').read_text(encoding='utf8').splitlines()]
    info=json.loads((folder/'case_info.json').read_text(encoding='utf8'))
    data=json.loads((folder/'datasets.json').read_text(encoding='utf8'))
    summary,pairs,cases=compute(records,info,data)
    require(same_tree(summary,json.loads((folder/'summary.json').read_text(encoding='utf8'))),'summary differs from raw measurements')
    require((folder/'paired_cases.csv').read_text(encoding='utf8')==csv_text(pairs),'paired CSV mismatch')
    require((folder/'case_summary.csv').read_text(encoding='utf8')==csv_text(cases),'case CSV mismatch')
    return {'passed':True,'measurements':len(records),'pairs':len(pairs),'case_summaries':len(cases),'suite_id':data['suite_id']}


if __name__=='__main__':print(json.dumps(validate_bundle(Path(__file__).resolve().parent)))
