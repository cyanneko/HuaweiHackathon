"""Offline compact aggregate/action parity. Not per-partition fullstate parity.

Original engine physics and timing code are retained. Trace files are streamed;
only one original core State is retained and its emitted path row is popped.
"""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
O=Path(__file__).resolve().parent;B=O.parent;R67=B/'round67_offline_quality'
sys.path.insert(0,str(B/'round66_offline_oracle'))
from core import Case,State,next_public
BUILD=O/'framework';EXE=BUILD/'compact_dispatch'
MODES=('actual_naive','actual_r65')
WITNESS_FORMAT='core-json-array-canonical-v1'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def linux(path):
    p=str(Path(path).resolve());return '/mnt/'+p[0].lower()+p[2:].replace('\\','/')
def check(deadline):
    if deadline is not None and time.perf_counter()>=deadline:raise TimeoutError('compact harness deadline')
def native(args,stdout,stderr,deadline=None,default_timeout=180):
    check(deadline);start=time.perf_counter();timeout=default_timeout if deadline is None else deadline-start
    with Path(stdout).open('wb') as out,Path(stderr).open('wb') as err:
        p=subprocess.run(args,stdout=out,stderr=err,timeout=timeout)
    if p.returncode:raise RuntimeError(f'compact native exit {p.returncode}: {stderr}')
    check(deadline);return time.perf_counter()-start

WRAPPER=r'''
#include <stdexcept>
class WitnessScheduler:public SpillScheduler {
 std::ifstream input;
 std::vector<Action> step(char tag,int o,int p,int64_t need){
 char expected;int eo,ep,count;int64_t en;
 if(!(input>>expected>>eo>>ep>>en>>count)||expected!=tag||eo!=o||ep!=p||en!=need||count<0)throw std::runtime_error("witness callback mismatch");
 std::vector<Action>a;for(int i=0;i<count;++i){char type;int op,pid;if(!(input>>type>>op>>pid)||(type!='S'&&type!='L'))throw std::runtime_error("witness parse");a.emplace_back(type=='S'?Action::SPILL:Action::LOAD,op,pid);}return a;
 }
 public:explicit WitnessScheduler(const char*path):input(path){if(!input)throw std::runtime_error("witness open");}
 ~WitnessScheduler(){std::string extra;assert(!(input>>extra)&&"unconsumed witness callbacks");}
 std::vector<Action>onMemoryOverflow(const SystemState&,int o,int p,int64_t n)override{return step('O',o,p,n);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return step('M',o,p,s.operators[o].partitions[p].data_size);}
 std::vector<Action>onPeriodicAdjust(const SystemState&)override{return step('P',-1,-1,0);}
};
class CompactDispatch:public SpillScheduler {
 std::unique_ptr<SpillScheduler> inner;std::uint64_t seq=0;
 std::vector<Action> step(const SystemState&s,char tag,int o,int p,int64_t n){
 std::vector<Action>a;if(tag=='O')a=inner->onMemoryOverflow(s,o,p,n);else if(tag=='M')a=inner->onPartitionMiss(s,o,p);else a=inner->onPeriodicAdjust(s);
 std::ostringstream trace;trace<<"R69TRACE "<<seq++<<' '<<tag<<' '<<o<<' '<<p<<' '<<n<<' '<<s.memory_used<<' '<<s.hit_count<<' '<<s.miss_count<<' '<<s.total_io_bytes<<' '<<(s.next_op.type.empty()?"-":s.next_op.type)<<' '<<s.next_op.op_id<<' '<<s.next_op.key<<' '<<s.next_op.tuple_size;
 trace<<' '<<a.size();for(const auto&v:a)trace<<' '<<(v.type==Action::SPILL?'S':'L')<<' '<<v.op_id<<' '<<v.partition_id;trace<<'\n';std::cerr<<trace.str();return a;
 }
 public:CompactDispatch(const char*mode,const char*file){std::string m(mode);
 if(m=="actual_naive")inner=std::make_unique<OriginalNaive>();
 else if(m=="actual_r65")inner=std::make_unique<R65TurnoverRisk>();
 else if(m=="witness")inner=std::make_unique<WitnessScheduler>(file);
 else throw std::runtime_error("unknown compact mode");}
 std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,int64_t n)override{return step(s,'O',o,p,n);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return step(s,'M',o,p,s.operators[o].partitions[p].data_size);}
 std::vector<Action>onPeriodicAdjust(const SystemState&s)override{return step(s,'P',-1,-1,0);}
};
'''

