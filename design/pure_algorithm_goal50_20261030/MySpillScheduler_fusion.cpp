// Evidence-gated predictor; skipped observations stay gaps, never fabricated transitions.
// Approximate-cycle pure policy fused with causal online transition prediction.
#define PREDICT_INTERVAL 0
#define PREDICT_SAMPLE_UPDATES 0
// Approximate-cycle pure policy with causal confidence and hysteresis.
// Exact public next-op co-service pure algorithm; not speculative forecasting.
// Visibility-weighted pure count rule; no trained model.
// Pure-rule derivative; baseline author Vanius0525; see generate_vanius.py.
// Submit this class (and standard-library includes) after the official declarations.
// No input access, engine changes, training, external data, or C++17 features.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
// V2: weak-link floor, aggregate cycle evidence, independent phase validation.
// Bounded-memory dominant-successor cycle tracking. No input/future access.
#include <algorithm>
#include <cstdint>
#include <vector>

class ApproxCycleTracker {
    struct Edge {int first=-1,second=-1,a=0,b=0,total=0;};
    std::vector<Edge> edges_;
    std::vector<int> rank_,cycle_;
    std::vector<int64_t> seen_;
    int purity_,support_,last_=-1,anchor_=-1,quality_=768,checks_=0,outside_=0,qualified_=0;
    int64_t last_tick_=-1,anchor_tick_=-1;
    uint64_t direct_=0,built_at_=0,profiles_=0,conflicts_=0;
    bool locked_=false;
    void edge(int from,int to) {
        auto& e=edges_[from];
        auto qualified=[&](){return e.first>=0&&e.a>=support_&&100*e.a>=40*e.total;};
        bool before=qualified();
        if(e.total>=64){e.total=(e.total+1)/2;e.a/=2;e.b/=2;}
        ++e.total;
        if(e.first==to)++e.a;
        else if(e.second==to)++e.b;
        else if(e.a==0){e.first=to;e.a=1;}
        else if(e.b==0){e.second=to;e.b=1;}
        else{--e.a;--e.b;}
        if(e.b>e.a){std::swap(e.first,e.second);std::swap(e.a,e.b);}
        qualified_+=int(qualified())-int(before);
        ++direct_;
    }
public:
    explicit ApproxCycleTracker(int purity=80,int support=6):purity_(purity),support_(support){}
    void reset(int n) {
        edges_.assign(n,Edge{});rank_.assign(n,-1);seen_.assign(n,-1);cycle_.clear();
        last_=anchor_=-1;last_tick_=anchor_tick_=-1;quality_=768;checks_=outside_=0;
        direct_=built_at_=profiles_=conflicts_=0;qualified_=0;locked_=false;
    }
    void reveal(int id,int64_t tick) {
        if(id<0||id>=int(edges_.size()))return;
        if(tick<=last_tick_){if(tick==last_tick_&&last_!=id)++conflicts_;return;}
        if(!cycle_.empty()){
            const int len=int(cycle_.size());
            int score=512;
            if(rank_[id]<0){score=0;++outside_;}
            else{
                outside_=0;
                if(anchor_>=0 && anchor_tick_>=0){
                    int64_t gap=tick-anchor_tick_;
                    int expected=(rank_[anchor_]+int(gap%len))%len;
                    score=rank_[id]==expected?1024:0;
                }
                anchor_=id;anchor_tick_=tick;
            }
            // Score the frozen order before incorporating the new edge.
            quality_=(31*quality_+score)/32;++checks_;
            if(locked_ && (quality_<563||outside_>=8))locked_=false;
            int warm=std::max(8,std::min(64,2*len));
            if(!locked_&&checks_>=warm&&quality_>=768&&outside_<4)locked_=true;
        }
        if(last_>=0&&tick==last_tick_+1)edge(last_,id);
        seen_[id]=tick;last_=id;last_tick_=tick;
    }
    void rebuild(const SystemState& s) {
        if(qualified_<4||direct_<uint64_t(4*support_)||direct_-built_at_<16)return;
        built_at_=direct_;const int n=int(edges_.size());
        std::vector<unsigned char> eligible(n,0),state(n,0);
        for(const auto& o:s.operators)for(const auto& p:o.partitions){
            int id=o.op_id*s.num_partitions+p.partition_id;const auto& e=edges_[id];
            eligible[id]=o.phase==Phase::PROBE && p.data_size>0 && e.first>=0 &&
                e.a>=support_ && 100*e.a>=40*e.total;
        }
        std::vector<int> position(n,-1),path,best;int best_score=-1;
        for(int start=0;start<n;++start){
            if(!eligible[start]||state[start])continue;
            path.clear();int at=start;
            while(at>=0&&at<n&&eligible[at]&&!state[at]){
                state[at]=1;position[at]=int(path.size());path.push_back(at);at=edges_[at].first;
            }
            if(at>=0&&at<n&&position[at]>=0){
                int begin=position[at],len=int(path.size())-begin;
                if(len>=4){
                    int recent=0,total_votes=0,winner_votes=0;bool contains_last=false;
                    for(int j=begin;j<int(path.size());++j){int id=path[j];
                        total_votes+=edges_[id].total;winner_votes+=edges_[id].a;
                        recent+=seen_[id]>=0&&last_tick_-seen_[id]<=std::max(128,8*len);
                        contains_last=contains_last||id==last_;}
                    int score=len*(contains_last?5:1);
                    if(recent>=std::max(2,len/2)&&100*winner_votes>=purity_*total_votes&&score>best_score){best_score=score;best.assign(path.begin()+begin,path.end());}
                }
            }
            for(int id:path){position[id]=-1;state[id]=2;}
        }
        if(best.empty())return; // A transient dip does not erase a frozen profile.
        bool same=best.size()==cycle_.size();
        if(same)for(int i=0;i<int(best.size());++i){int id=best[i],next=best[(i+1)%best.size()];
            if(rank_[id]<0||cycle_[(rank_[id]+1)%cycle_.size()]!=next){same=false;break;}}
        if(same)return;
        cycle_=best;rank_.assign(n,-1);for(int i=0;i<int(cycle_.size());++i)rank_[cycle_[i]]=i;
        quality_=768;checks_=outside_=0;locked_=false;++profiles_;anchor_=-1;anchor_tick_=-1;
        for(int id:cycle_)if(seen_[id]>anchor_tick_){anchor_=id;anchor_tick_=seen_[id];}
    }
    bool active(int64_t now) const {
        return locked_&&anchor_>=0&&now>=anchor_tick_&&
            now-anchor_tick_<=std::max<int64_t>(64,4*int64_t(cycle_.size()));
    }
    int distance(int id,int64_t now) const {
        if(!active(now)||id<0||id>=int(rank_.size())||rank_[id]<0)return -1;
        int len=int(cycle_.size()),d=(rank_[id]-rank_[anchor_]+len)%len;
        return d==0?len:d;
    }
    double confidence(int64_t now) const {return active(now)?quality_/1024.0:0.0;}
    bool hasPredictiveEvidence() const{return qualified_>0;}
    int length() const{return int(cycle_.size());}
    uint64_t directEdges() const{return direct_;}
    uint64_t profiles() const{return profiles_;}
    uint64_t conflicts() const{return conflicts_;}
};

