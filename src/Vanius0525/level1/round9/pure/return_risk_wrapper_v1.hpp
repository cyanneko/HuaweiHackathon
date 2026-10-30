class MySpillScheduler : public SpillScheduler {
    ReferencePair inner_;ReturnRiskV1 stats_;int checkpoint_=0;int64_t next_checkpoint_=64;
    void before(const SystemState& s,char tag,int id) {
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        stats_.before(s,tag,id,[&](int i){return inner_.diagnosticProbability(i);});
        stats_.cpu_us+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;stats_.wall_us+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
    }
    void after(const SystemState& s,char tag,int id,const std::vector<Action>& actions) {
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        stats_.after(s,tag,id,actions);
        stats_.cpu_us+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;stats_.wall_us+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        if(stats_.active() && stats_.q()>=next_checkpoint_){snapshot();const int thresholds[4]={64,256,1024,4096};++checkpoint_;next_checkpoint_=checkpoint_<4?thresholds[checkpoint_]:((stats_.q()/65536)+1)*65536;}
    }
    void snapshot() {
        stats_.sync();std::cerr<<std::setprecision(17)<<"RR_SNAPSHOT {\"cb\":"<<stats_.c.callbacks<<",\"q\":"<<stats_.q()<<",\"d\":[";
        for(int i=0;i<stats_.size();++i){if(i)std::cerr<<',';std::cerr<<stats_.d[i];}std::cerr<<"],\"z\":[";
        for(int i=0;i<stats_.size();++i){if(i)std::cerr<<',';std::cerr<<stats_.z[i];}std::cerr<<"],\"p\":[";
        for(int i=0;i<stats_.size();++i){if(i)std::cerr<<',';std::cerr<<inner_.diagnosticProbability(i);}std::cerr<<"]}\n";
    }
public:
    MySpillScheduler(){inner_.diagnosticHook(&stats_);}
    ~MySpillScheduler(){if(stats_.active())snapshot();stats_.print_stats();}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t bytes) override {int id=op*s.num_partitions+pid;before(s,'O',id);auto a=inner_.onMemoryOverflow(s,op,pid,bytes);after(s,'O',id,a);return a;}
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {int id=op*s.num_partitions+pid;before(s,'M',id);auto a=inner_.onPartitionMiss(s,op,pid);after(s,'M',id,a);return a;}
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {before(s,'P',-1);auto a=inner_.onPeriodicAdjust(s);after(s,'P',-1,a);return a;}
};