def prepare():
    BUILD.mkdir(parents=True,exist_ok=True);frame=B/'round49_latency_baseline/reference_compilable.cpp'
    helpers=B/'round65_deficit_risk/dependencies/frozen_helpers.hpp';policy=B/'round65_deficit_risk/policy.hpp'
    raw=frame.read_text(encoding='utf-8');first=raw.index('class NaiveSpillScheduler');last=raw.index('class HashJoinEngine');needle='std::make_unique<NaiveSpillScheduler>()'
    suffix=raw[last:];assert suffix.count(needle)==1
    replacement='std::make_unique<CompactDispatch>(argc>2?argv[2]:"actual_naive",argc>3?argv[3]:"")'
    altered=suffix.replace(needle,replacement);assert altered.replace(replacement,needle)==suffix
    cpp=BUILD/'compact_dispatch.cpp';cpp.write_text(raw[:first]+raw[first:last].replace('NaiveSpillScheduler','OriginalNaive')+helpers.read_text(encoding='utf-8')+policy.read_text(encoding='utf-8')+WRAPPER+altered,encoding='utf-8')
    elapsed=native(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(cpp),'-o',linux(EXE)],BUILD/'compile.stdout.log',BUILD/'compile.stderr.log',default_timeout=30)
    manifest={'framework_sha256':sha(frame),'helpers_sha256':sha(helpers),'R65_policy_sha256':sha(policy),'source_sha256':sha(cpp),'binary_sha256':sha(EXE),'compile_seconds':elapsed,'engine_suffix_identical_except_factory':True,'original_Naive_sort_retained':True,'trace_scope':'aggregate counters, memory_used, next operation identity and complete actions; no per-partition fullstate trace','formal_D':None}
    (BUILD/'manifest.json').write_text(json.dumps(manifest,indent=2));return manifest

def iter_witness(path):
    """Incremental decoder for a JSON array; no complete witness list in RAM."""
    decoder=json.JSONDecoder();buffer='';eof=False;started=False;ended=False;need_value=True;after_comma=False
    with Path(path).open(encoding='utf-8') as stream:
        while True:
            buffer=buffer.lstrip()
            if not started:
                if buffer:
                    if buffer[0]!='[':raise ValueError('witness must be a JSON array')
                    buffer=buffer[1:];started=True;continue
            elif ended:
                if buffer:raise ValueError('trailing witness content')
                if eof:return
            elif buffer:
                if need_value:
                    if buffer[0]==']':
                        if after_comma:raise ValueError('trailing witness comma')
                        ended=True;buffer=buffer[1:];continue
                    try:row,end=decoder.raw_decode(buffer)
                    except json.JSONDecodeError:
                        if eof:raise
                    else:
                        if not isinstance(row,dict):raise ValueError('witness row must be object')
                        yield row;buffer=buffer[end:];need_value=False;after_comma=False;continue
                else:
                    if buffer[0]==',':buffer=buffer[1:];need_value=True;after_comma=True;continue
                    if buffer[0]==']':ended=True;buffer=buffer[1:];continue
                    raise ValueError('missing witness delimiter')
            if eof:raise ValueError('incomplete witness array')
            block=stream.read(65536)
            if block:buffer+=block
            else:eof=True