// Online first-order demand model. Input is ONLY revealed probe identities.
// An exact next_op is an observation; prediction starts AFTER that anchor.
#include <array>
#include <cstdint>
#include <algorithm>

// 0 preserves the original live lookup. Positive values refresh a frozen
// forecast every K completed probes (Hit+Miss), never per callback count.
#ifndef PREDICT_INTERVAL
#define PREDICT_INTERVAL 0
#endif
#ifndef PREDICT_SAMPLE_UPDATES
#define PREDICT_SAMPLE_UPDATES 0
#endif
static_assert(PREDICT_INTERVAL>=0,"Prediction interval must be non-negative");

class OnlineDemandPredictor {
    static constexpr int Q=512;
    struct Row {
        std::array<uint16_t,Q> counts{};
        uint32_t total=0;
        int best=0;
    };
    std::array<Row,Q> rows_{};
    int last_id_=-1,anchor_=-1;
    uint64_t last_tick_=0;
    uint64_t observations_=0,consecutive_=0,evaluations_=0,correct_=0,gaps_=0;
    uint64_t duplicates_=0,conflicts_=0,active_contexts_=0;
    double reliability_=0;
    std::array<double,Q> cached_protection_{};
    int cached_anchor_=-1,cached_best_=-1;
    uint64_t clock_=0,refresh_tick_=0;
    bool refreshed_=false,cache_usable_=false;
    uint64_t prepare_calls_=0,refreshes_=0,reused_=0,context_misses_=0;
    uint64_t scheduled_evaluations_=0,scheduled_correct_=0;
    uint64_t update_skips_=0;

