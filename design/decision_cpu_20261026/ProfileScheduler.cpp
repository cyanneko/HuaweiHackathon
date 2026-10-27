#define MySpillScheduler OriginalImplementation
#include "PreviousScheduler.cpp"
#undef MySpillScheduler
#include <chrono>
#include <iostream>
class MySpillScheduler final : public SpillScheduler {
    OriginalImplementation inner_;
    uint64_t rng_=7135123,counts_[3]{},sample_count_[3]{},total_ns_[3]{};
    uint64_t buckets_[3][20]{};
    template<class F> std::vector<Action> call(int type,F f) {
        ++counts_[type];rng_=rng_*6364136223846793005ULL+1;
        if((rng_>>58)!=0)return f();
        auto t=std::chrono::steady_clock::now();auto a=f();
        uint64_t ns=uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-t).count());
        ++sample_count_[type];total_ns_[type]+=ns;int b=0;uint64_t z=ns;while(z>1&&b<19){z>>=1;++b;}++buckets_[type][b];return a;
    }
public:
    ~MySpillScheduler() {
        for(int t=0;t<3;++t){std::cerr<<"PROFILE "<<t<<' '<<counts_[t]<<' '<<sample_count_[t]<<' '<<total_ns_[t];for(int b=0;b<20;++b)std::cerr<<' '<<buckets_[t][b];std::cerr<<'\n';}
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t b)override{return call(0,[&]{return inner_.onMemoryOverflow(s,o,p,b);});}
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return call(1,[&]{return inner_.onPartitionMiss(s,o,p);});}
    std::vector<Action> onPeriodicAdjust(const SystemState& s)override{return call(2,[&]{return inner_.onPeriodicAdjust(s);});}
};
