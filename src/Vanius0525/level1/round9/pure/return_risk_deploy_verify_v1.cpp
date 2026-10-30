#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
// Decision-only return-risk kernel; all clocks use legal aggregate PROBE counts.
class RiskCore {
public:
    static constexpr int MAX_N=512,MAX_K=8;
    std::array<double,MAX_N> d{},z{};
private:
    std::array<bool,MAX_N> resident{};
    int n_=0,p_=0,live_id_=-1,checkpoint_=0;
    int64_t last_q_=0,live_q_=-1,stat_q_=0,next_checkpoint_=64;
    bool active_=false,committed_=false,ever_unknown_=false;
    const double loga_=std::log(0.5)/2048.0;
    void advance(int64_t q) {
        if(q==stat_q_)return;
        if(ever_unknown_) {
            const double a=std::exp(loga_*static_cast<double>(q-stat_q_));
            for(int i=0;i<n_;++i){d[i]*=a;z[i]*=a;}
        }
        stat_q_=q;
    }
public:
    bool active()const{return active_;}
    int size()const{return n_;}
    int64_t q()const{return last_q_;}
    void sync(){if(active_)advance(last_q_);}
    template<class P> void before(const SystemState& s,char tag,int miss_id,P probability) {
        bool all=true;for(const auto& op:s.operators)all=all&&op.phase==Phase::PROBE;
        if(!all){active_=committed_=false;return;}
        const int64_t qnow=s.hit_count+s.miss_count;
        if(!active_) {
            active_=true;committed_=false;ever_unknown_=false;
            p_=s.num_partitions;n_=s.operators.size()*p_;
            d.fill(0);z.fill(0);live_id_=-1;live_q_=-1;stat_q_=qnow;
            for(const auto& op:s.operators)for(const auto& pa:op.partitions)
                resident[op.op_id*p_+pa.partition_id]=pa.in_memory;
        }
        if(committed_) {
            const int64_t len=qnow-last_q_;
            const bool known=live_id_>=0 && live_q_>last_q_ && live_q_<=qnow;
            const int64_t known_q=live_q_;
            const int64_t unknown=len-static_cast<int>(known);
            const bool event=tag=='M' && !(known&&known_q==qnow);
            if(unknown>0) {
                advance(last_q_);
                const double decay=std::exp(loga_*static_cast<double>(len));
                double weight=-std::expm1(loga_*static_cast<double>(len))/(-std::expm1(loga_));
                if(known)weight-=std::exp(loga_*static_cast<double>(qnow-known_q));
                for(int i=0;i<n_;++i) {
                    d[i]*=decay;z[i]*=decay;
                    if(!resident[i]) {
                        z[i]+=probability(i)*weight;
                        if(event&&i==miss_id)d[i]+=1;
                    }
                }
                stat_q_=qnow;ever_unknown_=true;
            }
            if(known){live_id_=-1;live_q_=-1;}
        }
        int next=-1;
        if(s.next_op.type=="PROBE")next=s.next_op.op_id*p_+s.next_op.key%p_;
        if(next>=0 && live_id_<0){live_id_=next;live_q_=qnow+1;}
        last_q_=qnow;
    }
    void after(const SystemState&,const std::vector<Action>& actions) {
        if(!active_)return;
        for(const auto& a:actions)
            resident[a.op_id*p_+a.partition_id]=a.type==Action::LOAD;
        committed_=true;
        // Preserve the original legal sparse sync cadence, without diagnostics.
        if(last_q_>=next_checkpoint_) {
            sync();const int thresholds[4]={64,256,1024,4096};++checkpoint_;
            next_checkpoint_=checkpoint_<4?thresholds[checkpoint_]:((last_q_/65536)+1)*65536;
        }
    }
    template<class P> double future(const SystemState& s,const std::vector<int>& sign,
                                     double base_future,P probability,int mode) {
        if(!ever_unknown_)return base_future;
        advance(s.hit_count+s.miss_count);
        std::array<double,MAX_K> gd{},gz{};
        double all_d=0,all_z=0;
        if(mode==0)for(int i=0;i<n_;++i){gd[i/p_]+=d[i];gz[i/p_]+=z[i];}
        if(mode==2)for(int i=0;i<n_;++i){all_d+=d[i];all_z+=z[i];}
        const double global=(1.0+all_d)/(1.0+all_z);
        double value=0;
        for(int i=0;i<n_;++i)if(sign[i]) {
            const double p=probability(i);double h;
            if(mode==0) {
                const double rg=(1.0+std::max(0.0,gd[i/p_]-d[i]))/(1.0+std::max(0.0,gz[i/p_]-z[i]));
                h=std::min(1.0,p*(rg+d[i])/(1.0+z[i]));
            }else if(mode==1)h=std::min(1.0,p*(1.0+d[i])/(1.0+z[i]));
            else h=std::min(1.0,p*global);
            const double bytes=s.operators[i/p_].partitions[i%p_].data_size;
            const double coef=sign[i]*(bytes/s.read_bandwidth+bytes/s.write_bandwidth+100.0);
            value+=64.0*h*coef;
        }
        return value;
    }
};

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
    RiskCore* compact=nullptr;
    int64_t checked_states=0,checked_pairs=0,nonbit_coordinates=0;
    double dz_abs_max=0,dz_scaled_max=0,future_abs_max=0;
    void verify(const char*) {
        check(compact && compact->active()==active_,"compact activation");
        if(!active_)return;
        check(compact->size()==n_ && compact->q()==last_q_,"compact clock");
        ++checked_states;
        for(int i=0;i<n_;++i)for(int kind=0;kind<2;++kind) {
            const double a=kind?z[i]:d[i],b=kind?compact->z[i]:compact->d[i];
            const double delta=std::abs(a-b),scaled=delta/std::max(1.0,std::abs(a));
            nonbit_coordinates+=a!=b;dz_abs_max=std::max(dz_abs_max,delta);dz_scaled_max=std::max(dz_scaled_max,scaled);
            check(scaled<=2e-12,"compact D/Z mismatch");
        }
    }
    void print_deploy() {
        std::cerr<<std::setprecision(17)<<"DEPLOY_CHECK {\"states\":"<<checked_states<<",\"pairs\":"<<checked_pairs
                 <<",\"nonbit_coordinates\":"<<nonbit_coordinates<<",\"dz_abs_max\":"<<dz_abs_max
                 <<",\"dz_scaled_max\":"<<dz_scaled_max<<",\"future_abs_max\":"<<future_abs_max
                 <<",\"sizeof_compact\":"<<sizeof(RiskCore)<<"}\n";
    }

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

        const double compact_pool=compact->future(s,sign,base_future,probability,0);
        const double compact_flat=compact->future(s,sign,base_future,probability,1);
        const double compact_global=compact->future(s,sign,base_future,probability,2);
        const bool compact_global_alt=immediate+compact_global+risk<0;
        verify("pair");++checked_pairs;
        future_abs_max=std::max(future_abs_max,std::max(std::abs(compact_pool-pool_future),std::abs(compact_flat-flat_future)));
        check(std::abs(compact_pool-pool_future)<=2e-12*std::max(1.0,std::abs(pool_future)),"compact pooled future");
        check(std::abs(compact_flat-flat_future)<=2e-12*std::max(1.0,std::abs(flat_future)),"compact flat future");
        check((immediate+compact_pool+risk<0)==pool_alt && (immediate+compact_flat+risk<0)==flat_alt,"compact decision");
        std::cerr<<std::setprecision(17)<<"RR_GLOBAL {\"cb\":"<<c.callbacks<<",\"q\":"<<last_q_
                 <<",\"F\":"<<compact_global<<",\"choose\":"<<compact_global_alt<<"}\n";
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

