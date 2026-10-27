"""Prototype: worst compatible empirical hidden-hit loss, not a future predictor.
An epoch must have a known unchanged eligible resident set. Split at every
callback/action/phase change, subtract deduplicated known next_op samples.
If eligibility cannot be established, conservatively use all eligible pages.
"""
import itertools,json
from pathlib import Path
def robust_loss(victims,cost,known,epochs):
    """Exact maximum for independent censored epochs with unlimited repetition."""
    v=set(victims)
    return sum(known[i]*cost[i] for i in v)+sum(h*max([cost[i] for i in eligible if i in v] or [0]) for h,eligible in epochs)
def assignments(total,n):
    if n==1:yield (total,);return
    for x in range(total+1):
        for rest in assignments(total-x,n-1):yield (x,)+rest
def brute(victims,cost,known,epochs):
    values=[]
    for h,eligible in epochs:
        epoch=[]
        for counts in assignments(h,len(eligible)):
            epoch.append(sum(n*cost[i] for i,n in zip(eligible,counts) if i in victims))
        values.append(epoch)
    return sum(known[i]*cost[i] for i in victims)+max(sum(x) for x in itertools.product(*values))
def main():
    checks=0
    cost=[2,3,5,7];known=[1,0,2,0];sets=[(0,1),(1,2,3),(0,2),(0,1,2,3)]
    for mask in range(16):
        v={i for i in range(4) if mask>>i&1}
        for h1,h2 in itertools.product(range(5),repeat=2):
            for e1,e2 in itertools.product(sets,repeat=2):
                ep=[(h1,e1),(h2,e2)];assert robust_loss(v,cost,known,ep)==brute(v,cost,known,ep);checks+=1
    out=dict(exhaustive_checks=checks,all_passed=True,
       meaning='Exact upper envelope of past hit-assignment costs compatible with the censored observations. Not a bound on future Score.',
       formula='sum_i_in_V known_i*c_i + sum_epoch H_epoch*max_{i in V intersect eligible_epoch} c_i')
    (Path(__file__).resolve().parent/'uncertainty_checks.json').write_text(json.dumps(out,indent=2),encoding='utf8');print(out)
if __name__=='__main__':main()
