// Offline observer: no shadow decision is returned to the engine.
#include <map>
class MySpillScheduler : public SpillScheduler {
    ReferencePair inner_;
    std::vector<bool> core_;
    std::map<std::string,long double> sums_;
    std::mt19937 rng_;
    int64_t callbacks_=0,misses_=0,pressure_=0;
    struct Sample {int64_t probe;std::string json;};
    std::vector<Sample> samples_;
    struct Item {int id;int64_t size;double prob,density;};
    static void array(std::ostream& out,const std::vector<bool>& a) {
        out<<'[';for(size_t i=0;i<a.size();++i){if(i)out<<',';out<<(a[i]?1:0);}out<<']';
    }
    static void metrics(std::ostream& out,const std::map<std::string,double>& a) {
        out<<'{';bool comma=false;for(const auto& kv:a){if(comma)out<<',';comma=true;out<<'"'<<kv.first<<"\":"<<kv.second;}out<<'}';
    }
    void diagnose(const SystemState& s,int op,int pid,const std::vector<Action>& actions) {
        if(!pressure(s,op,pid))return;
        ++pressure_;
        const int n=static_cast<int>(s.operators.size())*s.num_partitions;
        if(static_cast<int>(core_.size())!=n)core_.assign(n,false);
        const auto previous=core_;
        const auto probability=inner_.diagnosticProbabilities();
        if(static_cast<int>(probability.size())!=n)throw std::runtime_error("probability size");
        std::vector<Item> items;double mass=0,discrepancy=0;
        for(const auto& o:s.operators)for(const auto& x:o.partitions)if(x.data_size>0) {
            int id=o.op_id*s.num_partitions+x.partition_id;double p=probability[id];
            items.push_back({id,x.data_size,p,p*(1.0/s.read_bandwidth+1.0/s.write_bandwidth+1.0/x.data_size)});mass+=p;
        }
        if(!items.empty())for(const auto& x:items)discrepancy+=std::abs(x.prob/mass-1.0/items.size());
        std::map<std::string,double> z;
        z["pressure_states"]=1;z["sample_mass"]=inner_.diagnosticSampleMass();z["positive_probability_mass"]=mass;
        z["discrepancy_L1"]=discrepancy;
        const bool low=items.empty() || inner_.diagnosticSampleMass()<64;
        const bool concentrated=!low && discrepancy>=0.30;
        z["gate_low_samples"]=low;z["gate_low_concentration"]=!low && !concentrated;z["active"]=concentrated;
        int64_t all_spill_bytes=0;
        for(const auto& a:actions)if(a.type==Action::SPILL)all_spill_bytes+=s.operators[a.op_id].partitions[a.partition_id].data_size;
        z["actual_spill_bytes"]=static_cast<double>(all_spill_bytes);
        std::fill(core_.begin(),core_.end(),false);
        if(concentrated) {
            std::sort(items.begin(),items.end(),[&](const Item& a,const Item& b){
                const double da=a.density*(previous[a.id]?1.1:1.0),db=b.density*(previous[b.id]?1.1:1.0);
                return da!=db?da>db:a.id<b.id;
            });
            int64_t available=s.memory_limit;std::vector<Item> cold;
            std::vector<bool> cold0(n,false);
            for(const auto& x:items)if(x.size<=available)available-=x.size;else{cold.push_back(x);cold0[x.id]=true;}
            double cold_mass=0;for(const auto& x:cold)cold_mass+=x.prob;
            std::sort(cold.begin(),cold.end(),[](const Item& a,const Item& b){return a.size!=b.size?a.size<b.size:a.id<b.id;});
            int64_t reserve=0;double cumulative=0;
            if(cold_mass>0)for(const auto& x:cold){cumulative+=x.prob;reserve=x.size;if(cumulative>=0.5*cold_mass)break;}
            available=std::max<int64_t>(0,s.memory_limit-reserve);
            for(const auto& x:items)if(x.size<=available){core_[x.id]=true;available-=x.size;}
            int64_t core_bytes=0,resident_bytes=0;double core_mass=0,resident_mass=0,cold1_mass=0;
            for(const auto& x:items) {
                if(core_[x.id]){core_bytes+=x.size;core_mass+=x.prob;
                    if(s.operators[x.id/s.num_partitions].partitions[x.id%s.num_partitions].in_memory){resident_bytes+=x.size;resident_mass+=x.prob;}}
                else cold1_mass+=x.prob;
            }
            const int64_t effective=s.memory_limit-core_bytes,resident_effective=s.memory_limit-resident_bytes;
            double over_nominal=0,over_effective=0,added_cold=0,removed_cold=0;
            int different=0;
            for(const auto& x:items) {
                if(!core_[x.id]){if(x.size>reserve)over_nominal+=x.prob;if(x.size>effective)over_effective+=x.prob;}
                if(!core_[x.id] && !cold0[x.id]){added_cold+=x.prob;++different;}
                if(core_[x.id] && cold0[x.id]){removed_cold+=x.prob;++different;}
            }
            z["cold0_mass"]=cold_mass;z["cold1_mass"]=cold1_mass;z["added_cold_mass"]=added_cold;z["removed_cold_mass"]=removed_cold;
            z["changed_members"]=different;z["changed_cold_mass"]=added_cold+removed_cold;z["tail_changed"]=different>0;
            z["nominal_reserve_bytes"]=static_cast<double>(reserve);z["effective_reserve_bytes"]=static_cast<double>(effective);
            z["resident_effective_reserve_bytes"]=static_cast<double>(resident_effective);
            z["core_bytes"]=static_cast<double>(core_bytes);z["core_mass"]=core_mass;
            z["resident_core_bytes"]=static_cast<double>(resident_bytes);z["resident_core_mass"]=resident_mass;
            z["missing_core_bytes"]=static_cast<double>(core_bytes-resident_bytes);z["missing_core_mass"]=core_mass-resident_mass;
            z["over_nominal_mass"]=over_nominal;z["over_effective_mass"]=over_effective;
            z["over_nominal_fraction"]=cold1_mass>0?over_nominal/cold1_mass:0;
            z["over_effective_fraction"]=cold1_mass>0?over_effective/cold1_mass:0;
            const bool nominal_bad=z["over_nominal_fraction"]>0.5+1e-12,effective_bad=z["over_effective_fraction"]>0.5+1e-12;
            z["nominal_mismatch"]=nominal_bad;z["effective_mismatch"]=effective_bad;
            const int target=op*s.num_partitions+pid;const int64_t target_bytes=s.operators[op].partitions[pid].data_size;
            int64_t next_extra=0;
            if(s.next_op.type=="PROBE" && s.next_op.op_id>=0 && s.next_op.op_id<static_cast<int>(s.operators.size())) {
                const int np=s.next_op.key%s.num_partitions,ni=s.next_op.op_id*s.num_partitions+np;
                const auto& nx=s.operators[s.next_op.op_id].partitions[np];
                if(ni!=target && nx.in_memory && !core_[ni])next_extra=nx.data_size;
            }
            const bool forced=target_bytes>resident_effective,forced_next=target_bytes>resident_effective-next_extra;
            int64_t lost_bytes=0;double lost_mass=0;int lost_objects=0;
            for(const auto& a:actions)if(a.type==Action::SPILL) {
                int id=a.op_id*s.num_partitions+a.partition_id;
                if(core_[id]){lost_bytes+=s.operators[a.op_id].partitions[a.partition_id].data_size;lost_mass+=probability[id];++lost_objects;}
            }
            if(forced && !lost_objects)throw std::runtime_error("forced core break not observed");
            z["core_target"]=core_[target];z["cold_target"]=!core_[target];
            z["current_forces_core_break"]=forced;z["current_forces_core_break_with_next"]=forced_next;
            z["observed_core_break"]=lost_objects>0;z["observed_core_spill_bytes"]=static_cast<double>(lost_bytes);
            z["observed_core_spill_mass"]=lost_mass;z["observed_core_spill_objects"]=lost_objects;
            z["core_break_capacity_avoidable"]=lost_objects>0 && !forced;
            z["core_break_capacity_avoidable_with_next"]=lost_objects>0 && !forced_next;
            z["avoidable_with_next_core_spill_bytes"]=(lost_objects>0 && !forced_next)?static_cast<double>(lost_bytes):0;
            z["core_break_when_effective_mismatch"]=lost_objects>0 && effective_bad;
            z["core_break_when_no_effective_mismatch"]=lost_objects>0 && !effective_bad;
            z["core_spill_bytes_when_effective_mismatch"]=effective_bad?static_cast<double>(lost_bytes):0;
            z["actual_spill_bytes_active"]=static_cast<double>(all_spill_bytes);
        }
        for(const auto& kv:z)sums_[kv.first]+=kv.second;
        int64_t slot=pressure_<=128?pressure_-1:std::uniform_int_distribution<int64_t>(0,pressure_-1)(rng_);
        if(slot<128) {
            std::ostringstream out;out<<std::setprecision(17);
            out<<"{\"probe\":"<<s.hit_count+s.miss_count<<",\"miss_ordinal\":"<<misses_<<",\"callback_index\":"<<callbacks_
               <<",\"state_hash\":\""<<stateHash(s)<<"\",\"op\":"<<op<<",\"pid\":"<<pid
               <<",\"sample_mass\":"<<inner_.diagnosticSampleMass()<<",\"sizes\":[";
            bool comma=false;for(const auto& o:s.operators)for(const auto& x:o.partitions){if(comma)out<<',';comma=true;out<<x.data_size;}
            out<<"],\"resident\":[";comma=false;for(const auto& o:s.operators)for(const auto& x:o.partitions){if(comma)out<<',';comma=true;out<<(x.in_memory?1:0);}
            out<<"],\"probability\":[";for(size_t i=0;i<probability.size();++i){if(i)out<<',';out<<probability[i];}
            out<<"],\"before_core\":";array(out,previous);out<<",\"after_core\":";array(out,core_);
            out<<",\"next\":[\""<<s.next_op.type<<"\","<<s.next_op.op_id<<','<<s.next_op.key<<','<<s.next_op.tuple_size<<']';
            out<<",\"memory_used\":"<<s.memory_used<<",\"hits\":"<<s.hit_count<<",\"misses\":"<<s.miss_count<<",\"total_io_bytes\":"<<s.total_io_bytes;
            out<<",\"metrics\":";metrics(out,z);out<<'}';
            Sample sample{s.hit_count+s.miss_count,out.str()};
            if(pressure_<=128)samples_.push_back(sample);else samples_[slot]=sample;
        }
    }
public:
    MySpillScheduler():rng_(0) {
        const char* seed=std::getenv("R9_CORE_SAMPLE_SEED");if(!seed)throw std::runtime_error("missing shadow seed");
        rng_.seed(static_cast<unsigned>(std::strtoul(seed,nullptr,10)));
    }
    ~MySpillScheduler() {
        std::cerr<<std::setprecision(17)<<"CORE_COUNTS {\"callbacks\":"<<callbacks_<<",\"misses\":"<<misses_<<",\"pressure\":"<<pressure_<<",\"sums\":{";
        bool comma=false;for(const auto& kv:sums_){if(comma)std::cerr<<',';comma=true;std::cerr<<'"'<<kv.first<<"\":"<<kv.second;}
        std::cerr<<"}}\n";
        std::sort(samples_.begin(),samples_.end(),[](const Sample& a,const Sample& b){return a.probe<b.probe;});
        for(const auto& sample:samples_)std::cerr<<"CORE_SAMPLE "<<sample.json<<'\n';
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        ++callbacks_;return inner_.onMemoryOverflow(s,op,pid,z);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        ++callbacks_;++misses_;auto actions=inner_.onPartitionMiss(s,op,pid);diagnose(s,op,pid,actions);return actions;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        ++callbacks_;return inner_.onPeriodicAdjust(s);
    }
};