    void add(int from,int to) {
        Row& r=rows_[from];
        if(r.total>=4096) {
            r.total=0;r.best=0;
            for(int i=0;i<Q;++i){r.counts[i]>>=1;r.total+=r.counts[i];
                if(r.counts[i]>r.counts[r.best])r.best=i;}
        }
        ++r.counts[to];++r.total;
        if(r.counts[to]>r.counts[r.best])r.best=to;
    }
public:
    void reveal(int id,uint64_t tick) {
        if(id<0||id>=Q)return;
        if(last_id_>=0 && tick<=last_tick_) {
            ++duplicates_;
            if(tick==last_tick_ && id!=last_id_)++conflicts_;
            return;
        }
        ++observations_;
        if(last_id_>=0 && tick==last_tick_+1) {
            ++consecutive_;
            if(PREDICT_INTERVAL>0 && cache_usable_ && last_id_==cached_anchor_ &&
               clock_>=refresh_tick_ && clock_-refresh_tick_<=uint64_t(PREDICT_INTERVAL)) {
                ++scheduled_evaluations_;if(cached_best_==id)++scheduled_correct_;
            }
            // Score BEFORE training on this transition. Only observable,
            // consecutive demands are scored, never all hidden input probes.
            const Row& r=rows_[last_id_];
            if(r.total>=8 && 2*r.counts[r.best]>=r.total) {
                ++evaluations_;if(r.best==id)++correct_;
            }
            add(last_id_,id);
        } else if(last_id_>=0)++gaps_;
        last_id_=id;last_tick_=tick;
    }
    void prepare(const SystemState& s,int current_o=-1,int current_p=-1) {
        uint64_t t=uint64_t(s.hit_count+s.miss_count);
        clock_=t;++prepare_calls_;
        if(PREDICT_SAMPLE_UPDATES && PREDICT_INTERVAL>0 && refreshed_ &&
           t>=refresh_tick_ && t-refresh_tick_<uint64_t(PREDICT_INTERVAL)) {
            // Optional whole-module sampling: missing observations are never
            // invented later. reveal() will skip the gap on the next refresh.
            if(s.next_op.type=="PROBE")
                anchor_=s.next_op.op_id*s.num_partitions+int(s.next_op.key%s.num_partitions);
            else anchor_=current_o>=0?current_o*s.num_partitions+current_p:-1;
            ++update_skips_;
            if(cache_usable_&&anchor_==cached_anchor_)++reused_;
            else ++context_misses_;
            return;
        }
        if(current_o>=0)reveal(current_o*s.num_partitions+current_p,t);
        if(s.next_op.type=="PROBE") {
            const int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            reveal(o*s.num_partitions+p,t+1);
        }
        // A stale observed event across an unobserved gap is not an anchor.
        anchor_=(last_id_>=0&&(last_tick_==t||last_tick_==t+1))?last_id_:-1;
        if(PREDICT_INTERVAL>0 && refreshed_ && t>=refresh_tick_ &&
           t-refresh_tick_<uint64_t(PREDICT_INTERVAL)) {
            if(cache_usable_&&anchor_==cached_anchor_)++reused_;
            else ++context_misses_;
            return;
        }
        ++refreshes_;
        if(PREDICT_INTERVAL>0) {
            refresh_tick_=t;refreshed_=true;cache_usable_=false;
            cached_anchor_=anchor_;cached_best_=-1;
        }
        reliability_=0;
        if(anchor_>=0 && evaluations_>=8) {
            const Row& r=rows_[anchor_];
            const double accuracy=double(correct_+1)/double(evaluations_+2);
            if(r.total>=8 && 2*r.counts[r.best]>=r.total && accuracy>.5) {
                reliability_=std::min(1.0,double(r.total)/32.0)*(2*accuracy-1);
                ++active_contexts_;
            }
        }
        if(PREDICT_INTERVAL>0 && reliability_>0) {
            const Row& r=rows_[anchor_];
            // Freeze probabilities too: counts continue learning between
            // refreshes, but must not silently change the cached forecast.
            const int count=int(s.operators.size())*s.num_partitions;
            for(int i=0;i<std::min(count,Q);++i)
                cached_protection_[i]=reliability_*double(r.counts[i])/double(r.total);
            cached_best_=r.best;cache_usable_=true;
        }
    }
    double protection(int id) const {
        if(PREDICT_INTERVAL>0) {
            if(!cache_usable_||anchor_!=cached_anchor_||id<0||id>=Q||
               clock_<refresh_tick_||clock_-refresh_tick_>=uint64_t(PREDICT_INTERVAL))return 0;
            return cached_protection_[id];
        }
        if(anchor_<0||reliability_<=0||id<0||id>=Q)return 0;
        const Row& r=rows_[anchor_];
        return reliability_*double(r.counts[id])/double(r.total);
    }
    uint64_t observations()const{return observations_;}
    uint64_t consecutive()const{return consecutive_;}
    uint64_t evaluations()const{return evaluations_;}
    uint64_t correct()const{return correct_;}
    uint64_t gaps()const{return gaps_;}
    uint64_t duplicates()const{return duplicates_;}
    uint64_t conflicts()const{return conflicts_;}
    uint64_t activeContexts()const{return active_contexts_;}
    uint64_t prepareCalls()const{return prepare_calls_;}
    uint64_t refreshes()const{return refreshes_;}
    uint64_t reused()const{return reused_;}
    uint64_t contextMisses()const{return context_misses_;}
    uint64_t scheduledEvaluations()const{return scheduled_evaluations_;}
    uint64_t scheduledCorrect()const{return scheduled_correct_;}
    uint64_t updateSkips()const{return update_skips_;}
};

