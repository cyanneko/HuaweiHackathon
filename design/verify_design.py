"""Executable model of CostAwareScheduler.hpp; no third-party dependencies."""
import json, random
from pathlib import Path

class Model:
    def __init__(self,k,p,m,w=100,r=80,penalty=10,b=3,policy='cost',prefetch=True):
        self.k,self.p,self.m,self.w,self.r,self.penalty,self.b=k,p,m,w,r,penalty,b
        self.policy,self.prefetch=policy,prefetch
        self.sizes=[[0]*p for _ in range(k)]
        self.mem=[[True]*p for _ in range(k)]
        self.phase=[False]*k
        self.pressure=[[0.0]*p for _ in range(k)]
        self.used=self.hit=self.miss=self.count=self.peak=0
        self.io=0.0
        self.trace=[]
    def check(self):
        assert self.used==sum(self.sizes[o][p] for o in range(self.k) for p in range(self.p) if self.mem[o][p])
        assert 0<=self.used<=self.m
        self.peak=max(self.peak,self.used)
    def loss(self,o,p,nxt):
        z=self.sizes[o][p]; h=self.pressure[o][p]; q=.15+.70*h/(1+h)
        if nxt and nxt[0]=='PROBE' and nxt[1]==o and nxt[2]%self.p==p: q=1.
        if not self.phase[o]: q*=.35
        return z/self.w+q*(z/self.r+self.penalty)
    def select(self,need,target,nxt):
        deficit=need-(self.m-self.used)
        if deficit<=0:return [],0.
        c=[(o,p,self.sizes[o][p],self.loss(o,p,nxt)) for o in range(self.k) for p in range(self.p)
           if self.mem[o][p] and self.sizes[o][p]>0 and (o,p)!=target]
        if self.policy=='naive': c.sort(key=lambda x:(-x[2],-x[0],-x[1]))
        else:c.sort(key=lambda x:(x[3]/x[2],-x[2],-x[0],-x[1]))
        chosen=[]; freed=0
        for x in c:
            chosen.append(x); freed+=x[2]
            if freed>=deficit:break
        if freed<deficit:raise ValueError('infeasible protected-target allocation')
        cost=sum(x[3] for x in chosen)
        if self.policy!='naive':
            for x in c:
                if x[2]>=deficit and x[3]<cost:chosen=[x];freed=x[2];cost=x[3]
            for x in list(chosen):
                if freed-x[2]>=deficit:chosen.remove(x);freed-=x[2];cost-=x[3]
        return [(o,p) for o,p,_,_ in chosen],cost
    def spill(self,o,p):
        assert self.mem[o][p] and self.sizes[o][p]>0
        self.io+=self.sizes[o][p]/self.w;self.used-=self.sizes[o][p];self.mem[o][p]=False;self.check()
    def load(self,o,p):
        assert self.phase[o] and not self.mem[o][p]
        self.io+=self.sizes[o][p]/self.r;self.used+=self.sizes[o][p];self.mem[o][p]=True;self.check()
    def run(self,ops):
        for i,op in enumerate(ops):
            nxt=ops[i+1] if i+1<len(ops) else None
            typ,o,*args=op;acts=[]
            if typ=='SWITCH':self.phase[o]=True;continue
            p=args[0]%self.p
            if typ=='INSERT':
                assert not self.phase[o]
                size=args[1]
                if self.mem[o][p]:
                    if self.used+size>self.m:
                        victims,_=self.select(size,(o,p),nxt)
                        for v in victims:self.spill(*v);acts.append(('SPILL',*v))
                    self.used+=size
                else:self.io+=size/self.w
                self.sizes[o][p]+=size
            else:
                assert self.phase[o]
                if self.mem[o][p]:self.hit+=1
                else:
                    self.miss+=1;self.pressure[o][p]=min(32.,self.pressure[o][p]+1)
                    victims,_=self.select(self.sizes[o][p],(o,p),nxt)
                    for v in victims:self.spill(*v);acts.append(('SPILL',*v))
                    self.load(o,p);acts.append(('LOAD',o,p))
            self.count+=1;self.check()
            if self.count%self.b==0:
                self.pressure=[[x*.95 for x in row] for row in self.pressure]
                if self.policy!='naive' and self.prefetch and nxt and nxt[0]=='PROBE':
                    no,np=nxt[1],nxt[2]%self.p
                    if self.phase[no] and not self.mem[no][np] and self.sizes[no][np]<=self.m:
                        vs,cost=self.select(self.sizes[no][np],(no,np),nxt)
                        if cost<self.penalty:
                            for v in vs:self.spill(*v);acts.append(('PREFETCH_SPILL',*v))
                            self.load(no,np);acts.append(('PREFETCH_LOAD',no,np))
            self.trace.append(dict(step=i+1,op=op,actions=acts,used=self.used,io=self.io,hit=self.hit,miss=self.miss))
        return dict(io=round(self.io,6),hit=self.hit,miss=self.miss,score=round(self.io+self.penalty*self.miss,6),peak=self.peak)

