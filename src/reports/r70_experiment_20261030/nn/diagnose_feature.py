import json,struct
import pipeline as p
import verify_cpp as v

source=(v.OUT/'nn.cpp').read_text(encoding='utf8')
needle=' std::cerr<<"R70DETAIL "'
extra=r''' static int detail_seq=0;if(detail_seq++==22){for(std::size_t j=0;j<xs.size();++j){std::cerr<<std::setprecision(17)<<"R70C "<<j<<' '<<ps[j].cost<<' '<<ps[j].bytes<<' '<<(ps[j].cost/ps[j].bytes)<<'\n';for(int i=0;i<32;++i){std::uint32_t b;std::memcpy(&b,&xs[j][i],4);std::cerr<<"R70V "<<j<<' '<<i<<' '<<b<<'\n';}float z=r70_score(xs[j].data());std::uint32_t b;std::memcpy(&b,&z,4);std::cerr<<"R70V "<<j<<" 32 "<<b<<'\n';}}
'''
assert needle in source
target=v.OUT/'nn_feature_debug.cpp';target.write_text('#include <iomanip>\n'+source.replace(needle,extra+needle),encoding='utf8')
v.run(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',v.linux(target),'-o',v.linux(v.OUT/'nn_feature_debug')],'feature_debug_compile')
meta=p.inventory()['dev_skewed_06'];_,stderr=v.run(['wsl','-d','Ubuntu','--',v.linux(v.OUT/'nn_feature_debug'),v.linux(meta['path'])],'feature_debug_run')
actual={}
for line in stderr.splitlines():
    if line.startswith('R70V '):_,j,i,b=line.split();actual[int(j),int(i)]=int(b)
c=p.core.Case.read(meta['path']);s=p.core.State(c);model=json.loads((v.MODEL/'model.json').read_text());index=0;diff=[]
while s.advance():
    if s.callback[0]=='P':a=()
    else:
        plans=p.core.pool(s);xs=p.features(s,plans);scores=[p.score_python(model,x) for x in xs]
        if len(plans)>1:
            if index==22:
                for j,(a,x,z) in enumerate(zip(plans,xs,scores)):
                    for i,value in enumerate(x+[z]):
                        b=struct.unpack('<I',struct.pack('<f',value))[0]
                        if actual[j,i]!=b:diff.append(dict(plan=j,spill=a,dimension=i,name=p.FEATURE_NAMES[i] if i<32 else 'score',python=value,python_bits=b,cpp_bits=actual[j,i],cpp=struct.unpack('<f',struct.pack('<I',actual[j,i]))[0]))
                break
            index+=1
        a=plans[min(range(len(plans)),key=lambda j:(scores[j],p.tie(s,plans[j])))]
    s.apply(a)
raw_costs=[]
for a in plans:
    terms=[p.core.victim_cost(s,i) for i in a];sequential=0.
    for value in terms:sequential+=value
    raw_costs.append(dict(spill=a,terms=terms,builtin_sum=sum(terms),sequential_sum=sequential,bytes=sum(s.sizes[i] for i in a),builtin_density=sum(terms)/sum(s.sizes[i] for i in a),sequential_density=sequential/sum(s.sizes[i] for i in a)))
report=dict(raw=s.raw,callback=s.callback,plans=plans,differences=diff,python_costs=raw_costs,cpp_cost_lines=[line for line in stderr.splitlines() if line.startswith('R70C ')])
p.dump(v.OUT/'feature_debug_report.json',report);print(json.dumps(report),flush=True)
