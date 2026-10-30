"""Population likelihood diagnostic on a finite enumerated IID toy."""
import itertools,json,math,sys
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from enumerate_censored import transcript
from make_policy import HERE,ROOT,put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock

def statistics(trace):
    exact={};nexts={};misses={};anon=defaultdict(float)
    previous_q=previous_h=0;previous_next=None;after={0}
    for tag,q,h,m,current,nxt,before,actions in trace:
        known_hit=previous_next is not None and q>previous_q and previous_next in after
        hidden=h-previous_h-int(known_hit);assert hidden>=0
        anon[tuple(sorted(after))]+=hidden
        if current is not None:exact[q]=current;misses[q]=current
        if nxt is not None:exact[q+1]=nxt;nexts[q+1]=nxt
        after=set(before)
        for action,i in actions:
            if action=='S':after.remove(i)
            else:after.add(i)
        previous_q=q;previous_h=h;previous_next=nxt
    return exact,nexts,misses,anon

def main():
    truth=np.array([.1,.2,.7]);results=[]
    with experiment_lock():
        for period in [2,3]:
            for prefetch in [False,True]:
                counts=np.zeros(3);next_counts=np.zeros(3);miss_counts=np.zeros(3);anonymous=defaultdict(float)
                for seq in itertools.product(range(3),repeat=6):
                    weight=math.prod(truth[i] for i in seq)
                    trace,_,_,_=transcript(seq,period,prefetch,truth)
                    exact,nexts,misses,anon=statistics(trace)
                    for i in exact.values():counts[i]+=weight
                    for i in nexts.values():next_counts[i]+=weight
                    for i in misses.values():miss_counts[i]+=weight
                    for members,h in anon.items():anonymous[members]+=weight*h
                def objective(z):
                    logits=np.r_[z,0.];p=np.exp(logits-max(logits));p/=sum(p)
                    ll=float(np.dot(counts,np.log(p)));gp=counts/p
                    for members,h in anonymous.items():
                        mass=sum(p[list(members)]);ll+=h*np.log(mass)
                        gp[list(members)]+=h/mass
                    gradient=-p*(gp-np.dot(gp,p))
                    return -ll,gradient[:2]
                fit=minimize(objective,np.zeros(2),jac=True,method='BFGS',options={'gtol':1e-10,'maxiter':100})
                logits=np.r_[fit.x,0.];estimated=np.exp(logits-max(logits));estimated/=sum(estimated)
                assert max(abs(estimated-truth))<1e-7,(fit.message,estimated)
                assert max(abs(next_counts/sum(next_counts)-truth))<1e-12
                results.append({'period':period,'next_dependent_prefetch':prefetch,'enumerated_sequences':729,
                                'population_censored_mle':estimated.tolist(),'optimizer_success':bool(fit.success),
                                'gradient_norm':float(np.linalg.norm(fit.jac)),
                                'next_only_expected_frequency':(next_counts/sum(next_counts)).tolist(),
                                'all_visible_expected_frequency':(counts/sum(counts)).tolist(),
                                'current_miss_only_expected_frequency':(miss_counts/sum(miss_counts)).tolist(),
                                'expected_exact_samples':float(sum(counts)),'expected_anonymous_hits':float(sum(anonymous.values()))})
    out={'truth':truth.tolist(),'all_passed':True,'cases':results,
         'scope':'Population diagnostic sums all 729 hidden paths; not fitted/evaluated finite-sample cache performance. The next-only baseline is already consistent here. No claim that MLE beats it in finite samples, deployment cost, or non-IID traffic.'}
    put(HERE/'CENSORED_POPULATION_RESULTS.json',json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
