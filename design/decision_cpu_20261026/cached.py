from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'LeanScheduler.cpp').read_text('utf8')
loc=s.index('    int flags_,rule_=4;')
s=s[:loc]+'''    bool costs_cached_=false;
    int64_t min_positive_size_=INT64_MAX;
    std::array<double,512> fixed_write_cost_,fixed_read_cost_;
    void cacheImmutableCosts(const SystemState& s) {
        if(costs_cached_||phase_mask_!=((1<<int(s.operators.size()))-1))return;
        for(const auto& op:s.operators)for(const auto& x:op.partitions){
            int id=op.op_id*s.num_partitions+x.partition_id;
            fixed_write_cost_[id]=double(x.data_size)/s.write_bandwidth;
            fixed_read_cost_[id]=double(x.data_size)/s.read_bandwidth+32.0;
            if(x.data_size>0)min_positive_size_=std::min(min_positive_size_,x.data_size);
        }
        costs_cached_=true;
    }
'''+s[loc:]
needle='        auto& c=scratch_;int n=0,best=-1;uint64_t now=tick(s);'
assert needle in s
fast='''        if(!build)cacheImmutableCosts(s);
        // If every eligible object covers the deficit, the original sorted
        // prefix contains one victim. Cost rule 4 then chooses minimum TOTAL
        // value; the other rules choose their minimum ordering key.
        if(!build&&costs_cached_&&deficit<=min_positive_size_) {
            Victim winner{};bool found=false;uint64_t now=tick(s);
            for(const auto& op:s.operators)for(const auto& x:op.partitions) {
                int o=op.op_id,p=x.partition_id,id=o*s.num_partitions+p;
                if(!x.in_memory||x.data_size<=0||(o==to&&p==tp)||(o==po&&p==pp))continue;
                uint64_t age=now>last_[id]?now-last_[id]:0;
                double h=double(heat_[id])/(1.0+double(age)/64.0),key=0,value=0;
                if(rule==4) {
                    double q=.15+.70*h/(1.0+h);
                    if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)q=1.0;
                    value=(fixed_write_cost_[id]+q*fixed_read_cost_[id])*factor[o];key=value;
                } else if(rule==3)key=(double(last_[id])+1.0)*factor[o];
                else if(rule==6) {
                    key=(1.0+h)*factor[o]/double(x.data_size);
                    if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)key*=16.0;
                }
                Victim candidate{o,p,id,x.data_size,value,key};
                if(!found||less(candidate,winner)){winner=candidate;found=true;}
            }
            if(found){++linear_plans;std::vector<Action> a;a.reserve(3);a.emplace_back(Action::SPILL,winner.o,winner.p);return a;}
        }
'''
s=s.replace(needle,fast+needle)
(ROOT/'CachedScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'indexed':'IndexedScheduler.cpp'","'indexed':'IndexedScheduler.cpp','cached':'CachedScheduler.cpp'")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
e=(ROOT/'prepare_strict.py').read_text('utf8').replace("('Indexed','Indexed')","('Indexed','Indexed'),('Cached','Cached')")
e=e.replace('    else throw std::runtime_error("Unknown profile");','    else if(name=="cached")policy.reset(new CachedScheduler());\n    else throw std::runtime_error("Unknown profile");')
(ROOT/'prepare_strict.py').write_text(e,encoding='utf8')
print('Generated immutable exact-cost cache and sufficient-cover streaming selection.')