def write_witness(rows,path,deadline=None):
    """Stream core path rows into our canonical JSON-array format.

    semantic hash equals core.digest(list(rows)); consumes any iterable once.
    The caller may pass done.path, then delete the completed State immediately.
    """
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.incomplete');h=hashlib.sha256();h.update(b'[');count=0
    with temp.open('w',encoding='utf-8',newline='\n') as stream:
        stream.write('[')
        for row in rows:
            check(deadline);text=(',' if count else '')+json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)
            stream.write(text);h.update(text.encode());count+=1
        stream.write(']');h.update(b']');stream.flush();os.fsync(stream.fileno())
    check(deadline);os.replace(temp,path)
    return {'witness_path':str(path.resolve()),'witness_hash':h.hexdigest(),'witness_raw_sha256':sha(path),'witness_format':WITNESS_FORMAT,'callbacks':count}

def costs(s):return {'G':s.g,'ordered_objective':s.ordered_io+s.c.penalty*s.miss,'grouped_objective':s.g/(s.c.w*s.c.r),'ordered_io':s.ordered_io,'grouped_io':s.write/s.c.w+s.read/s.c.r,'write_bytes':s.write,'read_bytes':s.read,'total_io_bytes':s.write+s.read,'hits':s.hit,'misses':s.miss,'D':None}

def _case(input_path,case):
    actual=sha(input_path)
    if case is None:case=Case.read(input_path)
    if case.input_hash!=actual:raise ValueError('provided Case input identity mismatch')
    return case

