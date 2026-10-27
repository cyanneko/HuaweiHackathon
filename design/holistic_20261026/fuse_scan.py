"""Action-preserving loop fusion, independent of policy experiments."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
for src,dst in [('Previous.cpp','Fused.cpp'),('MySpillScheduler.cpp','FusedCover.cpp')]:
    s=(ROOT/src).read_text('utf8')
    begin=s.index('        if(quota) {\n',s.index('    std::vector<Action> plan('))
    end=s.index('            double v=0,key=-double(x.data_size)/factor[o];',begin)
    s=s[:begin]+'''        if(quota && (build || !allocations))allocate(s);
        std::array<Victim,512> c;int n=0,best=-1;uint64_t now=tick(s);
        // Read the public partition table once. Preserve accumulation order,
        // candidate order, floating-point expressions and every tie-break.
        for(const auto& op:s.operators)for(const auto& x:op.partitions) {
            if(!x.in_memory)continue;
            int o=op.op_id,p=x.partition_id;
            if(quota)used[o]+=double(x.data_size);
            if(x.data_size<=0||(o==to&&p==tp)||(o==po&&p==pp))continue;
            c[n++]={o,p,o*s.num_partitions+p,x.data_size,0,0};
        }
        if(quota) {
            double pad=double(s.memory_limit)/(32.0*s.operators.size());
            for(unsigned o=0;o<s.operators.size();++o)factor[o]=clip((budget_[o]+pad)/(used[o]+pad),.5,2.0);
        }
        for(int i=0;i<n;++i) {
            int o=c[i].o,p=c[i].p,id=c[i].id;
            const auto& op=s.operators[o];const auto& x=op.partitions[p];
'''+s[end:]
    old='            c[n]={o,p,id,x.data_size,v,key};if(best<0||less(c[n],c[best]))best=n;++n;'
    assert s.count(old)==1
    s=s.replace(old,'            c[i].value=v;c[i].key=key;if(best<0||less(c[i],c[best]))best=i;')
    (ROOT/dst).write_text(s,encoding='utf8')
freeze={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['Fused.cpp','FusedCover.cpp']}
(ROOT/'fused_freeze.json').write_text(json.dumps(freeze,indent=2))
# Extend the independent ledger; do not regenerate earlier inputs.
s=(ROOT/'strict_replay.cpp').read_text('utf8')
pos=s.index('\nstruct Op ')
incs='\n#define MySpillScheduler Fused\n#include "Fused.cpp"\n#undef MySpillScheduler\n#define MySpillScheduler FusedCover\n#include "FusedCover.cpp"\n#undef MySpillScheduler\n'
s=s[:pos]+incs+s[pos:]
pos=s.index('    else throw std::runtime_error("Unknown policy");')
s=s[:pos]+'    else if(name=="fused")policy.reset(new Fused());\n    else if(name=="fused_cover")policy.reset(new FusedCover());\n'+s[pos:]
(ROOT/'strict_fused.cpp').write_text(s,encoding='utf8')
print('Frozen',freeze)
