"""Learned action-value comparison using only actual callback-visible state."""
from pathlib import Path
from gate_family import source as family_source
FEATURES=r'''
    void actionFeatures(const SystemState& s,const std::vector<Action>& actions,float* f) const {
        double bytes=0,largest=0,known=0,build=0,count=0,age=0,min_age=1024;int spills=0;
        const int64_t q=s.hit_count+s.miss_count+1;
        for(const auto& a:actions)if(a.type==Action::SPILL) {
            const auto& p=s.operators[a.op_id].partitions[a.partition_id];
            const auto& h=history_[a.op_id*p_+a.partition_id];
            bytes+=p.data_size;largest=std::max(largest,static_cast<double>(p.data_size));++spills;
            if(h.last>=0) {
                known+=p.data_size;count+=p.data_size*std::min(16.,h.count);
                const double gap=std::min<int64_t>(1024,std::max<int64_t>(0,q-h.last));
                age+=p.data_size*gap;min_age=std::min(min_age,gap);
            }else age+=p.data_size*1024.;
            if(s.operators[a.op_id].phase==Phase::BUILD)build+=p.data_size;
        }
        f[0]=bytes/s.memory_limit;f[1]=largest/s.memory_limit;
        f[2]=static_cast<float>(spills)/std::max<size_t>(1,history_.size());
        f[3]=known/std::max(1.,bytes);f[4]=build/std::max(1.,bytes);
        f[5]=count/(16*std::max(1.,bytes));f[6]=age/(1024*std::max(1.,bytes));f[7]=min_age/1024;
    }
'''

def internal_source():
    s=family_source(force=0).replace('class MySpillScheduler','class ActionFamily')
    s=s.replace('public:\n','public:\n'+FEATURES,1)
    return s

def submission(code,margin=0.):
    s=internal_source()
    wrapper=r'''
class MySpillScheduler:public SpillScheduler {
    ActionFamily family_;
    double predict(const float* f) const { MODEL }
    static bool same(const std::vector<Action>& a,const std::vector<Action>& b) {
        if(a.size()!=b.size())return false;
        for(size_t i=0;i<a.size();++i)
            if(a[i].type!=b[i].type || a[i].op_id!=b[i].op_id || a[i].partition_id!=b[i].partition_id)return false;
        return true;
    }
    std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t z,bool miss) {
        float context[12];family_.prepareFeatures(s,op,pid,z,miss,context);
        family_.forceMode(0);
        auto baseline=miss?family_.onPartitionMiss(s,op,pid):family_.onMemoryOverflow(s,op,pid,z);
        // When no space was released, every alternative is identical.
        if(baseline.empty() || (miss && baseline.size()==1))return baseline;
        float bf[8];family_.actionFeatures(s,baseline,bf);
        auto best=baseline;double value=-MARGIN;
        for(int mode: {2,3}) {
            family_.forceMode(mode);
            auto trial=miss?family_.onPartitionMiss(s,op,pid):family_.onMemoryOverflow(s,op,pid,z);
            if(same(trial,baseline))continue;
            float af[8],f[30];family_.actionFeatures(s,trial,af);
            for(int j=0;j<12;++j)f[j]=context[j];
            for(int j=0;j<8;++j){f[12+j]=af[j];f[20+j]=af[j]-bf[j];}
            f[28]=std::log2(s.read_bandwidth/s.write_bandwidth)/14.;
            f[29]=std::log2(s.write_bandwidth)/14.;
            const double p=predict(f);
            if(p<value){value=p;best=trial;}
        }
        family_.forceMode(0);return best;
    }
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t z) override {return choose(s,o,p,z,false);}
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {family_.forceMode(0);return family_.onPeriodicAdjust(s);}
};
'''
    cut=s.index('class ActionFamily')
    prefix=s[:cut];inner=s[cut:]
    wrapper=wrapper.replace('    ActionFamily family_;',inner+'\n    ActionFamily family_;')
    return prefix+wrapper.replace('MODEL',code).replace('MARGIN',str(margin))