def main():
    root=Path(__file__).parent
    lines=(root/'sample_corrected.txt').read_text().splitlines()
    ops=[]
    for l in lines[3:]:
        t,*xs=l.split();ops.append((t,*map(int,xs)))
    sample={}
    for mode,pref in [('naive',False),('cost',False),('cost',True)]:
        model=Model(1,3,256,policy=mode,prefetch=pref)
        key=mode+('_prefetch' if pref else '')
        sample[key]=model.run(ops);sample[key]['trace']=model.trace
    rng=random.Random(20261013);results=[]
    for case in range(200):
        k=rng.randint(1,4);p=rng.randint(2,8);m=rng.randint(128,512);b=rng.randint(1,20)
        build=[0]*k;all_ops=[]
        # Cap each complete partition at M, so protected-target INSERT is feasible.
        totals=[[0]*p for _ in range(k)]
        for _ in range(120):
            o=rng.randrange(k);pid=rng.randrange(p);size=rng.randint(1,32)
            if totals[o][pid]+size<=m:
                all_ops.append(('INSERT',o,pid,size));totals[o][pid]+=size
        all_ops.extend(('SWITCH',o) for o in range(k))
        for i in range(250):
            o=rng.randrange(k);pid=0 if rng.random()<.65 else rng.randrange(p)
            all_ops.append(('PROBE',o,pid))
        row={'case':case}
        for policy,pref in [('naive',False),('cost',False),('cost',True)]:
            a=Model(k,p,m,b=b,policy=policy,prefetch=pref)
            r=a.run(all_ops)
            assert r['hit']+r['miss']==250
            row[policy+('_prefetch' if pref else '')]=r
        results.append(row)
    # Empty partition, direct disk append and interleaved BUILD/PROBE boundary cases.
    edges=[[( 'SWITCH',0),('PROBE',0,0)],
           [('INSERT',0,0,80),('INSERT',1,1,80),('INSERT',0,0,20),('SWITCH',0),('PROBE',0,0),('INSERT',1,0,20),('SWITCH',1),('PROBE',1,1)]]
    for ops2 in edges:Model(2,2,128,b=1).run(ops2)
    infeasible_detected=False
    try:Model(1,2,128).run([('INSERT',0,0,128),('INSERT',0,0,1)])
    except ValueError:infeasible_detected=True
    assert infeasible_detected
    summary={key:sum(x[key]['score'] for x in results) for key in ['naive','cost','cost_prefetch']}
    report=dict(sample=sample,random_cases=200,seed=20261013,aggregate_score=summary,
                edge_cases_passed=2,infeasible_detected=infeasible_detected,
                limitation='Python executable model tested; C++ header not compiled in this environment. Synthetic tests are not official benchmarks.')
    (root/'validation_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({**{k:v for k,v in report.items() if k!='sample'},'sample':{k:{a:b for a,b in v.items() if a!='trace'} for k,v in sample.items()}},indent=2))

if __name__=='__main__':main()
