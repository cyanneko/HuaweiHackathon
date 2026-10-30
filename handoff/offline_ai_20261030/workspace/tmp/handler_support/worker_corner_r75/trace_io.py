"""Strict native trace consumption; no false baseline when forcing was unused."""
import re
import time
import corner_state as adapter


def check_time(deadline):
    if deadline is not None and time.perf_counter()>=deadline:raise TimeoutError('single corner teacher budget exhausted')


def parse_line(line):
    tokens=line.split()
    if len(tokens)<11 or tokens[0]!='C':raise ValueError('not a complete native callback record')
    index=int(tokens[1]);kind=tokens[2];op,pid,need,q,physical,pre,post,count=map(int,tokens[3:11])
    if index<0 or kind not in ('O','M','P') or q<0 or count<0 or len(tokens)!=11+3*count:
        raise ValueError('invalid callback identity or truncated actions')
    actions=[[tokens[i],int(tokens[i+1]),int(tokens[i+2])] for i in range(11,len(tokens),3)]
    adapter.normalized(actions)
    return dict(index=index,kind=kind,op=op,pid=pid,need=need,q=q,physical_hash=physical,
                private_pre_hash=pre,private_post_hash=post,actions=actions)


def read_trace(path):
    with open(path,encoding='utf-8') as source:return [parse_line(line) for line in source if line.strip()]


def require_forced_end(stderr,callbacks):
    ends=re.findall(r'\bHANDLER_END\s+(\d+)\s+(\d+)',stderr)
    if len(ends)!=1 or tuple(map(int,ends[0]))!=(callbacks,1):
        raise ValueError('forced callback must be consumed exactly once with matching EOF callback count')
    return True


def advance(state,deadline=None):
    if state.callback is not None:return True
    while state.raw<len(state.c.ops):
        check_time(deadline)
        if state.advance(stop_raw=min(len(state.c.ops),state.raw+256)):return True
    return False


def check_callback(state,row,index):
    if state.callback is None:raise ValueError('native extra callback')
    kind,target,need=state.callback
    op=target//state.c.p if kind!='P' else -1
    pid=target%state.c.p if kind!='P' else -1
    actual=(index,kind,op,pid,need,state.hit+state.miss,adapter.physical_hash(state))
    expected=tuple(row[key] for key in ('index','kind','op','pid','need','q','physical_hash'))
    if actual!=expected:raise ValueError('native callback/public physical hash mismatch: '+str((index,actual,expected)))


def ledger(state):
    return dict(write_bytes=state.write,read_bytes=state.read,misses=state.miss,hits=state.hit,G=state.g)


def metrics(text):
    values={}
    for line in text.splitlines():
        if ':' not in line:continue
        key,value=line.split(':',1)
        if key in ('Hit_Count','Miss_Count','Total_IO_Time'):values[key]=float(value.strip())
    if set(values)!={'Hit_Count','Miss_Count','Total_IO_Time'}:raise ValueError('native aggregate metrics missing')
    return values


def check_metrics(state,values):
    if values['Hit_Count']!=state.hit or values['Miss_Count']!=state.miss:raise ValueError('native EOF hit/miss differs')
    if abs(values['Total_IO_Time']-state.ordered_io)>.011:raise ValueError('native EOF rounded IO differs')
