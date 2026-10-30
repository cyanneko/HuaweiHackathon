// Diagnostic wrapper: before-estimation, unchanged paired action, after-residency.
#include <chrono>
#include <ctime>
#include <iomanip>
#include <iostream>
class MySpillScheduler : public SpillScheduler {
    ReferencePair inner_;BoundedHitV1 stats_;
    int checkpoint_=0;int64_t last_q_=0;double cpu_us_=0,wall_us_=0;
    static BoundedHitV1::Mask mask(const SystemState& s) {
        BoundedHitV1::Mask m{};for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory){int id=o.op_id*s.num_partitions+p.partition_id;m[id/64]|=1ULL<<(id%64);}return m;
    }
    static void probabilities(const BoundedHitV1& model,int kind) {
        std::cerr<<'[';for(int i=0;i<model.size();++i){if(i)std::cerr<<',';std::cerr<<(kind==0?model.probability(i):kind==1?model.fittedNext(i):model.freshNext(i));}std::cerr<<']';
    }
    static void block(const BoundedHitV1::Block& b,int n) {
        std::cerr<<"{\"begin\":"<<b.begin<<",\"end\":"<<b.end<<",\"hidden\":"<<b.hidden<<",\"mask\":\"";
        for(int i=0;i<n;++i)std::cerr<<((b.mask[i/64]>>(i%64))&1ULL);
        std::cerr<<"\",\"exact\":[";
        for(int j=0;j<b.exact;++j){if(j)std::cerr<<',';std::cerr<<'['<<b.id[j]<<','<<static_cast<int>(b.source[j])<<']';}std::cerr<<"]}";
    }
    void before(const SystemState& s,char tag,int op=-1,int pid=-1) {
        bool all=true;for(const auto& o:s.operators)all=all && o.phase==Phase::PROBE;
        int next=-1;if(s.next_op.type=="PROBE")next=s.next_op.op_id*s.num_partitions+s.next_op.key%s.num_partitions;
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        stats_.before(s.operators.size()*s.num_partitions,all,s.hit_count+s.miss_count,s.hit_count,s.miss_count,mask(s),tag,op<0?-1:op*s.num_partitions+pid,next);
        cpu_us_+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;wall_us_+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        last_q_=s.hit_count+s.miss_count;
        if(checkpoint_<4 && (stats_.active() || stats_.delta().reset)) {
            const auto& d=stats_.delta();
            std::cerr<<std::setprecision(17)<<"BH_EVENT {\"q\":"<<last_q_<<",\"n\":"<<stats_.size()<<",\"active\":"<<(stats_.active()?"true":"false")
                     <<",\"reset\":"<<(d.reset?"true":"false")<<",\"live_id\":"<<stats_.liveId()<<",\"live_q\":"<<stats_.liveQ()<<",\"block\":";
            if(d.block_added)block(d.block,stats_.size());else std::cerr<<"null";
            std::cerr<<",\"fit\":"<<(d.fitted?"true":"false")<<",\"fit_q\":"<<stats_.fitQ();
            if(d.fitted){std::cerr<<",\"p\":";probabilities(stats_,0);std::cerr<<",\"next_p\":";probabilities(stats_,1);}
            std::cerr<<"}\n";
        }
    }
    void after(const SystemState& s,const std::vector<Action>& actions) {
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        auto m=mask(s);for(const auto& a:actions){int id=a.op_id*s.num_partitions+a.partition_id;if(a.type==Action::LOAD)m[id/64]|=1ULL<<(id%64);else m[id/64]&=~(1ULL<<(id%64));}
        stats_.after(m);
        cpu_us_+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;wall_us_+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        const int thresholds[4]={64,256,1024,4096};
        while(stats_.active() && checkpoint_<4 && last_q_>=thresholds[checkpoint_]) {
            BoundedHitV1 fresh=stats_;fresh.fit(last_q_);
            std::cerr<<std::setprecision(17)<<"BH_SNAPSHOT {\"threshold\":"<<thresholds[checkpoint_++]<<",\"q\":"<<last_q_<<",\"fit_q\":"<<stats_.fitQ()
                     <<",\"span\":"<<stats_.span(last_q_)<<",\"blocks\":"<<stats_.blocks()<<",\"next_count\":"<<stats_.nextCount()
                     <<",\"miss_only_count\":"<<stats_.exactCount()-stats_.nextCount()<<",\"anonymous\":"<<stats_.anonymousCount()<<",\"constant_hits\":"<<stats_.constantCount()
                     <<",\"live_id\":"<<stats_.liveId()<<",\"cached\":";probabilities(stats_,0);
            std::cerr<<",\"cached_next\":";probabilities(stats_,1);std::cerr<<",\"fresh\":";probabilities(fresh,0);std::cerr<<",\"fresh_next\":";probabilities(stats_,2);
            const auto old=inner_.diagnosticProbabilities();std::cerr<<",\"paired_next\":[";for(size_t i=0;i<old.size();++i){if(i)std::cerr<<',';std::cerr<<old[i];}std::cerr<<"]}\n";
        }
    }
public:
    ~MySpillScheduler() {
        const auto& c=stats_.counters();
        std::cerr<<std::setprecision(17)<<"BH_STATS {\"sizeof_estimator\":"<<sizeof(BoundedHitV1)<<",\"callbacks\":"<<c.before_calls<<",\"epochs\":"<<c.epochs
                 <<",\"intervals\":"<<c.intervals<<",\"anonymous_observed\":"<<c.hidden<<",\"known_hits\":"<<c.known_hits<<",\"duplicate_next\":"<<c.duplicate_next
                 <<",\"evictions\":"<<c.evictions<<",\"fits\":"<<c.fits<<",\"em_fits\":"<<c.em_fits<<",\"analytic_fits\":"<<c.analytic_fits
                 <<",\"max_probe_span\":"<<c.max_span<<",\"fit_span_sum\":"<<c.fit_span_sum<<",\"max_blocks\":"<<c.max_blocks<<",\"member_visits\":"<<c.member_visits
                 <<",\"last_observed_q\":"<<last_q_<<",\"last_fit_q\":"<<stats_.fitQ()<<",\"current_span\":"<<stats_.span(last_q_)
                 <<",\"kernel_process_cpu_us\":"<<cpu_us_<<",\"kernel_wall_us\":"<<wall_us_<<",\"checkpoints\":"<<checkpoint_<<"}\n";
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t bytes) override {
        before(s,'O',op,pid);auto actions=inner_.onMemoryOverflow(s,op,pid,bytes);after(s,actions);return actions;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        before(s,'M',op,pid);auto actions=inner_.onPartitionMiss(s,op,pid);after(s,actions);return actions;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        before(s,'P');auto actions=inner_.onPeriodicAdjust(s);after(s,actions);return actions;
    }
};
