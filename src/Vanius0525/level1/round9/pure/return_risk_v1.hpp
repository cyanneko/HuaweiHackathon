// Read-only return-risk statistics. Exact known-next exclusion, no policy action.
#include <array>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <ctime>
#include <chrono>
class ReturnRiskV1 {
public:
    static constexpr int MAX_N=512,MAX_K=8;
    struct Loss { double event=0,nonevent=0; int64_t events=0,nonevents=0,event_inf=0,nonevent_inf=0,clipped_trials=0; };
    struct Real {int64_t starts=0,initial=0,demand=0,known_demand=0,unknown_demand=0,prefetch=0,prefetch_confirmed=0,other_load=0,own_returns=0,own_wait_sum=0,own_wait_max=0,disk_exposure_closed=0,spill_bytes=0,read_bytes=0;};
    struct Counts {int64_t callbacks=0,epochs=0,mixed=0,intervals=0,known_positions=0,unknown_positions=0,known_hits=0,known_misses=0,duplicates=0,unknown_events=0,unknown_trials=0,fast_intervals=0,pressure=0,checks=0,pairs=0,pool_changed=0,flat_changed=0,base_alt=0,pool_alt=0,flat_alt=0;};
    std::array<double,MAX_N> d{},z{};
    std::array<std::array<Loss,MAX_K>,3> loss{}; // base, pooled, flat
    std::array<Real,MAX_K> real{};
    Counts c;
    double cpu_us=0,wall_us=0,sum_h_min=1e300,sum_h_max=0;
private:
    std::array<bool,MAX_N> resident{},open{},own{};
    std::array<int64_t,MAX_N> disk_start{},born{};
    int n_=0,k_=0,p_=0,live_id_=-1,pending_id_=-1;
    int64_t last_q_=0,last_h_=0,last_m_=0,live_q_=-1,stat_q_=0,pending_born_=-1;
    bool active_=false,committed_=false,ever_unknown_=false,pending_own_=false;
    const double loga_=std::log(0.5)/2048.0;
    static void check(bool yes,const char* what){if(!yes)throw std::runtime_error(what);}
    void advance(int64_t q) {
        check(q>=stat_q_,"risk time reversed");
        if(q==stat_q_)return;
        if(ever_unknown_){double a=std::exp(loga_*static_cast<double>(q-stat_q_));for(int i=0;i<n_;++i){d[i]*=a;z[i]*=a;}}
        stat_q_=q;
    }
    void completed(int id,int64_t q) {
        auto& a=real[id/p_];
        if(own[id]){++a.own_returns;a.own_wait_sum+=q-born[id];a.own_wait_max=std::max(a.own_wait_max,q-born[id]);}
    }
    void close_disk(int id,int64_t q) {
        check(open[id],"closing absent disk episode");
        real[id/p_].disk_exposure_closed+=q-disk_start[id];open[id]=false;
    }
    static void score(Loss& out,double h,int64_t trials,bool event) {
        check(h>=0 && h<=1 && std::isfinite(h),"invalid risk probability");
        if(event){++out.events;if(h==0)++out.event_inf;else out.event-=std::log(h);}
        const int64_t nonevents=trials-static_cast<int>(event);check(nonevents>=0,"event without exposure");
        out.nonevents+=nonevents;
        if(h==1){out.nonevent_inf+=nonevents;out.clipped_trials+=trials;}
        else out.nonevent-=nonevents*std::log1p(-h);
    }
    template<class P> void predict(P prob,std::array<double,MAX_N>& base,std::array<double,MAX_N>& pooled,std::array<double,MAX_N>& flat) const {
        std::array<double,MAX_K> gd{},gz{};
        for(int i=0;i<n_;++i){gd[i/p_]+=d[i];gz[i/p_]+=z[i];}
        for(int i=0;i<n_;++i){
            base[i]=prob(i);
            const double rg=(1.0+std::max(0.0,gd[i/p_]-d[i]))/(1.0+std::max(0.0,gz[i/p_]-z[i]));
            pooled[i]=std::min(1.0,base[i]*(rg+d[i])/(1.0+z[i]));
            flat[i]=std::min(1.0,base[i]*(1.0+d[i])/(1.0+z[i]));
        }
    }
public:
    int size() const{return n_;} int operators() const{return k_;} int partitions()const{return p_;}
    bool active()const{return active_;} int64_t q()const{return last_q_;} int liveId()const{return live_id_;} int64_t liveQ()const{return live_q_;}
    int pendingId()const{return pending_id_;}
    void sync(){if(active_)advance(last_q_);}
    int64_t ongoingExposure(int op)const{int64_t v=0;for(int i=op*p_;i<(op+1)*p_;++i)if(open[i])v+=last_q_-disk_start[i];return v;}
    int64_t censoredOwnCount(int op)const{int64_t v=0;for(int i=op*p_;i<(op+1)*p_;++i)v+=open[i]&&own[i];return v;}
    int64_t censoredOwnAge(int op)const{int64_t v=0;for(int i=op*p_;i<(op+1)*p_;++i)if(open[i]&&own[i])v+=last_q_-born[i];return v;}
    template<class P> void before(const SystemState& s,char tag,int miss_id,P probability) {
        ++c.callbacks;bool all=true;for(const auto& op:s.operators)all=all&&op.phase==Phase::PROBE;
        if(!all){++c.mixed;active_=committed_=false;return;}
        const int64_t qnow=s.hit_count+s.miss_count;
        if(!active_) {
            active_=true;committed_=false;ever_unknown_=false;++c.epochs;
            k_=s.operators.size();p_=s.num_partitions;n_=k_*p_;check(n_<=MAX_N,"risk n");
            d.fill(0);z.fill(0);open.fill(false);own.fill(false);born.fill(-1);
            live_id_=pending_id_=-1;live_q_=-1;stat_q_=qnow;
            for(const auto& op:s.operators)for(const auto& pa:op.partitions){int id=op.op_id*p_+pa.partition_id;resident[id]=pa.in_memory;if(!pa.in_memory){open[id]=true;disk_start[id]=qnow;++real[op.op_id].initial;}}
        }
        bool known=false;int known_id=-1;int64_t known_q=-1;
        if(committed_) {
            const int64_t len=qnow-last_q_;check(len>=0,"risk q decrease");
            check(s.miss_count-last_m_==(tag=='M'?1:0) && s.hit_count>=last_h_,"risk counters");
            known=live_id_>=0 && live_q_>last_q_ && live_q_<=qnow;known_id=live_id_;known_q=live_q_;
            if(known){
                ++c.known_positions;
                if(resident[known_id])++c.known_hits;
                else{++c.known_misses;check(tag=='M'&&qnow==known_q&&miss_id==known_id,"unreported known miss");}
                if(pending_id_>=0){check(pending_id_==known_id,"prefetch mismatch");++real[pending_id_/p_].prefetch_confirmed;
                    if(pending_own_){auto& a=real[pending_id_/p_];++a.own_returns;a.own_wait_sum+=known_q-pending_born_;a.own_wait_max=std::max(a.own_wait_max,known_q-pending_born_);}pending_id_=-1;}
            }
            const int64_t unknown=len-static_cast<int>(known);check(unknown>=0,"negative unknown span");
            const bool event=tag=='M' && !(known&&known_q==qnow);
            if(len){++c.intervals;c.unknown_positions+=unknown;}
            if(unknown>0) {
                advance(last_q_);
                std::array<double,MAX_N> base{},pool{},flat{};predict(probability,base,pool,flat);
                // Base p is the unchanged inner scheduler state at interval start.
                const double decay=std::exp(loga_*static_cast<double>(len));
                double weight=-std::expm1(loga_*static_cast<double>(len))/(-std::expm1(loga_));
                if(known)weight-=std::exp(loga_*static_cast<double>(qnow-known_q));
                check(weight>=0,"negative geometric exposure");
                for(int i=0;i<n_;++i){
                    d[i]*=decay;z[i]*=decay;
                    if(!resident[i]){
                        const bool hit=event&&i==miss_id;
                        score(loss[0][i/p_],base[i],unknown,hit);score(loss[1][i/p_],pool[i],unknown,hit);score(loss[2][i/p_],flat[i],unknown,hit);
                        c.unknown_trials+=unknown;z[i]+=base[i]*weight;if(hit){d[i]+=1;++c.unknown_events;}
                    }
                    check(resident[i]==s.operators[i/p_].partitions[i%p_].in_memory,"resident changed outside callback");
                }
                stat_q_=qnow;ever_unknown_=true;
            }else{if(len)++c.fast_intervals;check(!event,"unknown event in known-only interval");}
            if(known){live_id_=-1;live_q_=-1;}
        }
        if(tag=='M') {
            check(miss_id>=0 && !resident[miss_id] && open[miss_id],"risk miss state");
            auto& a=real[miss_id/p_];++a.demand;
            if(known&&known_q==qnow)++a.known_demand;else ++a.unknown_demand;
            completed(miss_id,qnow);close_disk(miss_id,qnow);
            if(s.operators[miss_id/p_].partitions[miss_id%p_].data_size>s.memory_limit-s.memory_used)++c.pressure;
        }
        int next=-1;if(s.next_op.type=="PROBE")next=s.next_op.op_id*p_+s.next_op.key%p_;
        if(next>=0){if(live_id_>=0){check(live_id_==next&&live_q_==qnow+1,"duplicate next mismatch");++c.duplicates;}else{live_id_=next;live_q_=qnow+1;}}
        else check(live_id_<0,"live next disappeared");
        last_q_=qnow;last_h_=s.hit_count;last_m_=s.miss_count;
    }
    void after(const SystemState& s,char tag,int miss_id,const std::vector<Action>& actions) {
        if(!active_)return;
        for(const auto& a:actions){const int id=a.op_id*p_+a.partition_id;const int64_t bytes=s.operators[a.op_id].partitions[a.partition_id].data_size;auto& r=real[a.op_id];
            if(a.type==Action::SPILL){check(resident[id]&&!open[id],"risk spill state");resident[id]=false;open[id]=own[id]=true;born[id]=disk_start[id]=last_q_;++r.starts;r.spill_bytes+=bytes;}
            else{check(!resident[id],"risk load state");resident[id]=true;r.read_bytes+=bytes;
                if(tag=='M' && id==miss_id){check(!open[id],"demand episode not closed");}
                else if(id==live_id_){check(pending_id_<0,"double pending prefetch");++r.prefetch;pending_id_=id;pending_born_=born[id];pending_own_=own[id];close_disk(id,last_q_);}
                else{++r.other_load;close_disk(id,last_q_);}
            }
        }
        committed_=true;
    }
    template<class P> void compare(const SystemState& s,const std::vector<Action>& history,const std::vector<Action>& dynamic,const std::vector<int>& sign,double immediate,double base_future,double risk,P probability) {
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        ++c.pairs;const bool base_alt=immediate+base_future+risk<0;
        double pool_future=base_future,flat_future=base_future,write_delta=0;int64_t freed0=0,freed1=0;
        if(ever_unknown_) {
            advance(s.hit_count+s.miss_count);std::array<double,MAX_N> base{},pool{},flat{};predict(probability,base,pool,flat);pool_future=flat_future=0;
            double sum=0;for(int i=0;i<n_;++i){sum+=pool[i];if(sign[i]){const double bytes=s.operators[i/p_].partitions[i%p_].data_size;const double coef=sign[i]*(bytes/s.read_bandwidth+bytes/s.write_bandwidth+100.0);pool_future+=64.0*pool[i]*coef;flat_future+=64.0*flat[i]*coef;}}
            sum_h_min=std::min(sum_h_min,sum);sum_h_max=std::max(sum_h_max,sum);
        }else{sum_h_min=std::min(sum_h_min,1.0);sum_h_max=std::max(sum_h_max,1.0);}
        for(const auto& a:history)freed0+=s.operators[a.op_id].partitions[a.partition_id].data_size;
        for(const auto& a:dynamic)freed1+=s.operators[a.op_id].partitions[a.partition_id].data_size;
        write_delta=static_cast<double>(freed1-freed0)/s.write_bandwidth;
        const bool pool_alt=immediate+pool_future+risk<0,flat_alt=immediate+flat_future+risk<0;
        c.base_alt+=base_alt;c.pool_alt+=pool_alt;c.flat_alt+=flat_alt;c.pool_changed+=pool_alt!=base_alt;c.flat_changed+=flat_alt!=base_alt;
        cpu_us+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;wall_us+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        std::cerr<<std::setprecision(17)<<"RR_PAIR {\"cb\":"<<c.callbacks<<",\"q\":"<<last_q_<<",\"I\":"<<immediate<<",\"risk\":"<<risk<<",\"F\":["<<base_future<<','<<pool_future<<','<<flat_future<<"],\"choose\":["<<base_alt<<','<<pool_alt<<','<<flat_alt<<"],\"freed\":["<<freed0<<','<<freed1<<"],\"write_delta\":"<<write_delta<<",\"sign\":[";
        bool first=true;for(int i=0;i<n_;++i)if(sign[i]){if(!first)std::cerr<<',';first=false;std::cerr<<'['<<i<<','<<sign[i]<<']';}std::cerr<<"]}\n";
    }
    void print_stats() {
        sync();std::cerr<<std::setprecision(17)<<"RR_STATS {\"sizeof_estimator\":"<<sizeof(ReturnRiskV1)<<",\"q\":"<<last_q_<<",\"pending\":"<<pending_id_<<",\"cpu_us\":"<<cpu_us<<",\"wall_us\":"<<wall_us<<",\"sum_h_min\":"<<(c.pairs?sum_h_min:0)<<",\"sum_h_max\":"<<sum_h_max;
#define RR_COUNT(name) std::cerr<<",\"" #name "\":"<<c.name
        RR_COUNT(callbacks);RR_COUNT(epochs);RR_COUNT(mixed);RR_COUNT(intervals);RR_COUNT(known_positions);RR_COUNT(unknown_positions);RR_COUNT(known_hits);RR_COUNT(known_misses);RR_COUNT(duplicates);RR_COUNT(unknown_events);RR_COUNT(unknown_trials);RR_COUNT(fast_intervals);RR_COUNT(pressure);RR_COUNT(checks);RR_COUNT(pairs);RR_COUNT(pool_changed);RR_COUNT(flat_changed);RR_COUNT(base_alt);RR_COUNT(pool_alt);RR_COUNT(flat_alt);
#undef RR_COUNT
        std::cerr<<",\"loss\":[";for(int model=0;model<3;++model){if(model)std::cerr<<',';std::cerr<<'[';for(int op=0;op<k_;++op){if(op)std::cerr<<',';auto& x=loss[model][op];std::cerr<<"{\"event\":"<<x.event<<",\"nonevent\":"<<x.nonevent<<",\"events\":"<<x.events<<",\"nonevents\":"<<x.nonevents<<",\"event_inf\":"<<x.event_inf<<",\"nonevent_inf\":"<<x.nonevent_inf<<",\"clipped_trials\":"<<x.clipped_trials<<'}';}std::cerr<<']';}
        std::cerr<<"],\"real\":[";for(int op=0;op<k_;++op){if(op)std::cerr<<',';const auto& a=real[op];std::cerr<<"{\"starts\":"<<a.starts<<",\"initial\":"<<a.initial<<",\"demand\":"<<a.demand<<",\"known_demand\":"<<a.known_demand<<",\"unknown_demand\":"<<a.unknown_demand<<",\"prefetch\":"<<a.prefetch<<",\"prefetch_confirmed\":"<<a.prefetch_confirmed<<",\"other_load\":"<<a.other_load<<",\"own_returns\":"<<a.own_returns<<",\"own_wait_sum\":"<<a.own_wait_sum<<",\"own_wait_max\":"<<a.own_wait_max<<",\"disk_exposure_closed\":"<<a.disk_exposure_closed<<",\"disk_exposure_open\":"<<ongoingExposure(op)<<",\"own_censored_count\":"<<censoredOwnCount(op)<<",\"own_censored_age\":"<<censoredOwnAge(op)<<",\"spill_bytes\":"<<a.spill_bytes<<",\"read_bytes\":"<<a.read_bytes<<'}';}std::cerr<<"]}\n";
    }
};
static_assert(sizeof(ReturnRiskV1)<=32768,"return risk fixed state budget");
