"""Independent raw-request/byte audit; no use of scheduler's model or future labels."""
import json,math,copy
from pathlib import Path

def trace_lines(path):
    with Path(path).open('rb') as f:return [x for x in f if x.startswith(b'TRACE ')]

class Ledger:
    def __init__(self,header):
        self.k,self.p,self.m,self.w,self.r,self.penalty,self.n,self.b=header
        self.sizes=[0]*(self.k*self.p);self.mem=[True]*len(self.sizes);self.phases=[False]*self.k
        self.used=self.count=self.writes=self.reads=self.hits=self.misses=0
    def clone(self):
        c=copy.copy(self);c.sizes=self.sizes.copy();c.mem=self.mem.copy();c.phases=self.phases.copy();return c
    def state(self):
        return {'writes':self.writes,'reads':self.reads,'hits':self.hits,'misses':self.misses,'used':self.used,'counter':self.count,
                'resident':''.join('1' if x else '0' for x in self.mem),'phases':''.join('P' if x else 'B' for x in self.phases)}
    def verify(self,state):
        assert self.state()=={k:state[k] for k in self.state()},(self.state(),state)
    def apply(self,line,tag,op=-1,pid=-1,z=0):
        t=line.decode().split();assert t[:2]==['TRACE',tag] and list(map(int,t[2:5]))==[op,pid,z]
        count=int(t[5]);assert len(t)==6+3*count
        actions=[[t[6+3*j],int(t[7+3*j]),int(t[8+3*j])] for j in range(count)]
        if tag=='M':assert actions and actions[-1]==['L',op,pid]
        seen=set()
        for typ,o,pa in actions:
            assert 0<=o<self.k and 0<=pa<self.p and (typ,o,pa) not in seen;seen.add((typ,o,pa))
            i=o*self.p+pa;size=self.sizes[i]
            if typ=='S':
                assert self.mem[i] and size>0 and (tag!='O' or (o,pa)!=(op,pid))
                self.mem[i]=False;self.used-=size;self.writes+=size
            else:
                assert typ=='L' and tag!='O' and self.phases[o] and not self.mem[i]
                self.mem[i]=True;self.used+=size;self.reads+=size
            assert 0<=self.used<=self.m
        if tag=='O':assert self.used+z<=self.m
        return actions
    def step(self,op,callback,after_current=None):
        typ,o=op[:2]
        if typ=='SWITCH':self.phases[o]=True;return
        pid=op[2];i=o*self.p+pid
        if typ=='INSERT':
            z=op[3]
            if self.mem[i]:
                if self.used+z>self.m:callback('O',o,pid,z)
                self.used+=z
            else:self.writes+=z
            self.sizes[i]+=z
        elif self.mem[i]:self.hits+=1
        else:
            self.misses+=1;callback('M',o,pid,0)
            if after_current is not None:after_current(self)
        self.count+=1
        if self.count%self.b==0:callback('P',-1,-1,0)

