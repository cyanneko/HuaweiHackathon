"""Bounded offline-only supervisor. Deployment features never receive future/penalty."""
import copy, hashlib, json, math, random, re, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SEED=20552801
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def teacher_preference(plan,b,l):
    if plan==[l]:return 1.
    if plan==[b]:return -1.
    return 0.

class State:
    def __init__(self,k,p,m,w,r,penalty,period):
        self.k,self.p,self.m,self.w,self.r,self.penalty,self.period=k,p,m,w,r,penalty,period
        self.size=[0]*(k*p);self.res=[True]*(k*p);self.phase=[False]*k
        self.used=0;self.cost=0.;self.hits=0;self.misses=0;self.count=0
    def candidates(self,c):
        typ,o,pid,n=c;t=o*self.p+pid;need=self.size[t] if typ=='PROBE' else n
        d=need-(self.m-self.used)
        cs=[i for i,z in enumerate(self.size) if self.res[i] and z>0 and i!=t]
        fit=[i for i in cs if self.size[i]>=d]
        b=min(fit,key=lambda i:(self.size[i],i)) if fit else None
        l=min(cs,key=lambda i:(-self.size[i],i)) if cs else None
        return d,b,l,cs
    def plan(self,c,nxt,mode='bf',force=None):
        d,b,l,cs=self.candidates(c);chosen=[];free=self.m-self.used
        t=c[1]*self.p+c[2];need=self.size[t] if c[0]=='PROBE' else c[3]
        if mode=='ng' and nxt and nxt[0]=='PROBE':
            hot=nxt[1]*self.p+nxt[2]
            if sum(self.size[i] for i in cs if i!=hot)>=need-free:cs=[i for i in cs if i!=hot]
        else:hot=-1
        while free<need and cs:
            fit=[i for i in cs if self.size[i]>=need-free]
            v=force if force in cs else (min(fit,key=lambda i:(self.size[i],i)) if fit and mode=='bf' else min(cs,key=lambda i:(-self.size[i],i)))
            force=None;chosen.append(v);free+=self.size[v];cs.remove(v)
        if free<need:raise ValueError('infeasible physical state')
        return chosen
    def event(self,c,nxt,mode='bf',force=None):
        typ,o,pid,n=c;t=o*self.p+pid
        if typ=='SWITCH':self.phase[o]=True;return
        if typ=='INSERT':
            if self.res[t]:
                if self.used+n>self.m:self.spill(self.plan(c,nxt,mode,force))
                self.used+=n
            else:self.cost+=n/self.w
            self.size[t]+=n
        else:
            if self.res[t]:self.hits+=1
            else:
                self.misses+=1;self.cost+=self.penalty
                self.spill(self.plan(c,nxt,mode,force))
                if not self.phase[o]:raise ValueError('BUILD load')
                self.cost+=self.size[t]/self.r;self.used+=self.size[t];self.res[t]=True
        self.count+=1
        if self.used>self.m:raise ValueError('OOM')
    def spill(self,ids):
        for i in ids:
            assert self.res[i] and self.size[i]>0
            self.cost+=self.size[i]/self.w;self.used-=self.size[i];self.res[i]=False

