"""R67 offline-only frozen official engine and independent Python replay.

The executable dispatches actual frozen policies or reads a witness file. No
online deployment claim: file input and tracing belong only to verification.
"""
import hashlib, json, os, subprocess, sys, time
from pathlib import Path
O=Path(__file__).resolve().parent;B=O.parent;R66=B/'round66_offline_oracle'
sys.path.insert(0,str(R66))
from core import Case, State, digest, next_public
MODES=('actual_naive','actual_r65','newpool_base')
BUILD=O/'framework';EXE=BUILD/'offline_dispatch'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def linux(p):
    p=Path(p).resolve();return '/mnt/'+str(p)[0].lower()+str(p)[2:].replace('\\','/')
def run(args,log,timeout=30):
    start=time.perf_counter();p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    log=Path(log);log.parent.mkdir(parents=True,exist_ok=True);log.write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(f'{log}: exit {p.returncode}')
    return p,time.perf_counter()-start

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
class OfflineDispatch:public SpillScheduler {
 std::unique_ptr<SpillScheduler> inner;
 std::vector<Action> step(const SystemState&s,char tag,int o,int p,int64_t n){
 std::vector<Action>a;if(tag=='O')a=inner->onMemoryOverflow(s,o,p,n);else if(tag=='M')a=inner->onPartitionMiss(s,o,p);else a=inner->onPeriodicAdjust(s);
 std::ostringstream trace;trace<<"R67TRACE "<<tag<<' '<<o<<' '<<p<<' '<<n<<' '<<s.memory_used<<' '<<s.hit_count<<' '<<s.miss_count<<' '<<s.total_io_bytes<<' '<<(s.next_op.type.empty()?"-":s.next_op.type)<<' '<<s.next_op.op_id<<' '<<s.next_op.key<<' '<<s.next_op.tuple_size;
 for(const auto&op:s.operators){trace<<' '<<(op.phase==Phase::PROBE?1:0);for(const auto&v:op.partitions)trace<<' '<<v.data_size<<' '<<(v.in_memory?1:0);}
 trace<<' '<<a.size();for(const auto&v:a)trace<<' '<<(v.type==Action::SPILL?'S':'L')<<' '<<v.op_id<<' '<<v.partition_id;
 trace<<'\n';std::cerr<<trace.str();return a;
 }
 public:OfflineDispatch(const char*mode,const char*file){std::string m(mode);
 if(m=="actual_naive")inner=std::make_unique<OriginalNaive>();
 else if(m=="actual_r65")inner=std::make_unique<R65TurnoverRisk>();
 else if(m=="newpool_base")inner=std::make_unique<R66Scheduler<R66BaseScore>>();
 else if(m=="witness")inner=std::make_unique<WitnessScheduler>(file);
 else throw std::runtime_error("unknown offline mode");}
 std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,int64_t n)override{return step(s,'O',o,p,n);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return step(s,'M',o,p,s.operators[o].partitions[p].data_size);}
 std::vector<Action>onPeriodicAdjust(const SystemState&s)override{return step(s,'P',-1,-1,0);}
};
'''

def prepare():
    BUILD.mkdir(parents=True,exist_ok=True)
    framework=B/'round49_latency_baseline/reference_compilable.cpp'
    helpers=B/'round65_deficit_risk/dependencies/frozen_helpers.hpp';policy=B/'round65_deficit_risk/policy.hpp';shared=R66/'shared_pool.hpp'
    source=framework.read_text(encoding='utf-8');start=source.index('class NaiveSpillScheduler');end=source.index('class HashJoinEngine')
    naive=source[start:end].replace('NaiveSpillScheduler','OriginalNaive')
    suffix=source[end:];needle='std::make_unique<NaiveSpillScheduler>()';assert suffix.count(needle)==1
    suffix=suffix.replace(needle,'std::make_unique<OfflineDispatch>(argc>2?argv[2]:"actual_naive",argc>3?argv[3]:"")')
    cpp=BUILD/'offline_dispatch.cpp';cpp.write_text(source[:start]+naive+helpers.read_text(encoding='utf-8')+policy.read_text(encoding='utf-8')+shared.read_text(encoding='utf-8')+WRAPPER+suffix,encoding='utf-8')
    _,elapsed=run(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(cpp),'-o',linux(EXE)],BUILD/'compile.log')
    report={'framework_sha256':sha(framework),'frozen_helpers_sha256':sha(helpers),'actual_r65_policy_sha256':sha(policy),'newpool_header_sha256':sha(shared),'source_sha256':sha(cpp),'binary_sha256':sha(EXE),'compile_seconds':elapsed,'modes':MODES,'factory_only_engine_change':True,'Naive_tie_rule':'original std::sort comparator retained verbatim; no deterministic replacement','D':None,'purpose':'offline trace verification only'}
    (BUILD/'manifest.json').write_text(json.dumps(report,indent=2));return report

def physical_prefix(s):
    tag,t,need=s.callback;c=s.c;n=next_public(s)
    tok=['R67TRACE',tag,t//c.p if tag!='P' else -1,t%c.p if tag!='P' else -1,need,s.used,s.hit,s.miss,s.write+s.read,n[0] or '-',n[1],n[2] if len(n)>2 else 0,n[3] if len(n)>3 else 0]
    for o in range(c.k):
        tok.append(int(s.phase[o]))
        for p in range(c.p):i=o*c.p+p;tok.extend([s.sizes[i],int(s.mem[i])])
    return list(map(str,tok))

def replay_actual(case,stderr):
    lines=['R67TRACE '+line.split('R67TRACE ',1)[1] for line in stderr.splitlines() if 'R67TRACE ' in line]
    s=State(case);index=0
    while s.advance():
        assert index<len(lines),'missing official callback';tok=lines[index].split();prefix=physical_prefix(s)
        assert tok[:len(prefix)]==prefix,(index,'physical/next mismatch',tok[:len(prefix)],prefix)
        pos=len(prefix);count=int(tok[pos]);tail=tok[pos+1:];assert count>=0 and len(tail)==3*count
        actions=[(tail[3*i],int(tail[3*i+1]),int(tail[3*i+2])) for i in range(count)]
        tag,target,need=s.callback;spill=[];loaded=False;seen=set()
        for j,(kind,o,p) in enumerate(actions):
            assert 0<=o<case.k and 0<=p<case.p;flat=o*case.p+p
            assert flat not in seen;seen.add(flat)
            if kind=='S':
                assert not loaded and tag!='P' and flat!=target and s.mem[flat] and s.sizes[flat]>0
                spill.append(flat)
            else:
                assert kind=='L' and tag=='M' and not loaded and j+1==len(actions) and flat==target and not s.mem[flat] and s.phase[o];loaded=True
        assert (tag=='M')==loaded
        assert tag!='P' or not actions
        s.apply(tuple(spill));index+=1
    assert index==len(lines),'unconsumed official callback'
    return s,lines

def costs(s):return {'G':s.g,'grouped_objective':s.g/(s.c.w*s.c.r),'ordered_objective':s.ordered_io+s.c.penalty*s.miss,'ordered_io':s.ordered_io,'grouped_io':s.write/s.c.w+s.read/s.c.r,'write_bytes':s.write,'read_bytes':s.read,'total_io_bytes':s.write+s.read,'hits':s.hit,'misses':s.miss,'D':None}

def _execute(input_path,mode,out_dir,action_file=None):
    assert EXE.exists(),'call prepare() once before measurement window'
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);ip=Path(input_path).resolve();case=Case.read(ip)
    args=['wsl','-d','Ubuntu','--',linux(EXE),linux(ip),mode]
    if action_file is not None:args.append(linux(action_file))
    p,elapsed=run(args,out/'official_trace.log');state,lines=replay_actual(case,p.stderr)
    metrics={k:float(v.strip()) for line in p.stdout.splitlines() if ':' in line for k,v in [line.split(':',1)]}
    assert metrics['Hit_Count']==state.hit and metrics['Miss_Count']==state.miss
    assert abs(metrics['Total_IO_Time']-state.ordered_io)<=.011,'official two-decimal IO mismatch'
    report={'mode':mode,'input':str(ip),'input_sha256':case.input_hash,'cost':costs(state),'callbacks':len(lines),'witness_hash':digest(state.path),'trace_sha256':hashlib.sha256('\n'.join(lines).encode()).hexdigest(),'binary_sha256':sha(EXE),'source_sha256':sha(BUILD/'offline_dispatch.cpp'),'framework_source_sha256':json.loads((BUILD/'manifest.json').read_text())['framework_sha256'],'all_public_physical_next_actions_match':True,'legal_complete_witness':True,'all_callbacks_consumed':True,'official_IO_hits_misses_match':True,'byte_ledger_matches_every_callback':True,'replay_verified':True,'process_seconds':elapsed,'formal_D':None,'official_D_excluded':True}
    (out/'witness.json').write_text(json.dumps(state.path,indent=2));(out/'report.json').write_text(json.dumps(report,indent=2));return dict(report,witness=state.path)

def verify_witness(input_path,witness,out_dir):
    """Replay any legal complete spill/demand-load/empty-periodic witness.

    Returns a report with cost and full witness; no causal-pool restriction.
    Input witness is a list of core.path dictionaries, or a JSON-file Path.
    """
    start=time.perf_counter();out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    if isinstance(witness,(str,Path)):witness=json.loads(Path(witness).read_text())
    c=Case.read(input_path);s=State(c);rows=[];j=0
    while s.advance():
        assert j<len(witness);w=witness[j];tag,t,need=s.callback
        assert (s.raw,s.stage,tag)==(w['raw'],w['stage'],w['kind'])
        spill=tuple(w['spill']);acts=[('S',i//c.p,i%c.p) for i in spill]
        if tag=='M':acts.append(('L',t//c.p,t%c.p))
        values=[tag,t//c.p if tag!='P' else -1,t%c.p if tag!='P' else -1,need,len(acts)]
        for a in acts:values.extend(a)
        rows.append(' '.join(map(str,values)));s.apply(spill);j+=1
    assert j==len(witness),'unconsumed provided witness'
    actionfile=out/'actions.txt';actionfile.write_text('\n'.join(rows)+'\n')
    report=_execute(input_path,'witness',out,actionfile);assert report['witness']==witness and report['cost']['G']==s.g
    report['end_to_end_seconds']=time.perf_counter()-start
    (out/'report.json').write_text(json.dumps({k:v for k,v in report.items() if k!='witness'},indent=2));return report

if __name__=='__main__':print(json.dumps(prepare(),indent=2))
