"""Debug-only score/action and closed-loop parity, never a formal D benchmark."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROUND = OUT.parent
WORKSPACE = ROUND.parents[3]
sys.path[:0] = [str(ROUND), str(WORKSPACE/'tmp/r66_root_nn')]
from core import Case, State, pool, features, next_public, rollout
from tiny_train import score_python_f32


def linux(p):
    return '/mnt/' + str(p)[0].lower() + str(p)[2:].replace('\\', '/')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def command(args, log):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=60)
    log.write_text(r.stdout+r.stderr, encoding='utf-8')
    if r.returncode:
        raise RuntimeError(str(log)+': '+str(r.returncode))
    return r


TRACE = r'''
class NaiveSpillScheduler: public SpillScheduler {
  INNER inner;
  std::vector<Action> step(const SystemState&s,char tag,int o,int p,std::int64_t n){
    std::vector<Action>a;
    if(tag=='O') a=inner.onMemoryOverflow(s,o,p,n);
    else if(tag=='M') a=inner.onPartitionMiss(s,o,p);
    else a=inner.onPeriodicAdjust(s);
    std::cerr<<"R66TRACE "<<tag<<' '<<o<<' '<<p<<' '<<n<<' '
      <<s.memory_used<<' '<<s.hit_count<<' '<<s.miss_count<<' '<<s.total_io_bytes<<' '
      <<(s.next_op.type.empty()?"-":s.next_op.type)<<' '<<s.next_op.op_id<<' '
      <<s.next_op.key<<' '<<s.next_op.tuple_size;
    for(const auto&op:s.operators){std::cerr<<' '<<(op.phase==Phase::PROBE?1:0);
      for(const auto&v:op.partitions)std::cerr<<' '<<v.data_size<<' '<<(v.in_memory?1:0);}
    std::cerr<<' '<<a.size();for(const auto&v:a)std::cerr<<' '
      <<(v.type==Action::SPILL?'S':'L')<<' '<<v.op_id<<' '<<v.partition_id;
    std::cerr<<'\n';return a;
  }
public:
 std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{return step(s,'O',o,p,n);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return step(s,'M',o,p,s.operators[o].partitions[p].data_size);}
 std::vector<Action>onPeriodicAdjust(const SystemState&s)override{return step(s,'P',-1,-1,0);}
};
'''


def expected(case, mode, model, witness_override=None):
    s = State(case)
    witness = witness_override if witness_override is not None else (rollout(case, mode=mode).path if mode != 'nn' else None)
    lines = []
    selected = []
    while s.advance():
        tag,t,need = s.callback
        if witness is not None:
            row=witness[len(lines)]
            assert (s.raw,s.stage,tag)==(row['raw'],row['stage'],row['kind'])
            a = tuple(row['spill'])
        else:
            a = min(pool(s), key=lambda a:(score_python_f32(model,features(s,a)),
                    len(a),sum(s.sizes[i] for i in a),a))
        op = case.ops[s.raw+1] if s.raw+1<len(case.ops) else ('',-1)
        # Final operation fields use the official default Operation initialization.
        next_values = [op[0] or '-',op[1],op[2] if len(op)>2 else 0,
                       op[3] if len(op)>3 else 0]
        tok = ['R66TRACE',tag,t//case.p if tag!='P' else -1,
               t%case.p if tag!='P' else -1,need,s.used,s.hit,s.miss,s.write+s.read]+next_values
        for o in range(case.k):
            tok.append(int(s.phase[o]))
            for p in range(case.p):
                i=o*case.p+p;tok.extend([s.sizes[i],int(s.mem[i])])
        acts = [('S',i//case.p,i%case.p) for i in a]
        if tag=='M':acts.append(('L',t//case.p,t%case.p))
        tok.append(len(acts))
        for action in acts:tok.extend(action)
        lines.append(' '.join(map(str,tok)))
        selected.append(list(a));s.apply(a)
    return s,lines,selected


def official_trace_witness(case,lines):
    """Replay original Naive actions; its std::sort leaves equal-size ties unspecified."""
    state=State(case);witness=[]
    offset=13+case.k*(1+2*case.p)
    for line in lines:
        assert state.advance()
        token=line.split();n=int(token[offset]);tail=token[offset+1:]
        assert len(tail)==n*3
        actions=[(tail[i],int(tail[i+1]),int(tail[i+2])) for i in range(0,len(tail),3)]
        loads=[a for a in actions if a[0]=='L']
        tag,t,_=state.callback
        assert loads==([('L',t//case.p,t%case.p)] if tag=='M' else [])
        assert not loads or actions[-1]==loads[0]
        assert all(a[0] in ('S','L') for a in actions)
        spill=[o*case.p+p for typ,o,p in actions if typ=='S']
        witness.append(dict(raw=state.raw,stage=state.stage,kind=tag,spill=spill))
        state.apply(spill)
    assert not state.advance()
    return witness


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--model-dir',default=str(OUT))
    ap.add_argument('--train-ids',default='exact_04')
    ap.add_argument('--out-name',default='integration_v2')
    args=ap.parse_args()
    model_out=Path(args.model_dir).resolve()
    target=model_out/args.out_name;target.mkdir(exist_ok=True)
    model=json.loads((model_out/'model.json').read_text())
    framework=ROUND.parent/'round49_latency_baseline/reference_compilable.cpp'
    raw=framework.read_text(encoding='utf-8')
    start=raw.index('class NaiveSpillScheduler');end=raw.index('class HashJoinEngine')
    prefix=raw[:start]+'\n#include <iomanip>\n'
    shared=(ROUND/'shared_pool.hpp').read_text()
    header=(model_out/'tiny_score.hpp').read_text()
    scorer='struct NNScore {float operator()(const std::array<float,16>&x)const{return r66_tiny_score(x.data());}};\n'
    # Standalone score parity includes all one hundred real training candidates.
    vectors=json.loads((model_out/'score_vectors.json').read_text())
    vals='\n'.join('{' + ','.join(format(float(x),'.17g')+'f' if ('.' in format(float(x),'.17g') or 'e' in format(float(x),'.17g')) else format(float(x),'.17g')+'.0f' for x in v['x']) + '},' for v in vectors)
    probe=target/'score_probe.cpp'
    probe.write_text(header+'\n#include <iostream>\n#include <iomanip>\nint main(){float xs[][16]={'+vals+'};for(auto&x:xs)std::cout<<std::setprecision(17)<<r66_tiny_score(x)<<"\\n";}\n')
    command(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(probe),'-o',linux(target/'score_probe')],target/'score_compile.log')
    score_run=command(['wsl','-d','Ubuntu','--',linux(target/'score_probe')],target/'scores.log')
    cpp_scores=list(map(float,score_run.stdout.split()))
    assert len(cpp_scores)==len(vectors)
    max_error=max(abs(v['score']-v2) for v,v2 in zip(vectors,cpp_scores))
    assert max_error==0, max_error
    for mode,inner in [('nn','R66Scheduler<NNScore>'),('base','R66Scheduler<R66BaseScore>'),('naive','OriginalNaive')]:
        naive=raw[start:end].replace('NaiveSpillScheduler','OriginalNaive') if mode=='naive' else ''
        body=prefix+shared+header+scorer+naive+TRACE.replace('INNER',inner)+raw[end:]
        cpp=target/(mode+'.cpp');cpp.write_text(body,encoding='utf-8')
        command(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(cpp),'-o',linux(target/mode)],target/(mode+'_compile.log'))
    # Export the uninstrumented production candidate separately. Do not time the trace harness.
    production=prefix+shared+header+scorer+'using NaiveSpillScheduler=R66Scheduler<NNScore>;\n'+raw[end:]
    (target/'nn_production_engine.cpp').write_text(production,encoding='utf-8')
    pilot=json.loads((ROUND/'data/train_manifest.json').read_text())
    def cases_of(obj):return obj['cases'] if isinstance(obj,dict) else obj
    train_ids=args.train_ids.split(',')
    train_cases=[dict(next(c for c in cases_of(pilot) if c['selection_id']==name),case_id='train_'+name)
                 for name in train_ids]
    holdouts=cases_of(json.loads((ROUND/'data/holdout_manifest.json').read_text()))
    cases=train_cases+holdouts
    results=[]
    for entry in cases:
        ip=Path(entry['input']);case=Case.read(ip);paths={}
        for mode in ('naive','base','nn'):
            name=entry['case_id']+'_'+mode
            run=command(['wsl','-d','Ubuntu','--',linux(target/mode),linux(ip)],target/(name+'.log'))
            # WSL can append its UTF16 startup warning and NUL to the first trace line.
            actual=['R66TRACE '+line.split('R66TRACE ',1)[1] for line in run.stderr.splitlines() if 'R66TRACE ' in line]
            witness=official_trace_witness(case,actual) if mode=='naive' else None
            state,expected_lines,paths[mode]=expected(case,mode,model,witness_override=witness)
            if actual!=expected_lines:
                for i,(a,b) in enumerate(zip(actual,expected_lines)):
                    if a!=b:raise AssertionError((name,i,'cpp',a,'python',b))
                raise AssertionError((name,len(actual),len(expected_lines)))
            metrics={k:float(v.strip()) for line in run.stdout.splitlines() if ':' in line for k,v in [line.split(':',1)]}
            assert metrics['Hit_Count']==state.hit and metrics['Miss_Count']==state.miss
            assert abs(metrics['Total_IO_Time']-state.ordered_io)<.011
            results.append(dict(case_id=entry['case_id'],split='train' if entry['case_id'].startswith('train_') else 'holdout_v1',
                                mode=mode,callbacks=len(actual),hits=state.hit,misses=state.miss,
                                write_bytes=state.write,read_bytes=state.read,
                                IO=state.ordered_io,cost_without_D=state.ordered_io+case.penalty*state.miss,
                                input_sha256=sha(ip),trace_sha256=hashlib.sha256('\n'.join(actual).encode()).hexdigest(),
                                all_callback_states_and_actions_match=True,formal_D=None,
                                replay_scope='official_action_driven_physical_replay' if mode=='naive' else 'independent_python_policy_and_physical_replay'))
        results[-1]['same_complete_actions_as_base']=paths['nn']==paths['base']
    report=dict(schema_version=1,purpose='debug_closed_loop_and_cpp_parity_not_formal_timing',
                score_vectors=len(vectors),cpp_vs_python_f32_max_abs_error=max_error,
                model_sha256=sha(model_out/'model.json'),framework_sha256=sha(framework),
                core_sha256=sha(ROUND/'core.py'),shared_pool_sha256=sha(ROUND/'shared_pool.hpp'),results=results,
                caveats=['Three of four holdout_v1 traces fit total build bytes within memory.',
                         'Pilot train teacher has no advantage over best incumbent.',
                         'Original official Naive equal-size ties differ from the deterministic-ID largest-first search seed.',
                         'Debug instrumentation invalidates formal decision-time comparisons.'])
    (target/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