def _prefix(s,seq):
    tag,t,need=s.callback;c=s.c;n=next_public(s)
    return list(map(str,['R69TRACE',seq,tag,t//c.p if tag!='P' else -1,t%c.p if tag!='P' else -1,need,s.used,s.hit,s.miss,s.write+s.read,n[0] or '-',n[1],n[2] if len(n)>2 else 0,n[3] if len(n)>3 else 0]))

def _execute(input_path,mode,out,case,deadline,actions=None,expected_witness_hash=None):
    start=time.perf_counter();out=Path(out);out.mkdir(parents=True,exist_ok=True);manifest=json.loads((BUILD/'manifest.json').read_text())
    if sha(EXE)!=manifest['binary_sha256']:raise ValueError('changed compact binary')
    argv=['wsl','-d','Ubuntu','--',linux(EXE),linux(input_path),mode]
    if actions is not None:argv.append(linux(actions))
    native_seconds=native(argv,out/'engine.stdout.log',out/'trace.stderr.log',deadline)
    s=State(case);seq=0;h=hashlib.sha256();h.update(b'[');temp=out/'witness.incomplete.json';wp=out/'witness.json'
    with temp.open('w',encoding='utf-8',newline='\n') as witness_out,(out/'trace.stderr.log').open(encoding='utf-8',errors='replace') as traces:
        witness_out.write('[')
        for line in traces:
            if 'R69TRACE ' not in line:continue
            check(deadline);tok=('R69TRACE '+line.split('R69TRACE ',1)[1]).split();assert s.advance(),'unexpected extra callback'
            prefix=_prefix(s,seq);assert tok[:len(prefix)]==prefix,(seq,'compact aggregate/public mismatch')
            count=int(tok[len(prefix)]);tail=tok[len(prefix)+1:];assert count>=0 and len(tail)==count*3
            tag,target,need=s.callback;spill=[];loaded=False;seen=set()
            for j in range(count):
                kind,o,p=tail[j*3:j*3+3];o=int(o);p=int(p);assert 0<=o<case.k and 0<=p<case.p;i=o*case.p+p
                assert i not in seen;seen.add(i)
                if kind=='S':assert not loaded and tag!='P' and i!=target and s.mem[i] and s.sizes[i]>0;spill.append(i)
                else:
                    assert kind=='L' and tag=='M' and not loaded and j+1==count and i==target and not s.mem[i] and s.phase[o];loaded=True
            assert (tag=='M')==loaded;assert tag!='P' or count==0
            s.apply(tuple(spill));row=s.path.pop();encoded=json.dumps(row,sort_keys=True,separators=(',',':'))
            separator=',' if seq else '';witness_out.write(separator+encoded);h.update((separator+encoded).encode());seq+=1
        assert not s.advance(),'missing compact callbacks'
        witness_out.write(']');h.update(b']');witness_out.flush();os.fsync(witness_out.fileno())
    check(deadline);witness_hash=h.hexdigest()
    if expected_witness_hash is not None:assert witness_hash==expected_witness_hash,'official actions differ from provided witness'
    metrics={k:float(v.strip()) for line in (out/'engine.stdout.log').read_text(encoding='utf-8',errors='replace').splitlines() if ':' in line for k,v in [line.split(':',1)]}
    assert metrics['Hit_Count']==s.hit and metrics['Miss_Count']==s.miss
    assert abs(metrics['Total_IO_Time']-s.ordered_io)<=.011,'official rounded IO mismatch'
    os.replace(temp,wp);report={'mode':mode,'input':str(Path(input_path).resolve()),'input_sha256':case.input_hash,'cost':costs(s),'callbacks':seq,'witness_path':str(wp.resolve()),'witness_hash':witness_hash,'witness_raw_sha256':sha(wp),'binary_sha256':manifest['binary_sha256'],'source_sha256':manifest['source_sha256'],'framework_source_sha256':manifest['framework_sha256'],'harness_sha256':sha(Path(__file__)),'core_source_sha256':sha(B/'round66_offline_oracle/core.py'),'replay_verified':True,'legal_complete_witness':True,'all_callbacks_consumed':True,'aggregate_public_actions_match':True,'full_partition_state_compared':False,'byte_ledger_matches_every_callback':True,'native_process_seconds':native_seconds,'end_to_end_seconds':time.perf_counter()-start,'formal_D':None,'verification_scope':'compact aggregate/public/action parity, not per-partition fullstate parity'}
    report['witness_format']=WITNESS_FORMAT
    check(deadline);(out/'report.json').write_text(json.dumps(report,indent=2));return report

def run_baseline(input_path,mode,out_dir,*,case=None,deadline=None):
    if mode not in MODES:raise ValueError('only actual_naive / actual_r65')
    check(deadline);case=_case(input_path,case);return _execute(input_path,mode,out_dir,case,deadline)

def verify_witness(input_path,witness_path,out_dir,*,case=None,deadline=None):
    check(deadline);case=_case(input_path,case);out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);s=State(case);seq=0;h=hashlib.sha256();h.update(b'[')
    with (out/'actions.txt').open('w',encoding='utf-8') as actions:
        for row in iter_witness(witness_path):
            check(deadline);assert s.advance(),'extra provided witness row';tag,t,need=s.callback
            assert (s.raw,s.stage,tag)==(row['raw'],row['stage'],row['kind'])
            spill=tuple(row['spill']);s.apply(spill);actual=s.path.pop();assert actual==row,'noncanonical provided path row'
            encoded=json.dumps(actual,sort_keys=True,separators=(',',':'));h.update(((',' if seq else '')+encoded).encode());seq+=1
            acts=[('S',i//case.p,i%case.p) for i in spill]
            if tag=='M':acts.append(('L',t//case.p,t%case.p))
            tokens=[tag,t//case.p if tag!='P' else -1,t%case.p if tag!='P' else -1,need,len(acts)]
            for a in acts:tokens.extend(a)
            actions.write(' '.join(map(str,tokens))+'\n')
        assert not s.advance(),'incomplete provided witness';h.update(b']')
    del s;check(deadline)
    return _execute(input_path,'witness',out,case,deadline,out/'actions.txt',h.hexdigest())

if __name__=='__main__':print(json.dumps(prepare(),indent=2))
