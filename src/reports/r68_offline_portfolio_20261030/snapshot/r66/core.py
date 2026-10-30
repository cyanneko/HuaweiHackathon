"""R66 Python reference v1. No full-hit observer; no beam state merging.

Text contract: overflow spill-only, demand-load last, periodic empty.
R65 history is a semantic port of round65_deficit_risk/policy.hpp.
Python is the reference; online C++ parity is a separate required gate.
"""
import copy, hashlib, itertools, json, struct, time
from dataclasses import dataclass, field
from pathlib import Path

POOL_VERSION='r66-eight-plans-v1'
FEATURE_VERSION='r66-f16-v1'
OBSERVER_VERSION='r65-causal-port-v1'
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def f32(x): return struct.unpack('f',struct.pack('f',x))[0]

@dataclass
class Case:
    k:int; p:int; m:int; w:int; r:int; penalty:int; b:int; ops:list
    input_hash:str=''
    @classmethod
    def read(cls,path):
        data=Path(path).read_bytes(); lines=data.decode().splitlines()
        k,p,m,w,r,pen=map(int,lines[0].split()); n,b=map(int,lines[1].split())
        ops=[]
        for line in lines[2+k:]:
            a=line.split(); ops.append((a[0],*map(int,a[1:])))
        assert len(ops)==n and min(m,w,r,b)>0
        return cls(k,p,m,w,r,pen,b,ops,hashlib.sha256(data).hexdigest())