// Round8 experimental paired-plan guard; generated by round8/pure/make_candidates.py.
// Submit this class (and standard-library includes) after the official declarations.
// No input access, engine changes, training, external data, or C++17 features.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
class ReferencePair : public SpillScheduler {
    ReturnRiskV1* diagnostic_=nullptr;
    static constexpr double penalty_proxy_us = 100.0;
    struct History { int64_t last = -1; double count = 0; };
    struct Victim { int op, pid; int64_t bytes; double priority, pool_priority; };
    std::vector<History> history_;
    std::vector<Victim> victims_;
    std::vector<int> step_distance_;
    std::vector<int> successor_, confidence_, recent_;
    int recent_head_=0, recent_count_=0;
    int64_t graph_version_=0, analyzed_version_=-1;
    bool uniform_cycle_=false;
    int confirmed_edges_=0;
    bool active_ = false;
    int p_ = 0, cached_stride_ = -1;
    int64_t observed_q_ = -1, observed_count_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;

    // Sources: periodic=1, after-miss-next=2. Current miss is deliberately excluded.
    std::vector<double> sample_count_;
    std::vector<int64_t> periodic_count_, after_miss_count_;
    double sample_total_=0, sample_squares_=0;
    std::vector<double> periodic_mass_;
    double periodic_total_=0,periodic_squares_=0;
    int64_t paired_checks_=0,paired_different_=0,paired_confident_=0,paired_source_veto_=0,paired_chosen_=0;
    int64_t sample_q_=-1, decay_q_=-1;
    int sample_sources_=0;
    std::vector<bool> core_;
    void sampleNext(const SystemState& s,int source) {
        if(s.next_op.type!="PROBE" || s.next_op.op_id<0 ||
           s.next_op.op_id>=static_cast<int>(s.operators.size()))return;
        const int id=s.next_op.op_id*p_+static_cast<int>(s.next_op.key%p_);
        const int64_t q=s.hit_count+s.miss_count+1;
        // Half-life 2048 PROBEs, amortized every >=256 clock steps.
        // Source counters remain raw diagnostics; only probability mass decays.
        if(decay_q_<0)decay_q_=q;
        if(q-decay_q_>=256) {
            const double decay=std::pow(0.5,static_cast<double>(q-decay_q_)/2048.0);
            for(auto& x:sample_count_)x*=decay;
            sample_total_*=decay;sample_squares_*=decay*decay;
            for(auto& x:periodic_mass_)x*=decay;
            periodic_total_*=decay;periodic_squares_*=decay*decay;decay_q_=q;
        }
        if(q!=sample_q_) {sample_q_=q;sample_sources_=0;}
        if(sample_sources_&source)return;
        if(source==1) {++periodic_count_[id];++periodic_mass_[id];++periodic_total_;++periodic_squares_;}
        else ++after_miss_count_[id];
        const bool accepted=true;
        const bool already=sample_sources_!=0;
        if(accepted && !already) {++sample_count_[id];++sample_total_;++sample_squares_;}
        sample_sources_|=source;
    }
    double probability(int id) const {
        return (sample_count_[id]+64.0/sample_count_.size())/(sample_total_+64.0);
    }
    void refreshCore(const SystemState& s) {
        struct Item {int id;int64_t size;double density;};
        std::vector<Item> items;std::vector<int64_t> sizes;
        for(const auto& o:s.operators) for(const auto& x:o.partitions) {
            if(o.phase!=Phase::PROBE || x.data_size<=0)continue;
            int id=o.op_id*p_+x.partition_id;
            double d=probability(id)*(1.0/s.read_bandwidth+1.0/s.write_bandwidth+penalty_proxy_us/x.data_size);
            items.push_back({id,x.data_size,d*(core_[id]?1.1:1.0)});
            sizes.push_back(x.data_size);
        }
        if(sizes.empty())return;
        std::sort(sizes.begin(),sizes.end());
        // Upper median object size is a soft working-space proxy, not empty memory.
        int64_t budget=std::max<int64_t>(0,s.memory_limit-sizes[sizes.size()/2]);
        std::sort(items.begin(),items.end(),[](const Item& a,const Item& b){
            return a.density!=b.density?a.density>b.density:a.id<b.id;
        });
        std::fill(core_.begin(),core_.end(),false);
        for(const auto& x:items)if(x.size<=budget){core_[x.id]=true;budget-=x.size;}
    }
    void observe(int op, int pid, int64_t q) {
        if (q <= observed_q_) return;
        const int current_id=op*p_+pid;
        if (q==observed_q_+1 && last_op_>=0) {
            const int previous_id=last_op_*p_+last_pid_;
            if (successor_[previous_id]==current_id) {
                confidence_[previous_id]=std::min(7,confidence_[previous_id]+1);
                if (confidence_[previous_id]==3) {++graph_version_;++confirmed_edges_;}
             } else {
                if(confidence_[previous_id]>=3)--confirmed_edges_;
                successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;
            }
        }
        recent_[recent_head_]=current_id;
        recent_head_=(recent_head_+1)%static_cast<int>(recent_.size());
        recent_count_=std::min(recent_count_+1,static_cast<int>(recent_.size()));
        auto& h = history_[op * p_ + pid];
        if (h.last >= 0)
            h.count *= 256.0 / (256.0 + static_cast<double>(q - h.last));
        h.count += 1; h.last = q;
        if (q == observed_q_ + 1 && op == last_op_) {
            const int delta = (pid - last_pid_ + p_) % p_;
            if (delta != 0 && delta == stride_) ++streak_;
            else { stride_ = delta; streak_ = 1; }
        } else { stride_ = -1; streak_ = 0; }
        last_op_ = op; last_pid_ = pid;
        observed_q_ = q; ++observed_count_;
        if (streak_ >= 3 && stride_ > 0 && cached_stride_ != stride_) {
            step_distance_.assign(p_, p_);
            int at = 0;
            for (int j = 1; j <= p_; ++j) {
                at = (at + stride_) % p_;
                if (step_distance_[at] == p_) step_distance_[at] = j;
            }
            cached_stride_ = stride_;
        }
    }
    void update(const SystemState& s, int op = -1, int pid = -1) {
        const int n = static_cast<int>(s.operators.size()) * s.num_partitions;
        if (p_ != s.num_partitions || static_cast<int>(history_.size()) != n) {
            p_ = s.num_partitions; history_.assign(n, History{});
            sample_count_.assign(n,0);periodic_count_.assign(n,0);after_miss_count_.assign(n,0);
            core_.assign(n,false);periodic_mass_.assign(n,0);periodic_total_=periodic_squares_=sample_squares_=0;sample_total_=0;sample_q_=-1;decay_q_=-1;sample_sources_=0;
            successor_.assign(n,-1);confidence_.assign(n,0);recent_.assign(n+2,-1);
            recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;confirmed_edges_=0;
            observed_q_ = -1; observed_count_ = 0;
            last_op_ = last_pid_ = stride_ = cached_stride_ = -1; streak_ = 0;
        }
        const int64_t q = s.hit_count + s.miss_count;
        // A miss and its periodic callback may expose the same pending request.
        // Probe ordinals deduplicate those, while preserving real repeated keys.
        if (op >= 0) observe(op, pid, q);
        if (s.next_op.type == "PROBE" && s.next_op.op_id >= 0 &&
            s.next_op.op_id < static_cast<int>(s.operators.size()))
            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);
    }
    void analyzeCycle(const SystemState& s) {
        if (analyzed_version_==graph_version_) return;
        analyzed_version_=graph_version_;uniform_cycle_=false;
        if(confirmed_edges_!=static_cast<int>(history_.size()))return;
        if (last_op_<0) return;
        int64_t size=-1;
        for (const auto& o:s.operators) {
            if (o.phase!=Phase::PROBE) return;
            for (const auto& p:o.partitions) {
                if (p.data_size<=0) return;
                if (size<0) size=p.data_size;
                else if (size!=p.data_size) return;
            }
        }
        const int start=last_op_*p_+last_pid_,n=static_cast<int>(history_.size());
        int at=start;
        for (int j=1;j<=n;++j) {
            if (confidence_[at]<3 || successor_[at]<0) return;
            at=successor_[at];
            if (at==start) {uniform_cycle_=(j==n);return;}
        }
    }
    void propose(const SystemState& s, int op, int pid, int64_t required,
                 std::vector<Action>& actions,bool dynamic_pool) {
        const int64_t free_bytes = s.memory_limit - s.memory_used;
        if (required <= free_bytes) return;
        const int64_t need = required - free_bytes;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE") {
            next_op = s.next_op.op_id; next_pid = static_cast<int>(s.next_op.key % p_);
        }
        analyzeCycle(s);
        if (uniform_cycle_) {
            // Verified equal-size cyclic-route hypothesis. MRU keeps a stable
            // resident subset without scanning all KP states on each request.
            for (int j=0;j<recent_count_;++j) {
                int slot=(recent_head_-1-j+static_cast<int>(recent_.size()))%static_cast<int>(recent_.size());
                int id=recent_[slot],o=id/p_,pa=id%p_;
                if ((o==op && pa==pid) || (o==next_op && pa==next_pid)) continue;
                const auto& part=s.operators[o].partitions[pa];
                if (part.in_memory && part.data_size>=need) {
                    actions.emplace_back(Action::SPILL,o,pa);return;
                }
            }
        }
        const int64_t now = s.hit_count + s.miss_count + 1;
        const bool evidence = s.hit_count + s.miss_count > 0;
        const bool scan = streak_ >= 6 && stride_ > 0 &&
            observed_count_ * 2 > now;
        victims_.clear();
        for (const auto& o : s.operators) for (const auto& part : o.partitions) {
            if (!part.in_memory || part.data_size <= 0 ||
                (o.op_id == op && part.partition_id == pid)) continue;
            const auto& h = history_[o.op_id * p_ + part.partition_id];
            double reuse = 0;
            if (evidence && h.last >= 0) {
                const double age = static_cast<double>(std::max<int64_t>(0, now - h.last));
                reuse = std::min(1.0, h.count / 16.0) / (1.0 + (age + 1.0) / 64.0);
            }
            if (evidence && scan && o.op_id == op && o.op_id == last_op_) {
                const int delta = (part.partition_id - last_pid_ + p_) % p_;
                reuse = 1.0 - static_cast<double>(step_distance_[delta]) / p_;
            }
            double pool_priority=reuse*(1.0/s.read_bandwidth+1.0/s.write_bandwidth+penalty_proxy_us/part.data_size);
            if(o.op_id==next_op && part.partition_id==next_pid)pool_priority+=1e12;
            // A 64-request retention horizon fixes the scale against immediate write cost.
            // This is a proxy, not a claim of unbiased estimates for correlated requests.
            if(o.phase==Phase::PROBE && !scan) {
                reuse=64.0*probability(o.op_id*p_+part.partition_id);
            }
            // The true penalty is absent from SystemState. This fixed 100 us
            // proxy is a user-selected heuristic, not the scoring penalty.
            double priority = reuse * (1.0 / s.read_bandwidth +
                1.0 / s.write_bandwidth + penalty_proxy_us / part.data_size);
            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;
            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority, pool_priority});
        }
        auto better = [dynamic_pool](const Victim& a, const Victim& b) {
            const double ap=dynamic_pool?a.priority:a.pool_priority;
            const double bp=dynamic_pool?b.priority:b.pool_priority;
            if(ap!=bp)return ap<bp;
            return a.bytes > b.bytes;
        };
        if ((evidence || s.read_bandwidth>=s.write_bandwidth) && !victims_.empty()) {
            auto less=better;
            const int cap=std::min<int>(4,victims_.size());
            std::partial_sort(victims_.begin(),victims_.begin()+cap,victims_.end(),less);
            int best_mask=0;double best_loss=1e300;
            for(int mask=1;mask<(1<<cap);++mask) {
                int64_t bytes=0;double loss=0;
                for(int j=0;j<cap;++j) if(mask&(1<<j)) {
                    const auto& v=victims_[j];bytes+=v.bytes;
                    loss+=v.priority*v.bytes+0.25*static_cast<double>(v.bytes)/s.write_bandwidth;
                }
                if(bytes>=need && loss<best_loss) {best_mask=mask;best_loss=loss;}
            }
            if(best_mask) {
                for(int j=0;j<cap;++j) if(best_mask&(1<<j))
                    actions.emplace_back(Action::SPILL,victims_[j].op,victims_[j].pid);
                return;
            }
        }
        if (!evidence) {
            std::sort(victims_.begin(),victims_.end(),better);
            int64_t freed=0;
            for (const auto& v:victims_) {
                if (freed>=need) break;
                actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
            }
            return;
        }
        // The common one-victim path is linear. If multiple are needed, heapify
        // once: O(n + v log n), preserving the O(n log n) worst-case bound.
        auto first=std::min_element(victims_.begin(),victims_.end(),better);
        if (first!=victims_.end() && first->bytes>=need) {
            actions.emplace_back(Action::SPILL,first->op,first->pid);return;
        }
        auto worse = [&](const Victim& a,const Victim& b){return better(b,a);};
        std::make_heap(victims_.begin(),victims_.end(),worse);
        int64_t freed=0;
        while (freed<need && !victims_.empty()) {
            std::pop_heap(victims_.begin(),victims_.end(),worse);
            const auto v=victims_.back();victims_.pop_back();
            actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
        }
    }


    // Only these two already-established planners are compared. No wider top-k.
    void release(const SystemState& s,int op,int pid,int64_t required,
                 std::vector<Action>& actions) {
        propose(s,op,pid,required,actions,false);
        if(required<=s.memory_limit-s.memory_used)return;
        for(const auto& o:s.operators)if(o.phase!=Phase::PROBE)return;
        const int64_t now=s.hit_count+s.miss_count+1;
        const bool scan=streak_>=6 && stride_>0 && observed_count_*2>now;
        if(scan || uniform_cycle_)return;
        pruneSpills(s,required,actions);
        std::vector<Action> alternative;
        propose(s,op,pid,required,alternative,true);
        pruneSpills(s,required,alternative);
        ++paired_checks_; if(diagnostic_)++diagnostic_->c.checks;
        std::vector<int> sign(sample_count_.size(),0);
        for(const auto& x:actions)--sign[x.op_id*p_+x.partition_id];
        for(const auto& x:alternative)++sign[x.op_id*p_+x.partition_id];
        double immediate=0,mean=0,second=0,pmean=0,psecond=0;
        bool different=false;
        for(const auto& o:s.operators)for(const auto& part:o.partitions) {
            const int id=o.op_id*p_+part.partition_id;
            if(!sign[id])continue;
            different=true;
            const double size=static_cast<double>(part.data_size);
            const double coefficient=sign[id]*(size/s.read_bandwidth+size/s.write_bandwidth+penalty_proxy_us);
            immediate+=sign[id]*size/s.write_bandwidth;
            // Exact next request is additional known immediate read/miss exposure.
            if(s.next_op.type=="PROBE" && s.next_op.op_id==o.op_id &&
               s.next_op.key%p_==part.partition_id)
                immediate+=sign[id]*(size/s.read_bandwidth+penalty_proxy_us);
            const double prob=probability(id);
            mean+=prob*coefficient;second+=prob*coefficient*coefficient;
            const double pp=(periodic_mass_[id]+64.0/periodic_mass_.size())/(periodic_total_+64.0);
            pmean+=pp*coefficient;psecond+=pp*coefficient*coefficient;
        }
        if(!different)return;
        ++paired_different_;
        const double effective=sample_squares_>0?sample_total_*sample_total_/sample_squares_:0;
        const double sd=64.0*std::sqrt(std::max(0.0,second-mean*mean)/(effective+1.0));
        if(diagnostic_)diagnostic_->compare(s,actions,alternative,sign,immediate,64.0*mean,2.0*sd,[&](int i){return probability(i);});
        if(immediate+64.0*mean+2.0*sd>=0)return;
        ++paired_confident_;
        if(false) {
            const double pn=periodic_squares_>0?periodic_total_*periodic_total_/periodic_squares_:0;
            const double psd=64.0*std::sqrt(std::max(0.0,psecond-pmean*pmean)/(pn+1.0));
            if(immediate+64.0*pmean-2.0*psd>0){++paired_source_veto_;return;}
        }
        actions.swap(alternative);++paired_chosen_;
    }

    void pruneSpills(const SystemState& s, int64_t required, std::vector<Action>& a) {
        const int64_t need=required-(s.memory_limit-s.memory_used);
        int64_t freed=0;
        for (const auto& x:a) freed+=s.operators[x.op_id].partitions[x.partition_id].data_size;
        size_t keep=0;
        for (const auto& x:a) {
            const int64_t size=s.operators[x.op_id].partitions[x.partition_id].data_size;
            if (freed-size>=need) {freed-=size;continue;}
            a[keep++]=x;
        }
        a.erase(a.begin()+keep,a.end());
    }
