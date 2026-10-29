"""Export cost-sensitive policy trees; preserve the public engine and timers."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parent;DESIGN=ROOT.parent
def scalar(v):
    s=format(float(v),'.9g');return s+('' if '.' in s or 'e' in s else '.0')+'f'
def tree_code(node,feature,category=None):
    if 'leaf' in node:return 'return '+str(node['leaf'])+';'
    if 'category_mask' in node:
        assert node['feature']==30 and category is not None and 0<=node['category_mask']<256
        condition='(('+str(node['category_mask'])+'u>>unsigned('+category(30)+'))&1u)'
        return 'if('+condition+'){'+tree_code(node['left'],feature,category)+'}else{'+tree_code(node['right'],feature,category)+'}'
    f=node['feature'];t=scalar(node['threshold'])
    return 'if('+feature(f)+'<='+t+'){'+tree_code(node['left'],feature,category)+'}else{'+tree_code(node['right'],feature,category)+'}'
def cheap(i):
    mem='double(s.memory_limit)';free='double(s.memory_limit-s.memory_used)';sz='double(bytes)'
    nn='(s.next_op.type=="PROBE"||s.next_op.type=="INSERT")'
    no='s.next_op.op_id';np='int(s.next_op.key%s.num_partitions)';nx=f's.operators[{no}].partitions[{np}]'
    expr={0:f'float(double(s.memory_used)/{mem})',1:f'float({sz}/{mem})',2:f'float(std::max(0.0,{sz}-{free})/{mem})',3:f'float({free}/{mem})',4:'float(s.operators.size()/8.0)',5:'float(s.num_partitions/64.0)',6:'float(build)',7:'float(s.operators[o].phase==Phase::PROBE)',17:'float(s.next_op.type=="PROBE")',18:'float(s.next_op.type=="INSERT")',
      19:f'({nn}?float({nx}.data_size/{mem}):0.0f)',20:f'({nn}?float({nx}.in_memory):0.0f)',21:f'({nn}?float({no}==o):0.0f)',22:f'({nn}?float((build?s.operators[o].partitions[p].data_size+{sz}:{sz})+{nx}.data_size<={mem}):0.0f)',
      23:'float(s.write_bandwidth/10000.0)',24:'float(s.read_bandwidth/10000.0)',25:'float(double(s.miss_count)/double(std::max(uint64_t(1),tick(s))))',26:'float(bounded(double(uint64_t(s.miss_count)+compensated_misses_-epoch_miss_)/double(std::max(uint64_t(1),tick(s)-epoch_))))',27:'targetHeatFeature(s,o,p)',29:'float(bounded(double(returns_-return_base_)/double(std::max(uint64_t(1),tick(s)-epoch_))))',30:'float(selected_expert_/7.0)'}
    return expr[i]
def forced_cover(source):
    marker='        // Exact minimum immediate write bytes for <=10 eligible candidates.'
    code='''        // Every resident x with size(x)>M-locked is infeasible beside the
        // partitions which this request must retain. Such x must be spilled.
        // If forced victims cover the deficit, this set attains the unavoidable
        // immediate-write lower bound. No future-Score optimality is claimed.
        int64_t locked=build?s.operators[to].partitions[tp].data_size+need:need;
        if(po>=0&&!(po==to&&pp==tp)&&s.operators[po].partitions[pp].in_memory)
            locked+=s.operators[po].partitions[pp].data_size;
        if(locked<=s.memory_limit){
            int64_t forced_bytes=0;
            for(int i=0;i<n;++i)if(c[i].bytes>s.memory_limit-locked)forced_bytes+=c[i].bytes;
            if(forced_bytes>=deficit){
                std::vector<Action> a;a.reserve(n+2);
                for(int i=0;i<n;++i)if(c[i].bytes>s.memory_limit-locked)a.emplace_back(Action::SPILL,c[i].o,c[i].p);
                return a;
            }
        }
'''
    assert marker in source;return source.replace(marker,code+marker,1)
def shared_scratch(source):
    marker='    struct Ghost {'
    assert marker in source
    source=source.replace(marker,'    std::array<Victim,512> scratch_candidates_{};\n    std::array<int64_t,1024> scratch_sums_{};\n'+marker,1)
    assert 'std::array<Victim,512> c;' in source
    source=source.replace('std::array<Victim,512> c;','auto& c=scratch_candidates_;',1)
    assert 'std::array<int64_t,1024> sums;' in source
    return source.replace('std::array<int64_t,1024> sums;','auto& sums=scratch_sums_;',1)
def export(path):
    obj=json.loads(path.read_text('utf8'))
    if obj.get('kind')=='bounded_reference':
        target=ROOT/(path.stem+'.cpp');source=forced_cover((DESIGN/'MySpillScheduler_neural.cpp').read_text('utf8'));target.write_bytes(source.encode('utf8'))
        return dict(name=path.stem,source=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),used_features=list(range(32)),lazy_features=False)
    nodes=obj['tree']
    def expand(i):
        n=nodes[i]
        if 'expert' in n:return dict(leaf=n['expert'])
        if 'category_mask' in n:
            assert n['feature']==30 and n['comparison']=='in_mask'
            return dict(feature=30,category_mask=n['category_mask'],left=expand(n['left']),right=expand(n['right']))
        return dict(feature=n['feature'],threshold=n['threshold'],left=expand(n['left']),right=expand(n['right']))
    node=expand(0);used=obj['used_features'];is_cheap=all(i in {0,1,2,3,4,5,6,7,17,18,19,20,21,22,23,24,25,26,27,29,30} for i in used)
    if is_cheap:body=tree_code(node,cheap,lambda i:'selected_expert_')
    else:
        body='std::array<float,32> x;bool ready=false;auto get=[&](int i){if(!ready){x=features(s,o,p,build,bytes);ready=true;}return x[i];};'
        body+=tree_code(node,lambda i:cheap(i) if i in {0,1,2,3,4,5,6,7,17,18,19,20,21,22,23,24,25,26,27,29,30} else f'get({i})',lambda i:'selected_expert_')
    code='int route(const SystemState& s,int o,int p,bool build,int64_t bytes) const {'+body+'}\n'
    if 27 in used:
        code='float targetHeatFeature(const SystemState& s,int o,int p) const {int id=o*s.num_partitions+p;uint64_t now=tick(s),age=now>last_[id]?now-last_[id]:0;double h=double(heat_[id])/(1.0+double(age)/64.0);return float(h/(1+h));}\n'+code
    code+='#ifdef PORTFOLIO_AUDIT\nint routeReference(const std::array<float,32>& x) const {'+tree_code(node,lambda i:f'x[{i}]',lambda i:'int(x[30]*7.0f+0.5f)')+'}\n#endif\n'
    template=(DESIGN/'neural_selector/Scheduler.template').read_text('utf8')
    old='auto f=features(s,o,p,build,bytes);selected_expert_=network(f);++inferences_;'
    # Reference must see the previous expert, just as the model did.
    new='int next_expert=route(s,o,p,build,bytes);\n#ifdef PORTFOLIO_AUDIT\nif(next_expert!=routeReference(features(s,o,p,build,bytes)))throw std::runtime_error("route feature mismatch");\n#endif\nselected_expert_=next_expert;++inferences_;'
    assert old in template
    source=template.replace('@@NETWORK@@',code).replace(old,new)
    if obj.get('forced_cover'):source=forced_cover(source)
    if obj.get('shared_scratch'):source=shared_scratch(source)
    if 'periodic_admission_shift' in obj:
        from admission_patch import patch
        source=patch(source,obj['periodic_admission_shift'])
    target=ROOT/(path.stem+'.cpp');target.write_bytes(source.encode('utf8'))
    return dict(name=path.stem,source=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),used_features=used,lazy_features=is_cheap)
def build():
    variants=[export(p) for p in sorted(ROOT.glob('tree_*.json')) if 'training_summary' not in p.stem and not p.stem.endswith('_manifest')]
    previous=json.loads((ROOT/'variants.json').read_text('utf8')) if (ROOT/'variants.json').exists() else []
    stable={v['name']:v['id'] for v in previous};next_id=max([2]+list(stable.values()))+1
    if any(100<=i<108 for i in stable.values()):raise RuntimeError('Tree IDs collide with reserved fixed-expert modes')
    for v in variants:
        if v['name'] not in stable:
            while 100<=next_id<108:next_id+=1
            stable[v['name']]=next_id;next_id+=1
        v['id']=stable[v['name']]
    header='#include <stdexcept>\n#define MySpillScheduler NeuralReference\n#include "../MySpillScheduler_neural.cpp"\n#undef MySpillScheduler\n#define MySpillScheduler PreviousReference\n#include "../MySpillScheduler_final.cpp"\n#undef MySpillScheduler\n'
    for i,v in enumerate(variants):
        header+=f'#define MySpillScheduler Tree_{i}\n#include "{v["source"]}"\n#undef MySpillScheduler\n'
    header+='static std::unique_ptr<SpillScheduler> makeScheduler(int mode){switch(mode){case 0:return std::make_unique<NeuralReference>();case 1:return std::make_unique<PreviousReference>();case 2:return std::make_unique<NaiveSpillScheduler>();'
    for i,v in enumerate(variants):header+=f'case {v["id"]}:return std::make_unique<Tree_{i}>();'
    header+='default:if(mode>=100&&mode<108)return std::make_unique<NeuralReference>(mode-100);throw std::runtime_error("mode");}}\n'
    ref=(DESIGN/'holistic_20261026/reference_current.cpp').read_text('utf8');marker='/* ===== 执行引擎 ===== */';ctor='std::make_unique<NaiveSpillScheduler>()'
    assert ref.count(marker)==ref.count(ctor)==1
    src=ref.replace(ctor,'makeScheduler(argc>2?std::stoi(argv[2]):0)',1).replace(marker,header+marker,1)
    (ROOT/'engine.cpp').write_bytes(src.encode('utf8'))
    p=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors',str(ROOT/'engine.cpp'),'-o',str(ROOT/'engine')],capture_output=True,text=True)
    (ROOT/'compile.log').write_text(p.stderr)
    if p.returncode:raise RuntimeError(p.stderr)
    (ROOT/'variants.json').write_text(json.dumps(variants,indent=2),encoding='utf8');print('Compiled',len(variants),'tree candidates',flush=True)
if __name__=='__main__':build()
