from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'ReserveScheduler.cpp').read_text('utf8')
s=s.replace('for(auto& g:ghost_)if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}',
 'for(int i=0,q=int(s.operators.size())*s.num_partitions;i<q;++i){auto& g=ghost_[i];if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}}')
s=s.replace('uint64_t now=tick(s);int mask=0;\n        for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;',
 'uint64_t now=tick(s);int mask=phase_mask_;\n        if(mask!=((1<<int(s.operators.size()))-1)){mask=0;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;}')
(ROOT/'ActiveScheduler.cpp').write_text(s,encoding='utf8')
s=s.replace('    int flags_,rule_=4;','    bool min_cached_=false;int64_t min_size_=INT64_MAX;\n    int flags_,rule_=4;')
needle='        std::array<Victim,512> c;int n=0,best=-1;uint64_t now=tick(s);'
assert needle in s
fast='''        if(!build&&rule==6&&!(flags_&1024)&&phase_mask_==((1<<int(s.operators.size()))-1)) {
            if(!min_cached_){for(const auto& op:s.operators)for(const auto& x:op.partitions)if(x.data_size>0)min_size_=std::min(min_size_,x.data_size);min_cached_=true;}
            if(deficit<=min_size_) {
                int bo=-1,bp=-1,bid=-1;int64_t bs=0;double bn=0;uint64_t now=tick(s);
                for(const auto& op:s.operators)for(const auto& x:op.partitions) {
                    int o=op.op_id,p=x.partition_id,id=o*s.num_partitions+p;
                    if(!x.in_memory||x.data_size<=0||(o==to&&p==tp)||(o==po&&p==pp))continue;
                    uint64_t age=now>last_[id]?now-last_[id]:0;
                    double h=double(heat_[id])/(1.0+double(age)/64.0);
                    double num=(1.0+h)*factor[o];
                    if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)num*=16.0;
                    bool better=bo<0;
                    if(!better){
                        double l=num*double(bs),r=bn*double(x.data_size),bound=0.00000000000001*(l+r);
                        if(l<r-bound)better=true;
                        else if(l<=r+bound){
                            // Near equal values use the original rounded divisions
                            // and exactly its size/ID tie breaking.
                            double a=num/double(x.data_size),b=bn/double(bs);
                            better=a<b||(a==b&&(x.data_size>bs||(x.data_size==bs&&id>bid)));
                        }
                    }
                    if(better){bo=o;bp=p;bid=id;bs=x.data_size;bn=num;}
                }
                if(bo>=0){++linear_plans;std::vector<Action> a;a.reserve(3);a.emplace_back(Action::SPILL,bo,bp);return a;}
            }
        }
'''
s=s.replace(needle,fast+needle)
(ROOT/'FrequencyScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'cold':'ColdScheduler.cpp'","'cold':'ColdScheduler.cpp','active':'ActiveScheduler.cpp','frequency':'FrequencyScheduler.cpp'")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
e=(ROOT/'prepare_strict.py').read_text('utf8').replace("('Cold','Cold')","('Cold','Cold'),('Active','Active'),('Frequency','Frequency')")
e=e.replace('    else throw std::runtime_error("Unknown profile");','    else if(name=="active")policy.reset(new ActiveScheduler());\n    else if(name=="frequency")policy.reset(new FrequencyScheduler());\n    else throw std::runtime_error("Unknown profile");')
(ROOT/'prepare_strict.py').write_text(e,encoding='utf8')
print('Generated active-range baseline and filtered ratio comparisons.')