def features(s,c,nxt,b,l):
    miss=c[0]=='PROBE';t=c[1]*s.p+c[2];n=s.size[t] if miss else c[3];f=s.m-s.used
    hot=nxt[1]*s.p+nxt[2] if nxt and nxt[0]=='PROBE' else -1
    count=sum(r and z>0 for r,z in zip(s.res,s.size))
    pb=sum(z for i,z in enumerate(s.size) if s.res[i] and s.phase[i//s.p])
    # official miss callback has already incremented miss_count
    mc=s.misses+int(miss)
    return [float(miss),f/s.m,n/s.m,max(0,n-f)/s.m,s.size[t]/s.m,s.size[b]/s.m,s.size[l]/s.m,
            float(s.phase[b//s.p]),float(s.phase[l//s.p]),float(hot==b),float(hot==l),float(hot>=0),
            mc/(s.hits+mc+1),count/(s.k*s.p),s.w/(s.w+s.r),pb/s.m]

class Model:
    def __init__(self,seed):
        rng=random.Random(seed);self.w=[[rng.uniform(-.12,.12) for _ in range(16)] for _ in range(8)]
        self.b=[0.]*8;self.v=[rng.uniform(-.12,.12) for _ in range(8)];self.a=-.02
    def forward(self,x):
        h=[max(0.,sum(w*z for w,z in zip(row,x))+b) for row,b in zip(self.w,self.b)]
        return sum(v*z for v,z in zip(self.v,h))+self.a,h
    def flat(self):return sum(self.w,[])+self.b+self.v+[self.a]
    def train(self,rows,steps):
        for _ in range(steps):
            gw=[[0.]*16 for j in range(8)];gb=[0.]*8;gv=[0.]*8;ga=0.
            for x,y in rows:
                pred,h=self.forward(x);g=max(-2.,min(2.,2*(pred-y)));ga+=g
                for j in range(8):
                    gv[j]+=g*h[j]
                    if h[j]>0:
                        d=g*self.v[j];gb[j]+=d
                        for i in range(16):gw[j][i]+=d*x[i]
            lr=.05/len(rows);self.a-=lr*ga
            for j in range(8):
                self.v[j]-=lr*gv[j];self.b[j]-=lr*gb[j]
                for i in range(16):self.w[j][i]-=lr*gw[j][i]

def readcase(p):
    with open(p,encoding='utf8') as f:
        k,q,m,w,r,pen=map(int,f.readline().split());n,period=map(int,f.readline().split())
        for _ in range(k):next(f)
        ops=[]
        for line in f:
            a=line.split();typ=a[0];o=int(a[1]);pid=int(a[2])%q if len(a)>2 else 0;z=int(a[3]) if len(a)>3 else 0
            ops.append((typ,o,pid,z))
    assert len(ops)==n
    return (k,q,m,w,r,pen,period),ops

def export(model):
    vals=','.join(format(x,'.9g')+'f' if '.' in format(x,'.9g') or 'e' in format(x,'.9g') else format(x,'.9g')+'.0f' for x in model.flat())
    (ROOT/'models').mkdir(exist_ok=True)
    (ROOT/'models/weights.inc').write_text(vals,encoding='ascii')
    policy=ROOT/'policies/tiny_nn.hpp';source=policy.read_text(encoding='utf8')
    source=source.replace('#include "../models/weights.inc"','// BEGIN TRAINED WEIGHTS\n'+vals+'\n// END TRAINED WEIGHTS')
    source=re.sub(r'// BEGIN TRAINED WEIGHTS\n.*?\n// END TRAINED WEIGHTS','// BEGIN TRAINED WEIGHTS\n'+vals+'\n// END TRAINED WEIGHTS',source,flags=re.S)
    policy.write_text(source,encoding='utf8')

def main():
    started=time.perf_counter();rng=random.Random(SEED);rows=[];evidence=[]
    physics_gate=ROOT/'teacher_physics_gate.json'
    if not json.loads(physics_gate.read_text(encoding='utf-8-sig')).get('passed'):raise RuntimeError('independent official prefix gate not passed')
    names=['cross_operator_1','temporal_2','combined_1','control_3']
    for name in names:
        p=ROOT.parent/'round54_mixture_release/data_v2/train'/('r54_'+name+'_train.txt')
        header,ops=readcase(p);limit=min(len(ops),8192);teacher={}
        for mode in ('bf','ng'):
            s=State(*header)
            for j,c in enumerate(ops[:limit]):s.event(c,ops[j+1] if j+1<len(ops) else None,mode)
            teacher[mode]=s.cost
        mode='ng' if teacher['ng']<teacher['bf'] else 'bf'
        s=State(*header);samples=[];eligible=0
        for j,c in enumerate(ops[:limit]):
            nxt=ops[j+1] if j+1<len(ops) else None;t=c[1]*s.p+c[2]
            callback=(c[0]=='INSERT' and s.res[t] and s.used+c[3]>s.m) or (c[0]=='PROBE' and not s.res[t])
            if callback:
                d,b,l,_=s.candidates(c)
                if d>0 and b is not None and b!=l:
                    eligible+=1;item=(j,copy.deepcopy(s),b,l)
                    if len(samples)<32:samples.append(item)
                    else:
                        z=rng.randrange(eligible)
                        if z<32:samples[z]=item
            s.event(c,nxt)
        for j,state,b,l in sorted(samples,key=lambda z:z[0]):
            costs=[]
            for first in (b,l):
                branch=copy.deepcopy(state);base=branch.cost
                for h in range(j,min(len(ops),j+32)):
                    branch.event(ops[h],ops[h+1] if h+1<len(ops) else None,force=first if h==j else None)
                costs.append(branch.cost-base)
            nxt=ops[j+1] if j+1<len(ops) else None
            pref=state.plan(ops[j],nxt,mode)
            teacher_y=teacher_preference(pref,b,l)
            physical=(costs[0]-costs[1])/(abs(costs[0])+abs(costs[1])+1.)
            y=.75*physical+.25*teacher_y
            rows.append((features(state,ops[j],nxt,b,l),y))
            evidence.append(dict(case=p.name,step=j+1,B=b,L=l,cost_B=costs[0],cost_L=costs[1],teacher=mode,teacher_preference=teacher_y,physical_target=physical,target=y))
        if time.perf_counter()-started>23:raise TimeoutError('bounded preparation exceeded23s')
        evidence.append(dict(case=p.name,sha256=sha(p),teacher_prefix_events=limit,teacher_prefix_costs=teacher,eligible_prefix_states=eligible,sampled=len(samples)))
    if not rows:raise RuntimeError('no eligible labels')
    model=Model(SEED);before=sum((model.forward(x)[0]-y)**2 for x,y in rows)/len(rows)
    model.train(rows,64);after=sum((model.forward(x)[0]-y)**2 for x,y in rows)/len(rows)
    export(model)
    (ROOT/'models/xy.json').write_text(json.dumps(dict(x=[x for x,y in rows],y=[y for x,y in rows])),encoding='utf8')
    (ROOT/'models/labels.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
    report=dict(seed=SEED,states=len(rows),branches=2*len(rows),horizon_events=32,gradient_steps=64,optimizer_updates=64,parameters=145,dense_MACs_per_forward=136,loss_before=before,loss_after=after,training_seconds=time.perf_counter()-started,teacher_scope='bounded first8192 original events per training case, not fullcase',deployment_features='callback state and next_op only; no lambda or future',eval_used=False,trained_candidate_validation='training loss and unit physics only; no performance validation',source_sha256=sha(__file__),weights_sha256=sha(ROOT/'models/weights.inc'),xy_sha256=sha(ROOT/'models/xy.json'))
    labels=[e for e in evidence if 'target' in e];cases=[e for e in evidence if 'teacher_prefix_costs' in e]
    report.update(teacher_missing=sum(e['teacher_preference']==0 for e in labels),
                  physical_ties=sum(e['physical_target']==0 for e in labels),
                  sign_disagreements=sum(e['physical_target']*e['teacher_preference']<0 for e in labels),
                  physical_only_recommended_counts={key:sum((e['physical_target']>0 if key=='L' else e['physical_target']<0 if key=='B' else e['physical_target']==0) for e in labels) for key in ['B','L','tie']},
                  teacher_selected_prefix_rule_counts={key:sum(('ng' if e['teacher_prefix_costs']['ng']<e['teacher_prefix_costs']['bf'] else 'bf')==key for e in cases) for key in ['bf','ng']},
                  teacher_prefix_cost_ties=sum(e['teacher_prefix_costs']['ng']==e['teacher_prefix_costs']['bf'] for e in cases),
                  mixture_risk='The .25 teacher preference can overwhelm small .75 physical targets; no improvement guarantee.',
                  teacher_physics_gate_sha256=sha(physics_gate),
                  teacher_physics_gate_scope='Independent original cross_operator_1_train first2048 events BF/NG ordered actions and physical ledger; not all cases or whole streams',
                  policy_sha256=sha(ROOT/'policies/tiny_nn.hpp'))
    (ROOT/'models/training.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
if __name__=='__main__':main()
