"""Null self-comparison for clipped relative timing scores, descriptive only."""
from pathlib import Path
import json,statistics
BASE=Path(__file__).resolve().parents[1]
def sc(v,b):return max(0.,min(10.,10*(1-v/b))) if b and v else 0.
def main():
    r=json.loads((BASE/'results/round4-cpu-panel.json').read_text());rows=[]
    for c in r['cases']:
        v=[x['Total_Score'] for x in c['runs']['naive']]
        forward=[sc(v[i+1],v[i]) for i in range(0,len(v)-1,2)]
        reverse=[sc(v[i],v[i+1]) for i in range(0,len(v)-1,2)]
        rows.append({'file':c['file'],'naive_mean_us':statistics.mean(v),'naive_median_us':statistics.median(v),'naive_min_us':min(v),'naive_max_us':max(v),'naive_stdev_us':statistics.stdev(v),'self_forward_mean_score':statistics.mean(forward),'self_reverse_mean_score':statistics.mean(reverse),'self_pair_count':len(forward),'candidate_mean_score':{n:statistics.mean(sc(a['Total_Score'],b['Total_Score']) for a,b in zip(c['runs'][n],c['runs']['naive'])) for n in c['runs'] if n!='naive'}})
    result={'scope':'Independent repeat-pairs of exactly the same Naive executable on zero-IO synthetic examples; null diagnostic, no case exclusion or scoring-policy change','repeats':r['repeats'],'cases':len(rows),'null_forward_equal_case_mean':statistics.mean(c['self_forward_mean_score'] for c in rows),'null_reverse_equal_case_mean':statistics.mean(c['self_reverse_mean_score'] for c in rows),'candidate_equal_case_mean':{n:statistics.mean(c['candidate_mean_score'][n] for c in rows) for n in rows[0]['candidate_mean_score']},'rows':rows,'interpretation':'Positive self-comparison indicates clipping plus timing variability can contribute apparent gains even with identical code. It does not identify how much any full-suite candidate gain is noise, and no calibrated score correction is applied.'}
    (BASE/'round4/CPU_NOISE_DIAGNOSTICS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