@dataclass
class History:
    slots:list=field(default_factory=list)
    pending:list=field(default_factory=list)
    load:object=None
    clock:int=0
    initialized:bool=False
    @staticmethod
    def age(h,a,t):
        d=(t-a)//64
        return (0,t) if d>=h else (h-d,a+d*64)
    def touch(self,s,i):
        x=self.slots[i]
        if x[0]!=s.sizes[i]: x[:]=[s.sizes[i],0,self.clock,-1,-1]
        x[1],x[2]=self.age(x[1],x[2],self.clock)
        x[1]=min(x[1],s.c.m//x[0]) if x[0]>0 else 0
        return x
    def observe(self,s):
        t=s.hit+s.miss
        if not self.initialized:
            self.initialized=True;self.clock=t
            self.slots=[[-1,0,0,-1,-1] for _ in s.sizes];return
        assert t>=self.clock
        self.clock=t
        for i,size,clock in self.pending:
            x=self.touch(s,i)
            if x[0]==size and not s.mem[i]:x[3]=clock
        self.pending=[]
        if self.load is not None:
            i,size,clock,h,a,reward=self.load;x=self.touch(s,i)
            if x[0]==size and s.mem[i]:
                x[3]=-1
                if reward and x[4]!=clock:
                    x[1],x[2]=self.age(h,a,self.clock);x[4]=clock
            self.load=None
    def effective(self,s,i):
        # Pure read equivalent to R65 touch, including size reset and cap.
        x=self.slots[i]
        if x[0]!=s.sizes[i]:return 0
        h,_=self.age(x[1],x[2],self.clock)
        return min(h,s.c.m//s.sizes[i]) if s.sizes[i]>0 else 0
    def record(self,s,spill,target,miss):
        self.pending=[];self.load=None
        for i in spill:
            if s.phase[i//s.c.p]:
                self.touch(s,i);self.pending.append((i,s.sizes[i],self.clock))
        if miss:
            x=self.touch(s,target);size=s.sizes[target]
            reward=s.phase[target//s.c.p] and size>0 and x[3]>=0 and 0<=self.clock-x[3]<=64 and x[4]!=self.clock
            h=min(x[1]+1,s.c.m//size) if reward else x[1]
            self.load=(target,size,self.clock,h,x[2] if x[1] else self.clock,reward)

@dataclass
class State:
    c:Case
    sizes:list=field(default_factory=list)
    mem:list=field(default_factory=list)
    phase:list=field(default_factory=list)
    raw:int=0
    stage:str='start'
    count:int=0
    hit:int=0
    miss:int=0
    write:int=0
    read:int=0
    ordered_io:float=0.
    h:History=field(default_factory=History)
    callback:object=None
    path:list=field(default_factory=list)
    def __post_init__(self):
        if not self.sizes:self.sizes=[0]*(self.c.k*self.c.p);self.mem=[True]*len(self.sizes);self.phase=[False]*self.c.k
    def clone(self):
        # immutable input shared; all physical/history/path state cloned.
        memo={id(self.c):self.c};return copy.deepcopy(self,memo)
    @property
    def used(self):return sum(z for z,m in zip(self.sizes,self.mem) if m)
    @property
    def g(self):return self.write*self.c.r+self.read*self.c.w+self.c.penalty*self.miss*self.c.w*self.c.r
    def snapshot(self):
        # Anchors outlive this mutable trajectory. Freeze every nested array,
        # history slot, pending intent and callback, not just the outer dict.
        return copy.deepcopy({k:v for k,v in self.__dict__.items() if k not in ('c','path','h')}|{'history':self.h.__dict__})
    @classmethod
    def from_snapshot(cls,c,snapshot):
        """Reconstruct a causal anchor, including a JSON-roundtripped one."""
        data=copy.deepcopy(snapshot);history=data.pop('history')
        if data.get('callback') is not None:data['callback']=tuple(data['callback'])
        history['pending']=[tuple(a) for a in history['pending']]
        if history['load'] is not None:history['load']=tuple(history['load'])
        return cls(c=c,h=History(**history),**data)
    def addwrite(self,n):self.write+=n;self.ordered_io+=n/self.c.w
    def addread(self,n):self.read+=n;self.ordered_io+=n/self.c.r
    def advance(self,stop_raw=None):
        """Stop at next callback; positions are raw operation + substage."""
        while self.raw<len(self.c.ops) and (stop_raw is None or self.raw<stop_raw):
            op=self.c.ops[self.raw];typ,o=op[:2];target=o*self.c.p+(op[2]%self.c.p if len(op)>2 else 0)
            if self.stage=='start':
                if typ=='SWITCH':self.phase[o]=True;self.raw+=1;continue
                if typ=='INSERT':
                    if self.mem[target] and self.used+op[3]>self.c.m:
                        self.stage='insert';self.callback=('O',target,op[3]);self.h.observe(self);return True
                    self.stage='insert'
                else:
                    assert typ=='PROBE' and self.phase[o]
                    if self.mem[target]:self.hit+=1;self.stage='finish'
                    else:
                        self.miss+=1;self.stage='finish';self.callback=('M',target,self.sizes[target]);self.h.observe(self);return True
            if self.stage=='insert':
                n=op[3]
                if not self.mem[target]:self.addwrite(n)
                else:assert self.used+n<=self.c.m
                self.sizes[target]+=n;self.stage='finish'
            if self.stage=='finish':
                self.count+=1;self.stage='next'
                if self.count%self.c.b==0:
                    self.callback=('P',-1,0);self.h.observe(self);return True
            if self.stage=='next':self.raw+=1;self.stage='start'
        self.callback=None;return False
    def apply(self,spill):
        kind,t,need=self.callback;spill=tuple(spill)
        assert len(set(spill))==len(spill)
        assert kind!='P' or not spill
        assert all(0<=i<len(self.sizes) and self.mem[i] and self.sizes[i]>0 and i!=t for i in spill)
        assert self.used-sum(self.sizes[i] for i in spill)+need<=self.c.m
        if kind!='P':self.h.record(self,spill,t,kind=='M')
        for i in spill:self.addwrite(self.sizes[i]);self.mem[i]=False
        if kind=='M':
            assert not self.mem[t] and self.phase[t//self.c.p]
            self.addread(self.sizes[t]);self.mem[t]=True
        self.path.append({'raw':self.raw,'stage':self.stage,'kind':kind,'spill':list(spill)})
        self.callback=None

def next_public(s):return s.c.ops[s.raw+1] if s.raw+1<len(s.c.ops) else ('',-1)
def action_key(s,a):return ','.join(map(str,a))+('->'+str(s.callback[1]) if s.callback[0]=='M' else '')
def victim_cost(s,i):
    n=next_public(s);target=n[1]*s.c.p+n[2]%s.c.p if n[0] in ('PROBE','INSERT') else -1
    z=s.sizes[i];return z/s.c.w+int(s.phase[i//s.c.p])*z/s.c.r+int(n[0]=='PROBE' and i==target)*z/s.c.r+s.h.effective(s,i)*z*(1/s.c.w+1/s.c.r)
def pool(s):
    kind,t,need=s.callback;deficit=max(0,need-(s.c.m-s.used))
    if kind=='P' or deficit==0:return [()]
    eligible=[i for i,z in enumerate(s.sizes) if s.mem[i] and z>0 and i!=t]
    singles=[i for i in eligible if s.sizes[i]>=deficit]
    plans=[(i,) for i in sorted(singles,key=lambda i:(victim_cost(s,i),s.sizes[i],i))[:4]]
    if singles:plans.extend([(min(singles,key=lambda i:(s.sizes[i],i)),),(max(singles,key=lambda i:(s.sizes[i],-i)),)])
    # BF includes the smallest sufficient single, otherwise largest until fit.
    for mode in ('bf','largest'):
        left=deficit;avail=eligible[:];a=[]
        while left>0 and avail:
            enough=[i for i in avail if s.sizes[i]>=left]
            i=min(enough,key=lambda i:(s.sizes[i],i)) if mode=='bf' and enough else max(avail,key=lambda i:(s.sizes[i],-i))
            a.append(i);left-=s.sizes[i];avail.remove(i)
        if left<=0:plans.append(tuple(sorted(a)))
    result=list(dict.fromkeys(plans));assert result and len(result)<=8
    return result
def features(s,a):
    kind,t,need=s.callback;c=s.c;free=c.m-s.used;d=max(0,need-free);n=next_public(s)
    nt=n[1]*c.p+n[2]%c.p if n[0] in ('INSERT','PROBE') else -1
    b=sum(s.sizes[i] for i in a);p=sum(s.sizes[i] for i in a if s.phase[i//c.p]);u=sum(s.h.effective(s,i)*s.sizes[i] for i in a)
    c0=sum(victim_cost(s,i) for i in a);T=c.m*(1/c.w+1/c.r)
    x=[kind=='M',free/c.m,need/c.m,d/c.m,sum(z for i,z in enumerate(s.sizes) if s.mem[i] and s.phase[i//c.p])/c.m,s.miss/(s.hit+s.miss+1),b/c.m,(b-d)/c.m,len(a)/(len(a)+1),p/c.m,n[0]=='PROBE' and nt in a,max((s.sizes[i] for i in a),default=0)/c.m,u/(c.m+u),c0/(T+c0),c.w/(c.w+c.r),n[0]=='INSERT' and nt in a]
    return [f32(float(v)) for v in x]
def plan_order(s,a):return (features(s,a)[13],len(a),sum(s.sizes[i] for i in a),a)
def rollout(c,mode='base',witness=None):
    s=State(c);j=0
    while s.advance():
        plans=pool(s)
        if witness is not None:
            row=witness[j];assert (s.raw,s.stage,s.callback[0])==(row['raw'],row['stage'],row['kind']);a=tuple(row['spill']);j+=1
        elif mode in ('naive','r65'):
            kind,t,need=s.callback;left=max(0,need-(c.m-s.used));eligible=[i for i,z in enumerate(s.sizes) if s.mem[i] and z>0 and i!=t]
            singles=[i for i in eligible if s.sizes[i]>=left] if left else []
            if kind=='P' or left==0:a=()
            elif mode=='r65' and singles:a=(min(singles,key=lambda i:(victim_cost(s,i),s.sizes[i],i)),)
            else:
                chosen=[]
                while left>0:
                    enough=[i for i in eligible if s.sizes[i]>=left]
                    pick=min(enough,key=lambda i:(s.sizes[i],i)) if mode=='r65' and enough else max(eligible,key=lambda i:(s.sizes[i],-i))
                    chosen.append(pick);left-=s.sizes[pick];eligible.remove(pick)
                a=tuple(sorted(chosen))
            assert a in plans
        else:a=min(plans,key=lambda a:plan_order(s,a))
        s.apply(a)
    if witness is not None:assert j==len(witness)
    return s
def search(c,seconds=3.,width=8,exact=False):
    start=time.perf_counter();initial=[rollout(c),rollout(c,'naive'),rollout(c,'r65')];best=min(initial,key=lambda s:s.g)
    init=best.g;front=[State(c)];expanded=0;timeout=False
    if exact:assert c.k*c.p<=4 and len(c.ops)<=32
    for raw in range(len(c.ops)):
        pending=front;finished=[]
        while pending:
            s=pending.pop()
            if time.perf_counter()-start>=seconds:timeout=True;break
            if not s.advance(stop_raw=raw+1):
                finished.append(s)
                continue
            plans=pool(s)
            if exact and s.callback[0]!='P':
                _,t,need=s.callback;eligible=[i for i,z in enumerate(s.sizes) if s.mem[i] and z>0 and i!=t]
                plans=[a for n in range(len(eligible)+1) for a in itertools.combinations(eligible,n) if s.used-sum(s.sizes[i] for i in a)+need<=c.m]
            for a in plans:
                z=s.clone();z.apply(a);expanded+=1
                if z.g<=best.g:pending.append(z)
        if timeout:break
        # Prune only at equal RAW INPUT boundary, never callback ordinal.
        # No merging: history, clocks, counters, physical state all retained.
        front=finished if exact else sorted(finished,key=lambda s:s.g)[:width]
        if raw+1==len(c.ops):
            for s in front:
                if s.g<best.g:best=s
    verified=rollout(c,witness=best.path)
    assert verified.g==best.g and verified.snapshot()==best.snapshot()
    status='exact_in_declared_domain' if exact and not timeout else ('timeout_feasible' if timeout else 'restricted_best_found')
    return best,{'status':status,'expanded':expanded,'seconds':time.perf_counter()-start,'initial_G':init,'initial_baselines_G':dict(zip(('new_pool_base','largest_first','r65_style'),(x.g for x in initial))),'final_G':best.g,'write_bytes':best.write,'read_bytes':best.read,'misses':best.miss,'grouped_objective':best.g/(c.w*c.r),'ordered_objective':best.ordered_io+c.penalty*best.miss,'improvement_G':init-best.g,'width':width,'merge':'none','global_lower_bound':best.g if exact and not timeout else None,'objective_scope':'spill-subsets/demand-load-only/periodic-empty','internal_replay_verified':True,'replay_verified':False}
def demonstrations(c,witness,stats,trajectory_id,split='train'):
    s=State(c);rows=[];wh=digest(witness);j=0
    while s.advance():
        a=tuple(witness[j]['spill']);plans=pool(s);anchor=s.snapshot();hbefore=digest(s.h.__dict__)
        items=[{'action_key':action_key(s,p),'actions':[('SPILL',i//c.p,i%c.p) for i in p]+([('LOAD',s.callback[1]//c.p,s.callback[1]%c.p)] if s.callback[0]=='M' else []),'x':features(s,p),'base_score':features(s,p)[13],'legal':True} for p in plans]
        assert hbefore==digest(s.h.__dict__)
        if a in plans and len(plans)>1:
            rows.append({'trajectory_id':trajectory_id,'split':split,'callback_id':j,'anchor_id':f'{s.raw}:{s.stage}','anchor_snapshot_hash':digest(anchor),'history_snapshot_hash':hbefore,'full_state_snapshot':anchor,'input_hash':c.input_hash,'candidate_pool_version':POOL_VERSION,'feature_version':FEATURE_VERSION,'observer_version':OBSERVER_VERSION,'candidate_pool_hash':digest(items),'plans':items,'label_kind':'path_demo','selected_action_key':action_key(s,a),'teacher_status':stats['status'],'teacher_witness_hash':wh,'teacher_upper_bound':stats['final_G']/(c.w*c.r),'valid_lower_bound_or_null':None,'certified_gap_or_null':None,'quality_weight':.25,'label_scope':'replay_verified_complete_path','branches_or_null':None})
        s.apply(a);j+=1
    return rows
