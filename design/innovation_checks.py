"""Small constructive checks of new proposals, not a benchmark."""
from pathlib import Path
import json
from itertools import combinations

class TinyState:
    def __init__(self,sizes,resident,m,w=100,r=80,penalty=10):
        self.sizes=list(sizes);self.resident=set(resident);self.m=m
        self.w,self.r,self.penalty=w,r,penalty
        self.io=self.misses=self.hits=0;self.actions=[]
        self.check()
    @property
    def used(self):return sum(self.sizes[p] for p in self.resident)
    def check(self):assert 0<=self.used<=self.m
    def spill(self,p):
        assert p in self.resident
        self.io+=self.sizes[p]/self.w;self.resident.remove(p);self.actions.append(['SPILL',p]);self.check()
    def load(self,p):
        assert p not in self.resident
        self.io+=self.sizes[p]/self.r;self.resident.add(p);self.actions.append(['LOAD',p]);self.check()
    def demand(self,p):
        if p in self.resident:self.hits+=1;return
        self.misses+=1
        while self.used+self.sizes[p]>self.m:
            v=max(self.resident,key=lambda x:(self.sizes[x],x));self.spill(v)
        self.load(p)
    def fused_miss(self,current,nxt):
        assert current not in self.resident and current!=nxt
        assert self.sizes[current]+self.sizes[nxt]<=self.m
        self.misses+=1
        extra=self.sizes[current]+(0 if nxt in self.resident else self.sizes[nxt])
        deficit=extra-(self.m-self.used)
        candidates=sorted(self.resident-{current,nxt})
        best=None
        for n in range(len(candidates)+1):
            for vs in combinations(candidates,n):
                sz=sum(self.sizes[p] for p in vs)
                if sz>=deficit and (best is None or sz<best[0]):best=(sz,vs)
        assert best is not None
        for p in best[1]:self.spill(p)
        if nxt not in self.resident:self.load(nxt)
        self.load(current)
        assert self.actions[-1]==['LOAD',current]
    def result(self):return dict(io=round(self.io,6),hit=self.hits,miss=self.misses,
                                 score=round(self.io+self.penalty*self.misses,6),resident=sorted(self.resident),actions=self.actions)

def main():
    baseline=TinyState([64]*4,{2,3},128)
    baseline.demand(0);baseline.demand(1)
    fused=TinyState([64]*4,{2,3},128)
    fused.fused_miss(0,1);fused.demand(1)
    assert fused.io==baseline.io and fused.misses==baseline.misses-1
    # A periodic callback sees only A. Waiting for its miss exposes next_op=C.
    eager=TinyState([64]*4,{2,3},128)
    eager.spill(2);eager.load(0);eager.demand(0)
    eager.misses+=1;eager.spill(3);eager.load(2)
    informed=TinyState([64]*4,{2,3},128)
    informed.misses+=1;informed.spill(3);informed.load(0);informed.demand(2)
    assert eager.result()['score']>informed.result()['score']
    sizes=[10,20,30,40];build=[]
    for spill_after in range(1,len(sizes)+1):
        written=sum(sizes[:spill_after])+sum(sizes[spill_after:])
        assert written==sum(sizes)
        build.append(dict(spill_after=spill_after,written_bytes=written,write_time=written/100))
    # Partial observation: two histories have identical counters and resident state.
    h1=[0]*100+[1]*100;h2=[0,1]*100
    assert len(h1)==len(h2)==200 and h1.count(0)==h2.count(0)==100
    assert h1[-1]==h2[-1]==1
    certificate=TinyState([64,64],{0},128)
    certificate.load(1);certificate.demand(1)
    certificate_wait=TinyState([64,64],{0},128);certificate_wait.demand(1)
    assert certificate.io==certificate_wait.io and certificate.misses==0 and certificate_wait.misses==1
    out={
      'adjacent_probe_example':{'sequential':baseline.result(),'fused':fused.result(),
       'claim_scope':'One constructed two-Probe prefix; no global performance guarantee.'},
      'build_write_invariant':build,
      'free_space_prefetch':{'prefetch':certificate.result(),'wait':certificate_wait.result()},
      'partial_observation_example':{'histories':2,'probe_count_each':200,'hits_each':200,
       'same_last_partition':1,'hidden_histories':['100*A then 100*B','(A,B)*100']},
      'prefetch_information_counterexample':{'eager_spills_C':eager.result(),'wait_sees_C':informed.result()},
      'status':'Constructive model checks only; no C++ implementation or new benchmark results.'
    }
    path=Path(__file__).with_name('innovation_checks.json');path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
