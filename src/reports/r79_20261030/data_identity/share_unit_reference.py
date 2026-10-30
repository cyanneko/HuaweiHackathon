"""Direct full-vector mathematical oracle for sharing-weight unit tests; no policy/native."""
import json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=64;HALF_LIFE=2048;decay=2**(-1/HALF_LIFE)
def weight(c,w2):
 s=sum(c);q=sum(x*x for x in c);n=s*s/w2 if w2 else 0
 valid=s>8 and n>1 and len(c)>1 and all(math.isfinite(x) and x>0 for x in [s,q,w2,n])
 v=max(0,(len(c)*q/(s*s)-1-(len(c)-1)/n)/(1-1/n)) if valid else 0
 confidence=(s-8)/(s+len(c)) if valid else 0
 heterogeneity=v*confidence/(1+v*confidence)
 return dict(S=s,Q=q,W2=w2,n=n,v=v,confidence=confidence,alpha=.75*(1-heterogeneity))
def main():
 c=[0.]*P;w2=0.;checkpoints=[]
 # Every ordinal is unique. Duplicates/misses in the protocol below add no sample.
 for q in range(1,24577):
  c=[x*decay for x in c];w2*=decay*decay
  pid=(q-1)%P if q<=4096 or q>8192 else 0
  c[pid]+=1;w2+=1
  if q in [1,8,9,64,4096,8192,12288,16384,24576]:checkpoints.append(dict(q=q,pid=pid,**weight(c,w2)))
  if q==8192:hot_c=c[:];hot_w2=w2
 assert checkpoints[4]['alpha']>.70 and checkpoints[5]['alpha']<.10 and checkpoints[-1]['alpha']>.70
 gap=32768;f=2**(-gap/HALF_LIFE);gap_c=[x*f for x in hot_c];gap_w2=hot_w2*f*f
 empty=weight(gap_c,gap_w2);assert empty['alpha']==.75 and empty['S']<=8
 next_c=[x*decay for x in gap_c];next_c[0]+=1;next_result=weight(next_c,gap_w2*decay*decay+1)
 assert next_result['alpha']==.75 and all(math.isfinite(x) for x in next_result.values())
 out=dict(kind='mathematical_reference_only_no_native',confidence_formula='(S-8)/(S+P), only if S>8 and ESS n>1 and P>1; finite fallback .75',partition_count=P,half_life=HALF_LIFE,stages=[dict(name='uniform',q_first=1,q_last=4096,pid='(q-1)%64'),dict(name='single_hot',q_first=4097,q_last=8192,pid=0),dict(name='uniform_recovery',q_first=8193,q_last=24576,pid='(q-1)%64')],checkpoints=checkpoints,empty_gap_branch_from_hot=dict(gap=gap,after_gap=empty,after_one_next_sample=next_result),duplicate_test='After each accepted next ordinal replay the identical exposed next from Miss, Overflow and Periodic callbacks at the same q; S/Q/W2 and alpha must not change. Current miss alone never adds a next sample.',other_checks=['No observations: finite alpha .75','P=1: finite alpha .75','No next observation: common decay preserves ESS but reduces S and confidence; long empty gap returns alpha to .75','Use float tolerance about 1e-9 for moments/alpha, not exact binary equality. Reference applies full-vector decay and recomputes Q, independently of candidate lazy O(1) code.'],scope='This validates sharing-weight math/collection; no correctness claim about R75 refault heat, scheduler actions or performance.')
 (HERE/'share_unit_reference.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(checkpoints,indent=2))
if __name__=='__main__':main()
