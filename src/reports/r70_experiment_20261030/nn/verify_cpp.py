"""Non-timing C++14 score, feature/history and full closed-loop replay checks."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import pipeline as p

OUT=p.ROOT/'model_v2'/'verification'
MODEL=p.ROOT/'model_v2'
FRAME=p.WS/'hashjoin_lab/reports/collaboration_20261020/round49_latency_baseline/reference_compilable.cpp'

def linux(path):
    s=str(Path(path).resolve());return '/mnt/'+s[0].lower()+s[2:].replace('\\','/')

def run(args,name,timeout=60):
    with (OUT/(name+'.stdout.log')).open('wb') as out,(OUT/(name+'.stderr.log')).open('wb') as err:
        r=subprocess.run(args,stdout=out,stderr=err,timeout=timeout)
    if r.returncode:raise RuntimeError(f'{name}: exit {r.returncode}; see stderr log')
    return (OUT/(name+'.stdout.log')).read_text(errors='replace'),(OUT/(name+'.stderr.log')).read_text(errors='replace')

DETAIL=r'''
#include <cstring>
inline void r70detail(const R66History&h,const std::vector<r66::Plan>&ps,const std::vector<std::array<float,32>>&xs){
 std::uint64_t xh=14695981039346656037ULL,hh=xh;
 auto mix=[](std::uint64_t&z,std::uint64_t v){z^=v;z*=1099511628211ULL;};
 mix(xh,ps.size());for(std::size_t j=0;j<ps.size();++j){mix(xh,ps[j].spill.size());for(int i:ps[j].spill)mix(xh,i);for(float f:xs[j]){std::uint32_t b;std::memcpy(&b,&f,4);mix(xh,b);}float z=r70_score(xs[j].data());std::uint32_t b;std::memcpy(&b,&z,4);mix(xh,b);}
 mix(hh,h.clock_);for(std::size_t i=0;i<h.ops_*h.parts_;++i){const auto&v=h.slots_[i];mix(hh,v.size);mix(hh,v.h);mix(hh,v.anchor);mix(hh,v.ghost);mix(hh,v.reward);}
 std::cerr<<"R70DETAIL "<<xh<<' '<<hh<<'\n';
}
'''

def hashed(values):
    h=14695981039346656037
    for v in values:h=((h^(int(v)&((1<<64)-1)))*1099511628211)&((1<<64)-1)
    return h

def detail(s,plans,xs,scores):
    values=[len(plans)]
    for a,x,z in zip(plans,xs,scores):
        values.extend([len(a),*a]);values.extend(struct.unpack('<32I',struct.pack('<32f',*x)))
        values.append(struct.unpack('<I',struct.pack('<f',z))[0])
    history=[s.h.clock]+[v for slot in s.h.slots for v in slot]
    return f'R70DETAIL {hashed(values)} {hashed(history)}'

def expected(case,mode,model):
    s=p.core.State(case);lines=[];details=[];stats=dict(multi_spill=0,rewarded_history=0,score_ties=0,size_reset_slots=0)
    while s.advance():
        tag,t,need=s.callback
        if tag=='P':a=()
        else:
            plans=p.core.pool(s)
            if mode in ('nn','heuristic') and len(plans)>1:
                xs=p.features(s,plans);scores=[p.score_python(model,x) if mode=='nn' else x[13] for x in xs]
                details.append(detail(s,plans,xs,scores))
                stats['score_ties']+=len(set(scores))<len(scores)
                stats['rewarded_history']+=any(slot[4]>=0 for slot in s.h.slots)
                stats['size_reset_slots']+=sum(slot[0]!=s.sizes[i] for i,slot in enumerate(s.h.slots))
                a=min(range(len(plans)),key=lambda j:(scores[j],p.tie(s,plans[j])))
                a=plans[a]
            else:a=min(plans,key=lambda a:(p.core.features(s,a)[13],p.tie(s,a)))
        stats['multi_spill']+=len(a)>1
        op=p.core.next_public(s);values=[op[0] or '-',op[1],op[2] if len(op)>2 else 0,op[3] if len(op)>3 else 0]
        tok=['R66TRACE',tag,t//case.p if tag!='P' else -1,t%case.p if tag!='P' else -1,need,s.used,s.hit,s.miss,s.write+s.read]+values
        for o in range(case.k):
            tok.append(int(s.phase[o]))
            for q in range(case.p):i=o*case.p+q;tok.extend([s.sizes[i],int(s.mem[i])])
        actions=[('S',i//case.p,i%case.p) for i in a]
        if tag=='M':actions.append(('L',t//case.p,t%case.p))
        tok.append(len(actions))
        for action in actions:tok.extend(action)
        lines.append(' '.join(map(str,tok)));s.apply(a)
    return s,lines,details,stats

def equal_lines(actual,expected,name):
    if actual!=expected:
        for i,(a,b) in enumerate(zip(actual,expected)):
            if a!=b:raise AssertionError((name,i,a,b))
        raise AssertionError((name,'length',len(actual),len(expected)))

def main():
    OUT.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    raw=FRAME.read_text(encoding='utf8');first=raw.index('class NaiveSpillScheduler');last=raw.index('class HashJoinEngine')
    shared=(MODEL/'shared_pool.hpp').read_text();scorer=(MODEL/'tiny_score.hpp').read_text()
    policy=(MODEL/'policy.hpp').read_text().replace('#include "shared_pool.hpp"','').replace('#include "tiny_score.hpp"','')
    standalone=shared+'\n'+scorer+'\n'+policy
    (MODEL/'MySpillScheduler.policy.hpp').write_text(standalone)
    baseline=shared+'\nclass MySpillScheduler:public R66Scheduler<R66BaseScore>{};\n'
    (MODEL/'base13.policy.hpp').write_text(baseline)
    heuristic=shared+'\ninline float r70_score(const float x[32]){return x[13];}\n'+policy
    (MODEL/'Heuristic.policy.hpp').write_text(heuristic)
    cached=json.loads((OUT/'report.json').read_text()) if (OUT/'report.json').exists() else None
    if cached:assert cached['model_sha256']==p.sha(MODEL/'model.json') and cached['policy_sha256']==p.sha(MODEL/'MySpillScheduler.policy.hpp')
    # Reuse the frozen full physical/public callback trace format, not its model.
    old=p.R66/'learning_pilot/integrate_pilot.py'
    sys.path.insert(0,str(p.WS/'tmp/r66_root_nn'))
    spec=importlib.util.spec_from_file_location('_r70_old_trace',old);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    vectors=json.loads((MODEL/'score_vectors.json').read_text());model=json.loads((MODEL/'model.json').read_text())
    literal=lambda v:format(float(v),'.17g')+('f' if '.' in format(float(v),'.17g') or 'e' in format(float(v),'.17g') else '.0f')
    array=','.join('{'+','.join(map(literal,v['x']))+'}' for v in vectors)
    cpp=OUT/'score_probe.cpp';cpp.write_text(scorer+'\n#include <iostream>\n#include <iomanip>\nint main(){float x[][32]={'+array+'};for(auto&a:x)std::cout<<std::setprecision(17)<<r70_score(a)<<"\\n";}')
    if cached:error=cached['max_score_error']
    else:
        run(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(cpp),'-o',linux(OUT/'score_probe')],'score_compile')
        scores,_=run(['wsl','-d','Ubuntu','--',linux(OUT/'score_probe')],'score_run')
        scores=list(map(float,scores.split()));assert len(scores)==len(vectors)
        error=max(abs(a-v['score']) for a,v in zip(scores,vectors));assert error==0,error
    for mode in ('nn','heuristic'):
        text=standalone if mode=='nn' else heuristic
        text=text.replace('class MySpillScheduler:public SpillScheduler',DETAIL+'\nclass MySpillScheduler:public SpillScheduler')
        needle='auto xs=r70::features(s,history_,plans,r66::flat(s,o,pid),need);'
        assert needle in text;text=text.replace(needle,needle+'r70detail(history_,plans,xs);')
        trace=mod.TRACE.replace('INNER','MySpillScheduler')
        cpp=OUT/(mode+'.cpp');contents=raw[:first]+text+'\n'+trace+raw[last:]
        unchanged=cpp.exists() and cpp.read_text(encoding='utf8')==contents and (OUT/mode).exists()
        if not unchanged:
            cpp.write_text(contents,encoding='utf8')
            run(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(cpp),'-o',linux(OUT/mode)],mode+'_compile')
    cases=p.inventory();selected=[k for k,v in cases.items() if v['split']=='dev'];results=cached['results'] if cached else []
    completed={(r['case_id'],r['mode']) for r in results}
    for name in selected:
        c=p.core.Case.read(cases[name]['path'])
        for mode in ('nn','heuristic'):
            if (name,mode) in completed:continue
            expected_state,lines,details,coverage=expected(c,mode,model)
            stdout,stderr=run(['wsl','-d','Ubuntu','--',linux(OUT/mode),linux(cases[name]['path'])],name+'_'+mode)
            actual=['R66TRACE '+line.split('R66TRACE ',1)[1] for line in stderr.splitlines() if 'R66TRACE ' in line]
            actual_details=['R70DETAIL '+line.split('R70DETAIL ',1)[1] for line in stderr.splitlines() if 'R70DETAIL ' in line]
            equal_lines(actual,lines,name+' '+mode+' physical/actions')
            equal_lines(actual_details,details,name+' '+mode+' features/history/scores')
            metrics={k:float(v.strip()) for line in stdout.splitlines() if ':' in line for k,v in [line.split(':',1)]}
            s=expected_state;assert metrics['Hit_Count']==s.hit and metrics['Miss_Count']==s.miss
            assert abs(metrics['Total_IO_Time']-s.ordered_io)<=.011
            item=dict(case_id=name,mode=mode,callbacks=len(lines),full_physical_next_actions_match=True,
                      feature_history_score_callback_hashes_match=True,detail_callbacks=len(details),coverage=coverage,
                      input_sha256=c.input_hash,write_bytes=s.write,read_bytes=s.read,hits=s.hit,misses=s.miss,
                      G=s.g,cost_without_D=s.g/(c.w*c.r),formal_D=None)
            results.append(item);print(json.dumps(item),flush=True)
    report=dict(passed=True,status='non_D_CPP14_O2_full_replay_validated',score_vectors=len(vectors),max_score_error=error,
                results=results,model_sha256=p.sha(MODEL/'model.json'),policy_sha256=p.sha(MODEL/'MySpillScheduler.policy.hpp'),
                base13_policy_sha256=p.sha(MODEL/'base13.policy.hpp'),framework_sha256=p.sha(FRAME),
                heuristic_policy_sha256=p.sha(MODEL/'Heuristic.policy.hpp'),dev_case_ids=selected,
                seconds=time.perf_counter()-start,holdout_labels_or_solver_runs=False,
                holdout_identity_hashes_checked_for_split_leakage=True,formal_D=None)
    p.dump(OUT/'report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)

if __name__=='__main__':main()