class CaseAudit:
    def __init__(self,header,ops,reference,states,phase_a_row):
        self.header,self.ops,self.states=header,ops,{x['id']:x for x in states}
        self.reference=trace_lines(reference);self.snapshots={};self.starts={};self.ends={};self.checked={}
        self.samples={x['q']:x for x in phase_a_row['observation_audit']['samples']}
        starts={s['raw_operation_index_zero_based']:s['id'] for s in states}
        endpoints={}
        for s in states:
            for h in [4096,8192]:endpoints.setdefault(s['raw_operation_index_zero_based']+h-1,[]).append((s['id'],h))
        self.base=Ledger(header);self.index=0;self.raw_stop=max(endpoints)
        def callback(tag,o,pid,z):
            line=self.reference[self.index];self.index+=1;self.base.apply(line,tag,o,pid,z)
        for raw,op in enumerate(ops):
            if raw>self.raw_stop:break
            if raw in starts:
                id=starts[raw];self.snapshots[id]=self.base.clone();self.starts[id]=self.index
                assert all(self.base.phases) and op[0]=='PROBE' and not self.base.mem[op[1]*self.base.p+op[2]]
            self.base.step(op,callback)
            for key in endpoints.get(raw,[]):self.ends[key]=self.index
        assert len(self.snapshots)==len(states)
    def collector_prefix(self,path,completed=None):
        lines=trace_lines(path);assert lines==self.reference[:len(lines)],'collector TRACE differs'
        if completed:
            raw=completed['raw_end_inclusive'];last=max(self.states.values(),key=lambda s:s['raw_operation_index_zero_based'])
            assert raw==last['raw_operation_index_zero_based']
            ledger=self.snapshots[last['id']].clone();i=self.starts[last['id']]
            def callback(tag,o,pid,z):
                nonlocal i
                ledger.apply(self.reference[i],tag,o,pid,z);i+=1
            ledger.step(self.ops[raw],callback);assert len(lines)==i;ledger.verify(completed['state'])
        return len(lines)
    def row(self,row,folder):
        id=row['state_id'];assert id not in self.checked
        selected=self.states[id];raw=selected['raw_operation_index_zero_based'];start=self.snapshots[id]
        assert row['raw_start']==raw and row['q0']==selected['q'];start.verify(row['before'])
        assert row['history']==selected['history'] and row['dynamic']==selected['dynamic']
        assert set(map(tuple,row['history']))!=set(map(tuple,row['dynamic']))
        sample=self.samples[row['q0']]
        for key in ['immediate','mean','sd','effective','margin']:assert math.isclose(row[key],sample[key],rel_tol=2e-10,abs_tol=2e-8),(key,row[key],sample[key])
        assert row['original_dynamic']==sample['chosen_dynamic']==selected['phase_a_original_dynamic_choice']
        original=(row['dynamic'] if row['original_dynamic'] else row['history'])+[['L',*self.ops[raw][1:3]]]
        assert row['original']==original
        before=row['before']['policy_summary'];prepared=row['prepared_policy']
        assert prepared['miss_calls']==before['miss_calls']+1
        assert len(row['branches'])==4
        comparisons={};details=[]
        for branch in row['branches']:
            c,a=branch['continuation'],branch['action'];assert (c,a) not in comparisons and c in [0,1] and a in [0,1]
            traces=trace_lines(Path(folder)/branch['trace']);ledger=start.clone();index=0
            expected=(row['dynamic'] if a else row['history'])+[['L',*self.ops[raw][1:3]]]
            def callback(tag,o,pid,z):
                nonlocal index
                acts=ledger.apply(traces[index],tag,o,pid,z)
                if index==0:assert acts==expected
                index+=1
            def immediate(l):
                l.verify(branch['after_current_actions'])
                got=branch['after_current_actions']['policy_summary'].copy();got.pop('continuation')
                want=prepared.copy();want.pop('continuation');assert got==want,'repeated current policy update'
                assert branch['after_current_actions']['policy_summary']['continuation']==c
            endpoint_rows={e['horizon']:e for e in branch['endpoints']};assert set(endpoint_rows)=={4096,8192}
            branch_deltas={}
            for i in range(raw,raw+8192):
                assert self.ops[i][0]=='PROBE'
                ledger.step(self.ops[i],callback,immediate if i==raw else None)
                h=i-raw+1
                if h in endpoint_rows:
                    e=endpoint_rows[h];assert e['raw_end_inclusive']==i and e['q_end']==row['q0']+h-1
                    assert ledger.hits+ledger.misses==e['q_end'];ledger.verify(e['state'])
                    delta={k:getattr(ledger,k)-getattr(start,k) for k in ['writes','reads','hits','misses']}
                    assert delta['hits']+delta['misses']==h
                    delta['cost100_us']=delta['writes']/ledger.w+delta['reads']/ledger.r+100*delta['misses']
                    delta['resident']=e['state']['resident'];delta['used']=e['state']['used']
                    branch_deltas[h]=delta
                    if c==0 and a==row['original_dynamic']:
                        assert traces[:index]==self.reference[self.starts[id]:self.ends[id,h]],'C0 original TRACE differs'
            assert index==len(traces),'extra branch callbacks'
            comparisons[c,a]=branch_deltas
            details.append({'continuation':c,'action':a,'callbacks':index,'endpoints':branch_deltas,
                            'independent_bytes_clocks_and_actions_pass':True})
        delta_rows=[]
        for c in [0,1]:
            for h in [4096,8192]:
                history,dynamic=comparisons[c,0][h],comparisons[c,1][h]
                differences={k:history[k]-dynamic[k] for k in ['writes','reads','misses','hits']}
                # Compute signed physical deltas directly, avoiding subtraction of large suffix totals.
                cost=differences['writes']/start.w+differences['reads']/start.r+100*differences['misses']
                delta_rows.append({'continuation':c,'horizon':h,**differences,'delta100_us':cost,
                    'resident_equal':history['resident']==dynamic['resident'],'resident_xor_objects':sum(x!=y for x,y in zip(history['resident'],dynamic['resident']))})
        result={'state_id':id,'C0_original_trace_exact_both_endpoints':True,'current_miss_update_exactly_once':True,
                'branches':details,'deltas_history_minus_dynamic':delta_rows}
        self.checked[id]=result;return result
