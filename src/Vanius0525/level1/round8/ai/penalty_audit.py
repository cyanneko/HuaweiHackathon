"""Read-only hidden-penalty sensitivity on fixed, legal counterfactual trajectories."""
import argparse,json
from make_policy import HERE,put

def main():
    p=argparse.ArgumentParser();p.add_argument('report',choices=['LOCAL_PILOT_RESULTS','INDEPENDENT_COLLECT_RESULTS']);a=p.parse_args()
    data=json.loads((HERE/(a.report+'.json')).read_text());rows=[]
    for flow in data['rows']:
        rd,wr=flow['bandwidths']
        for state in flow['rows']:
            branches=state['branches'];deltas=[]
            for cont in range(2):
                b0,b1=branches[cont*2:cont*2+2]
                deltas.append({'read_bytes':b0['read_bytes']-b1['read_bytes'],'write_bytes':b0['write_bytes']-b1['write_bytes'],'misses':b0['misses']-b1['misses']})
            gains={str(lam):[d['read_bytes']/rd+d['write_bytes']/wr+lam*d['misses'] for d in deltas] for lam in [1,50,500]}
            signs={lam: int(min(v)>0)-int(min(v)<0) for lam,v in gains.items()}
            rows.append({'flow':flow['id'],'operation':state['operation'],'deltas':deltas,'gain_us_by_penalty':gains,'robust_preference_sign':signs,'preference_changes_with_hidden_penalty':len(set(signs.values()))>1})
    result={'states':len(rows),'hidden_penalty_preference_flips':sum(x['preference_changes_with_hidden_penalty'] for x in rows),'limits':'Exact reweighting of fixed action trajectories; penalty is never an online feature. Two continuation policies are conditional, not OPT. No new solver calls.','rows':rows}
    put(HERE/('PENALTY_'+a.report+'.json'),json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='rows'})
if __name__=='__main__':main()