public:
    void diagnosticHook(ReturnRiskV1* p){diagnostic_=p;}
    double diagnosticProbability(int id) const{return probability(id);}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a); pruneSpills(s,z,a); return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        active_ = true; update(s,op,pid); sampleNext(s,2); std::vector<Action> a;
        release(s,op,pid,s.operators[op].partitions[pid].data_size,a);
        pruneSpills(s,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> a;
        update(s); sampleNext(s,1);
        if (!active_) return a;
        if (s.next_op.type != "PROBE") return a;
        const int op=s.next_op.op_id;
        if (op < 0 || op >= static_cast<int>(s.operators.size())) return a;
        const int pid=static_cast<int>(s.next_op.key % p_);
        const auto& part=s.operators[op].partitions[pid];
        if (s.operators[op].phase != Phase::PROBE || part.in_memory ||
            part.data_size > s.memory_limit) return a;
        analyzeCycle(s);
        // Preserve the later miss callback's extra lookahead unless no eviction
        // is needed or the equal-size cyclic-route hypothesis supplies it.
        if (part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_) return a;
        release(s,op,pid,part.data_size,a); pruneSpills(s,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
};

class MySpillScheduler : public SpillScheduler {
    ReferencePair inner_;ReturnRiskV1 stats_;RiskCore core_;int checkpoint_=0;int64_t next_checkpoint_=64;
    void before(const SystemState& s,char tag,int id) {
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        stats_.before(s,tag,id,[&](int i){return inner_.diagnosticProbability(i);});core_.before(s,tag,id,[&](int i){return inner_.diagnosticProbability(i);});stats_.verify("before");
        stats_.cpu_us+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;stats_.wall_us+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
    }
    void after(const SystemState& s,char tag,int id,const std::vector<Action>& actions) {
        const auto start=std::chrono::steady_clock::now();const auto cpu=std::clock();
        stats_.after(s,tag,id,actions);core_.after(s,actions);
        stats_.cpu_us+=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;stats_.wall_us+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        if(stats_.active() && stats_.q()>=next_checkpoint_){snapshot();const int thresholds[4]={64,256,1024,4096};++checkpoint_;next_checkpoint_=checkpoint_<4?thresholds[checkpoint_]:((stats_.q()/65536)+1)*65536;}stats_.verify("after");
    }
    void snapshot() {
        stats_.sync();core_.sync();stats_.verify("snapshot");std::cerr<<std::setprecision(17)<<"RR_SNAPSHOT {\"cb\":"<<stats_.c.callbacks<<",\"q\":"<<stats_.q()<<",\"d\":[";
        for(int i=0;i<stats_.size();++i){if(i)std::cerr<<',';std::cerr<<stats_.d[i];}std::cerr<<"],\"z\":[";
        for(int i=0;i<stats_.size();++i){if(i)std::cerr<<',';std::cerr<<stats_.z[i];}std::cerr<<"],\"p\":[";
        for(int i=0;i<stats_.size();++i){if(i)std::cerr<<',';std::cerr<<inner_.diagnosticProbability(i);}std::cerr<<"]}\n";
    }
public:
    MySpillScheduler(){inner_.diagnosticHook(&stats_);stats_.compact=&core_;}
    ~MySpillScheduler(){if(stats_.active())snapshot();stats_.print_stats();stats_.print_deploy();}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t bytes) override {int id=op*s.num_partitions+pid;before(s,'O',id);auto a=inner_.onMemoryOverflow(s,op,pid,bytes);after(s,'O',id,a);return a;}
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {int id=op*s.num_partitions+pid;before(s,'M',id);auto a=inner_.onPartitionMiss(s,op,pid);after(s,'M',id,a);return a;}
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {before(s,'P',-1);auto a=inner_.onPeriodicAdjust(s);after(s,'P',-1,a);return a;}
};