class MySpillScheduler : public SpillScheduler {
    OnlineDemandPredictor predictor_;
    uint64_t fusion_protection_uses_=0;
    bool fusion_prepared_=false;
    double fusionProtection(const SystemState& s,int o,int p,int current_o,int current_p) {
        if(current_o<0 || s.operators[current_o].phase!=Phase::PROBE ||
           s.operators[o].phase!=Phase::PROBE)return 0;
        if(!fusion_prepared_)return 0;
        const double estimate=predictor_.protection(o*s.num_partitions+p);
        if(estimate<=0)return 0;
        if(true && near_.active(s.hit_count+s.miss_count+1))return 0;
        if(true){
            if(s.next_op.type!="PROBE")return 0;
            const int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);
            if((o==current_o&&p==current_p)||(o==no&&p==np))return 0;
            int64_t reserved=s.operators[current_o].partitions[current_p].data_size;
            if(no!=current_o||np!=current_p)reserved+=s.operators[no].partitions[np].data_size;
            if(reserved>s.memory_limit || s.operators[o].partitions[p].data_size>s.memory_limit-reserved)return 0;
        }
        if(1>0)++fusion_protection_uses_;
        return estimate;
    }

    ApproxCycleTracker near_{60,6};
    struct History { int64_t last = -1; double count = 0; double sample = 0; };
    struct Victim { int op, pid; int64_t bytes; double priority; };
    std::vector<History> history_;
    std::vector<Victim> victims_;
    std::vector<int> step_distance_;
    std::vector<int> successor_, confidence_, recent_;
    int64_t sample_q_=-1,sample_seen_=0; double sample_total_=0;
    std::vector<double> weighted_;
    double weighted_total_=0;
    int64_t weight_tick_=-1,decay_tick_=0,period_tick_=-1,period_estimate_=0,hit_samples_=0;
    void recordWeight(int id,int64_t q,double mass) {
        if(q<=weight_tick_)return;
        if(q-decay_tick_>=8192){
            int64_t shifts=(q-decay_tick_)/8192;
            double factor=std::ldexp(1.0,-int(std::min<int64_t>(64,shifts)));
            for(auto& w:weighted_)w*=factor;
            weighted_total_*=factor;decay_tick_+=shifts*8192;
        }
        weighted_[id]+=mass;weighted_total_+=mass;weight_tick_=q;
    }
    int recent_head_=0, recent_count_=0;
    int64_t graph_version_=0, analyzed_version_=-1;
    bool uniform_cycle_=false;
    int confirmed_edges_=0;
    bool active_ = false;
    int p_ = 0, cached_stride_ = -1;
    int64_t observed_q_ = -1, observed_count_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;
    void observe(int op, int pid, int64_t q) {
        if (q <= observed_q_) return;
        const int current_id=op*p_+pid;
        near_.reveal(current_id,q);
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
    void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false) {
        fusion_prepared_=near_.hasPredictiveEvidence();
        if(fusion_prepared_)predictor_.prepare(s,op,pid);
        const int n = static_cast<int>(s.operators.size()) * s.num_partitions;
        if (p_ != s.num_partitions || static_cast<int>(history_.size()) != n) {
            p_ = s.num_partitions; history_.assign(n, History{});
            near_.reset(n);
            weighted_.assign(n,0);weighted_total_=0;weight_tick_=-1;decay_tick_=0;period_tick_=-1;period_estimate_=0;hit_samples_=0;
            successor_.assign(n,-1);confidence_.assign(n,0);recent_.assign(n+2,-1);
            recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;confirmed_edges_=0;
            observed_q_ = -1; observed_count_ = 0;
            last_op_ = last_pid_ = stride_ = cached_stride_ = -1; streak_ = 0;
        }
        const int64_t q = s.hit_count + s.miss_count;
        if(op>=0)recordWeight(op*p_+pid,q,1.0);
        if(periodic){
            bool all_probe=true;for(const auto& x:s.operators)all_probe=all_probe&&x.phase==Phase::PROBE;
            if(all_probe){
                if(period_tick_>=0 && q>period_tick_){
                    int64_t delta=q-period_tick_;
                    period_estimate_=period_estimate_>0?std::min(period_estimate_,delta):delta;
                }
                period_tick_=q;
            }else period_tick_=-1;
            if(s.next_op.type=="PROBE"){
                int no=s.next_op.op_id,np=int(s.next_op.key%p_);
                if(s.operators[no].phase==Phase::PROBE && s.operators[no].partitions[np].in_memory){
                    double mass=double(std::max<int64_t>(1,period_estimate_));
                    
                    if(q+1>weight_tick_)++hit_samples_;
                    recordWeight(no*p_+np,q+1,mass);
                }
            }
        }

        // A miss and its periodic callback may expose the same pending request.
        // Probe ordinals deduplicate those, while preserving real repeated keys.
        if (op >= 0) observe(op, pid, q);
        if (s.next_op.type == "PROBE" && s.next_op.op_id >= 0 &&
            s.next_op.op_id < static_cast<int>(s.operators.size()))
            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);
    }
    void sample(const SystemState& s) {
        if(s.next_op.type!="PROBE")return;
        int64_t q=s.hit_count+s.miss_count+1;if(q<=sample_q_)return;
        int id=s.next_op.op_id*p_+int(s.next_op.key%p_);
        if(id<0||id>=int(history_.size()))return;
        ++history_[id].sample;++sample_total_;++sample_seen_;sample_q_=q;
        if(sample_seen_%512==0){for(auto& h:history_)h.sample*=.5;sample_total_*=.5;}
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
    void release(const SystemState& s, int op, int pid, int64_t required,
                 std::vector<Action>& actions) {
        const int64_t free_bytes = s.memory_limit - s.memory_used;
        if (required <= free_bytes) return;
        const int64_t need = required - free_bytes;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE") {
            next_op = s.next_op.op_id; next_pid = static_cast<int>(s.next_op.key % p_);
        }
        analyzeCycle(s);
        near_.rebuild(s);
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
            if(evidence && sample_seen_>=16) {
                double count_reuse=std::min(4.0,64.0*(h.sample+.1)/(sample_total_+.1*history_.size()));
                if(hit_samples_>=16 && weighted_total_>0) {
                    double corrected=std::min(4.0,double(history_.size())*(weighted_[o.op_id*p_+part.partition_id]+.1)/(weighted_total_+.1*history_.size()));
                    count_reuse=corrected;
                }
                reuse=.5*reuse+.5*count_reuse;
            }
            if (evidence && scan && o.op_id == op && o.op_id == last_op_) {
                const int delta = (part.partition_id - last_pid_ + p_) % p_;
                reuse = 1.0 - static_cast<double>(step_distance_[delta]) / p_;
            }
            int cycle_distance=near_.distance(o.op_id*p_+part.partition_id,now);
            if(cycle_distance>=0){
                double blend=1.0*near_.confidence(now);
                double cyclic=1.0*double(near_.length()-cycle_distance)/near_.length();
                reuse=(1.0-blend)*reuse+blend*cyclic;
            }
            reuse+=1*fusionProtection(s,o.op_id,part.partition_id,op,pid)*std::max(0.0,1.0-reuse);
            // The true penalty is absent from SystemState. Only its documented
            // lower bound (1 microsecond) is used in this cost-density heuristic.
            double priority = reuse * (1.0 / s.read_bandwidth +
                1.0 / s.write_bandwidth + 1.0 / part.data_size);
            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;
            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});
        }
        auto better = [](const Victim& a, const Victim& b) {
            if (a.priority != b.priority) return a.priority < b.priority;
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
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a); pruneSpills(s,z,a); return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        active_=true;update(s,op,pid);std::vector<Action>a;
        const int64_t current=s.operators[op].partitions[pid].data_size;
        release(s,op,pid,current,a);pruneSpills(s,current,a);
        auto written=[&](const std::vector<Action>& x){int64_t z=0;for(const auto& t:x)
            if(t.type==Action::SPILL)z+=s.operators[t.op_id].partitions[t.partition_id].data_size;return z;};
        if(s.next_op.type=="PROBE"){
            int no=s.next_op.op_id,np=int(s.next_op.key%p_);
            const auto& next=s.operators[no].partitions[np];
            if(s.operators[no].phase==Phase::PROBE && !next.in_memory && (no!=op||np!=pid) && current+next.data_size<=s.memory_limit){
                int64_t old_write=written(a);
                if(3>=2 && s.memory_limit-s.memory_used+old_write<current+next.data_size){
                    std::vector<Action>joint;release(s,op,pid,current+next.data_size,joint);pruneSpills(s,current+next.data_size,joint);
                    int64_t new_write=written(joint);
                    double extra=double(new_write-old_write)/s.write_bandwidth;
                    if(extra<=.25*double(next.data_size)/s.read_bandwidth)a=joint;
                }
                if(s.memory_limit-s.memory_used+written(a)>=current+next.data_size){
                    recordWeight(no*p_+np,s.hit_count+s.miss_count+1,1.0);
                    a.emplace_back(Action::LOAD,no,np);
                }
            }
        }
        a.emplace_back(Action::LOAD,op,pid);return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> a;
        if (!active_) return a;
        update(s,-1,-1,true); sample(s);
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
        recordWeight(op*p_+pid,s.hit_count+s.miss_count+1,1.0);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
};
