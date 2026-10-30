"""Descriptive summaries and mixture sensitivity. Never replaces current score policy."""
from pathlib import Path
import json,statistics,hashlib,collections
BASE=Path(__file__).resolve().parents[1]

def score(c,name):
    rs=[]
    for a,b in zip(c['runs']['naive'],c['runs'][name]):
        v,n=b['Total_Score'],a['Total_Score'];rs.append(max(0.,min(10.,10.*(1.-v/n))) if v and n else 0.)
    return statistics.mean(rs)

def summarize(report,metadata):
    names=[n for n in report['summary'] if n!='naive'];result={}
    for name in names:
        rows=[]
        for case in report['cases']:
            meta=metadata.get(case['file'],{})
            row={'file':case['file'],'score':score(case,name),'family':meta.get('family','unknown'),'corner':meta.get('corner',None)}
            vals=case['runs'][name];bases=case['runs']['naive']
            row['cost_ratio']=statistics.mean(v['Total_Score'] for v in vals)/max(1e-30,statistics.mean(v['Total_Score'] for v in bases))
            row['io_miss']=statistics.mean(v['Total_IO_Time']+case['penalty']*v['Miss_Count'] for v in vals)
            row['decision_us']=statistics.mean(v['Total_Decision_Time'] for v in vals)
            row['naive_io_miss']=statistics.mean(v['Total_IO_Time']+case['penalty']*v['Miss_Count'] for v in bases)
            row['cpu_only']=row['naive_io_miss']==0 and row['io_miss']==0
            row['positive_io_against_zero_base']=row['naive_io_miss']==0 and row['io_miss']>0
            row['io_miss_ratio']=row['io_miss']/row['naive_io_miss'] if row['naive_io_miss']>0 else None
            rows.append(row)
        groups=collections.defaultdict(list)
        for r in rows:groups[r['family']].append(r)
        families={family:{'cases':len(v),'mean_score':statistics.mean(r['score'] for r in v),'max_cost_ratio':max(r['cost_ratio'] for r in v),'sum_decision_us':sum(r['decision_us'] for r in v)} for family,v in groups.items()}
        corner=[r['score'] for r in rows if r['corner'] is True];regular=[r['score'] for r in rows if r['corner'] is False]
        sensitivity={str(weight):weight*statistics.mean(corner)+(1-weight)*statistics.mean(regular) for weight in [0.,.1,.2,.25,.5,1.]} if corner and regular and len(corner)+len(regular)==len(rows) else None
        result[name]={'mean_score':statistics.mean(r['score'] for r in rows),'cases':len(rows),'sum_decision_us':sum(r['decision_us'] for r in rows),'max_cost_ratio':max(r['cost_ratio'] for r in rows),'regressions_gt_1pct':sum(r['cost_ratio']>1.01 for r in rows),'families':families,'equal_family_mean_diagnostic':statistics.mean(v['mean_score'] for v in families.values()) if 'unknown' not in families else None,'corner_weight_sensitivity_diagnostic':sensitivity,'cpu_only_cases':sum(r['cpu_only'] for r in rows),'positive_io_against_zero_base':sum(r['positive_io_against_zero_base'] for r in rows),'worst_io_miss_cases':sorted([r for r in rows if r['io_miss_ratio'] is not None],key=lambda r:r['io_miss_ratio'],reverse=True)[:8],'worst_cases':sorted(rows,key=lambda r:r['cost_ratio'],reverse=True)[:8]}
    return result

def main():
    output={'promotion':False,'scope':'synthetic samples only; equal family and corner mixture diagnostics do not estimate hidden distribution or replace per-member mean','generated':{},'members':{}}
    for suite in ['fresh','ood','screen','capacity-screen','guards-screen','case-ablations']:
        p=BASE/'results'/('round4-'+suite+'.json')
        if not p.exists():continue
        metadata={}
        data=BASE/'build/data'/('round4-'+suite if suite in ['fresh','ood'] else 'val')
        if (data/'manifest.json').exists():
            metadata={r['file']:r for r in json.loads((data/'manifest.json').read_text())['cases']}
        report=json.loads(p.read_text());output['generated'][suite]={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'repeats':report['repeats'],'summary':summarize(report,metadata)}
    for member in ['Vanius0525','cyanneko','liunianwww']:
        p=BASE/'results'/('round4-member-'+member+'.json')
        if not p.exists():continue
        metadata={}
        if member!='Vanius0525':
            records=json.loads((BASE/'build/team_snapshot_923d21e'/member/'manifest.json').read_text())['cases']
            metadata={Path(r['path']).name:{**r,'corner':r.get('family')=='corners' if member=='liunianwww' else None} for r in records if r['split']=='eval'}
        else:
            for folder in ['holdout','ood','round3-fresh','round3-ood']:
                d=json.loads((BASE/'build/data'/folder/'manifest.json').read_text())
                metadata.update({r['file']:{**r,'corner':False} for r in d['cases']})
            for r in json.loads((BASE/'results/balanced-own-corners.json').read_text())['cases']:
                if r['file']!='end_insert.txt':metadata[r['file']]={'family':'corner','corner':True}
        report=json.loads(p.read_text());output['members'][member]={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'repeats':report['repeats'],'summary':summarize(report,metadata)}
    if len(output['members'])==3:
        names=next(iter(output['members'].values()))['summary']
        output['equal_member_mean']={n:statistics.mean(v['summary'][n]['mean_score'] for v in output['members'].values()) for n in names}
    (BASE/'round4/RESULTS.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'equal_member_mean':output.get('equal_member_mean'),'generated':{s:{n:round(v['mean_score'],6) for n,v in d['summary'].items()} for s,d in output['generated'].items()}},indent=2))
if __name__=='__main__':main()
