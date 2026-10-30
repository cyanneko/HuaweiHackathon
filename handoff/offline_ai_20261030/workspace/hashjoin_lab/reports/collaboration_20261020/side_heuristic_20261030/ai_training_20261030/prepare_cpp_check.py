"""Prepare selected model migration only after full Python closed-loop evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import sys
from train import HERE,WS,old,dump,sha
from export_cpp import export,score_sequential,literal


def hashed(values):
    h=14695981039346656037
    for value in values:h=((h^(int(value)&((1<<64)-1)))*1099511628211)&((1<<64)-1)
    return h


DETAIL=r'''
#include <cstring>
inline void handler_detail(const R66History&h,const std::vector<r66::Plan>&ps,const std::vector<std::array<float,32>>&xs){
 std::uint64_t xh=14695981039346656037ULL,hh=xh;
 auto mix=[](std::uint64_t&z,std::uint64_t v){z^=v;z*=1099511628211ULL;};
 mix(xh,ps.size());for(std::size_t j=0;j<ps.size();++j){mix(xh,ps[j].spill.size());for(int i:ps[j].spill)mix(xh,i);for(float f:xs[j]){std::uint32_t b;std::memcpy(&b,&f,4);mix(xh,b);}}
 mix(hh,h.clock_);for(std::size_t i=0;i<h.ops_*h.parts_;++i){const auto&v=h.slots_[i];mix(hh,v.size);mix(hh,v.h);mix(hh,v.anchor);mix(hh,v.ghost);mix(hh,v.reward);}
 std::cerr<<"HANDLERDETAIL "<<xh<<' '<<hh<<'\n';
}
'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();out=args.out
    report=json.loads((HERE/'closed_loop_v1/report.json').read_text());assert report['status']=='PYTHON_COMPLETE_DEV_CLOSED_LOOP'
    model_path=HERE/'gpu_fixed_v1'/args.name/'model.json';model=json.loads(model_path.read_text())
    source=export(model_path,out,WS)
    trace_path=WS/'hashjoin_lab/reports/collaboration_20261020/round66_offline_oracle/learning_pilot/integrate_pilot.py'
    spec=importlib.util.spec_from_file_location('_trace_contract',trace_path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    frame=WS/'hashjoin_lab/reports/collaboration_20261020/round49_latency_baseline/reference_compilable.cpp'
    raw=frame.read_text(encoding='utf8');first=raw.index('class NaiveSpillScheduler');last=raw.index('class HashJoinEngine')
    instrumented=source.replace('class MySpillScheduler:public SpillScheduler',DETAIL+'\nclass MySpillScheduler:public SpillScheduler')
    needle='auto xs=r70::features(s,history_,plans,r66::flat(s,o,pid),need);';assert needle in instrumented
    instrumented=instrumented.replace(needle,needle+'handler_detail(history_,plans,xs);')
    (out/'diagnostic.cpp').write_text(raw[:first]+instrumented+'\n'+mod.TRACE.replace('INNER','MySpillScheduler')+raw[last:],encoding='utf8')
    suffix=raw[last:];assert suffix.count('std::make_unique<NaiveSpillScheduler>()')==1
    (out/'production.cpp').write_text(raw[:first]+source+'\n'+suffix.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<MySpillScheduler>()'),encoding='utf8')
    # Keep the actual original Naive framework for scoring; reference Python tie is not sufficient.
    (out/'official_naive.cpp').write_text(raw,encoding='utf8')
    manifest=json.loads((HERE/'closed_loop_v1/manifest.json').read_text());cases=[];vectors=[]
    for meta in manifest['cases']:
        c=old.core.Case.read(meta['path']);assert c.input_hash==meta['sha256']
        witness_path=HERE/'closed_loop_v1'/(meta['id']+'_'+args.name+'.witness.json')
        witness=json.loads(witness_path.read_text());s,lines,_=mod.expected(c,'nn',None,witness_override=witness)
        (out/(meta['id']+'.expected_trace')).write_text('\n'.join(lines)+'\n',encoding='utf8')
        state=old.core.State(c);details=[];i=0
        while state.advance():
            plans=old.core.pool(state)
            if len(plans)>1:
                xs=old.features(state,plans);values=[len(plans)]
                for action,x in zip(plans,xs):
                    values.extend([len(action),*action]);values.extend(struct.unpack('<32I',struct.pack('<32f',*x)))
                    if len(vectors)<128:vectors.append({'x':x,'score':score_sequential(model,x)})
                history=[state.h.clock]+[v for slot in state.h.slots for v in slot]
                details.append('HANDLERDETAIL %d %d'%(hashed(values),hashed(history)))
            w=witness[i];assert (w['raw'],w['stage'],w['kind'])==(state.raw,state.stage,state.callback[0])
            state.apply(tuple(w['spill']));i+=1
        assert i==len(witness) and state.g==s.g
        (out/(meta['id']+'.expected_detail')).write_text('\n'.join(details)+'\n',encoding='utf8')
        cases.append({'id':meta['id'],'input_path':meta['path'],'input_sha256':c.input_hash,
                      'witness_sha256':sha(witness_path),'G':s.g,'write_bytes':s.write,'read_bytes':s.read,
                      'hits':s.hit,'misses':s.miss,'io_us':s.write/c.w+s.read/c.r,
                      'cost_without_D':s.g/(c.w*c.r),'penalty':c.penalty,'callbacks':len(lines),'detail_callbacks':len(details)})
    dump(out/'score_vectors.json',vectors)
    array=','.join('{'+','.join(map(literal,v['x']))+'}' for v in vectors)
    (out/'score_probe.cpp').write_text((out/'score.hpp').read_text()+'\n#include <iostream>\n#include <iomanip>\nint main(){float xs[][32]={'+array+'};for(auto&x:xs)std::cout<<std::setprecision(17)<<r70_score(x)<<"\\n";}',encoding='utf8')
    dump(out/'manifest.json',{'model_name':args.name,'model_sha256':sha(model_path),'source_sha256':sha(out/'MySpillScheduler.cpp'),
         'frame_sha256':sha(frame),'cases':cases,'formal_D':None,'expected_score_error':0,
         'source_only_stdlib':True,'python_closed_loop_sha256':sha(HERE/'closed_loop_v1/report.json')})
    print(json.dumps({'prepared':str(out),'cases':len(cases),'vectors':len(vectors)}))


if __name__=='__main__':main()
