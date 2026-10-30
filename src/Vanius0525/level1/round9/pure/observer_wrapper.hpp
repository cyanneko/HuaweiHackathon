// ReferencePair is the unchanged Round8 paired class with only its class name changed.
class MySpillScheduler : public SpillScheduler {
    ReferencePair inner_;
    struct Sample {int64_t q;uint64_t hash;};
    std::vector<Sample> samples_;
    int64_t misses_=0,pressure_=0,resident_=0,eligible_=0;
    std::mt19937 rng_;
public:
    MySpillScheduler():rng_(0) {
        const char* seed=std::getenv("R9_SAMPLE_SEED");if(!seed)throw std::runtime_error("missing diagnostic sampling seed");
        rng_.seed(static_cast<unsigned>(std::strtoul(seed,nullptr,10)));
    }
    ~MySpillScheduler() {
        std::sort(samples_.begin(),samples_.end(),[](const Sample& a,const Sample& b){return a.q<b.q;});
        std::cerr<<"NEXT_COUNTS "<<misses_<<' '<<pressure_<<' '<<resident_<<' '<<eligible_<<'\n';
        for(const auto& x:samples_)std::cerr<<"NEXT_SAMPLE "<<x.q<<' '<<x.hash<<'\n';
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t z) override {
        return inner_.onMemoryOverflow(s,o,p,z);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        ++misses_;if(pressure(s,o,p)){++pressure_;if(residentNext(s,o,p))++resident_;}
        if(eligible(s,o,p)) {
            ++eligible_;Sample x{s.hit_count+s.miss_count,stateHash(s)};
            if(samples_.size()<128)samples_.push_back(x);
            else {int64_t j=std::uniform_int_distribution<int64_t>(0,eligible_-1)(rng_);if(j<128)samples_[j]=x;}
        }
        return inner_.onPartitionMiss(s,o,p);
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {return inner_.onPeriodicAdjust(s);}
};
