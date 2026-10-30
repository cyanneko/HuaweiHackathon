// Only actual calls reach inner_; counterfactual calls use the pre-callback copy.
class MySpillScheduler : public SpillScheduler {
    R80ObservedReference inner_;
    uint64_t callback_=0;
    int next_threshold_=0,snapshots_=0;
    std::vector<Action> demand(const SystemState& s,char tag,int op,int pid,int64_t required) {
        ++callback_;const int bounds[3]={256,1024,4096};const int64_t q=s.hit_count+s.miss_count;
        const bool selected=next_threshold_<3 && q>=bounds[next_threshold_] && required>s.memory_limit-s.memory_used;
        std::vector<int> thresholds;std::unique_ptr<R80ObservedReference> before;
        if(selected) {
            while(next_threshold_<3 && q>=bounds[next_threshold_])thresholds.push_back(bounds[next_threshold_++]);
            before.reset(new R80ObservedReference(inner_));
        }
        auto actions=tag=='M'?inner_.onPartitionMiss(s,op,pid):inner_.onMemoryOverflow(s,op,pid,required);
        if(selected){before->observerEmit(s,tag,op,pid,required,callback_,thresholds,actions);++snapshots_;}
        return actions;
    }
public:
    ~MySpillScheduler() override {
        std::cerr << "OBS_END {\"callbacks\":" << callback_ << ",\"snapshots\":" << snapshots_
                  << ",\"thresholds_consumed\":" << next_threshold_ << "}\n";
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t bytes) override {
        return demand(s,'O',op,pid,bytes);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        return demand(s,'M',op,pid,s.operators[op].partitions[pid].data_size);
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        ++callback_;return inner_.onPeriodicAdjust(s);
    }
};
