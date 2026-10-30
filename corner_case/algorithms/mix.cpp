// R9 pure online sampling experiment; baseline author Vanius0525.
#include <cmath>
#define R9_SAMPLE_MODE 4
// R7 deterministic pure-algorithm candidate; no fitted tree or input access.
#include <limits>
#define R7_EXACT 0
// Submit this class (and standard-library includes) after the official declarations.
// No input access, engine changes, training, external data, or C++17 features.
#include <algorithm>
#include <cstdint>
#include <vector>
class MySpillScheduler : public SpillScheduler {
    struct History { int64_t last = -1; double count = 0; };
    struct Victim { int op, pid; int64_t bytes; double priority; };
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

    // Separate frequency evidence from the miss-biased legacy observer. Under
    // IID keys within one operator a miss's successor is independent of that
    // miss; correlated streams and operator scheduling need not have this
    // property. This is a bounded online heuristic, not an unbiasedness claim.
    struct SampleFrequency { double mass=0; int64_t last_clock=-1; };
    std::vector<SampleFrequency> sampled_;
    std::vector<double> sampled_op_mass_;
    std::vector<int64_t> sampled_op_last_;
    double sampled_mass_=0;
    int64_t sampled_q_=-1,sampled_clock_=0;

    void frequencyObservation(int op,int pid,int64_t q,double weight) {
        if(weight<=0 || q<=sampled_q_)return;
        if(op<0 || op>=static_cast<int>(sampled_op_mass_.size()) || pid<0 || pid>=p_)return;
        const int id=op*p_+pid;
        sampled_q_=q;++sampled_clock_;
        sampled_[id].mass+=weight;sampled_[id].last_clock=sampled_clock_;
        sampled_op_mass_[op]+=weight;sampled_op_last_[op]=q;
        sampled_mass_+=weight;
        // Event-clock aging avoids treating unobserved cache hits as evidence
        // that a resident partition is cold. The window is fixed before tests.
        if(sampled_clock_%512==0) {
            for(auto& item:sampled_)item.mass*=0.5;
            for(auto& mass:sampled_op_mass_)mass*=0.5;
            sampled_mass_*=0.5;
        }
    }

    void frequencyUpdate(const SystemState& s,int op,int pid) {
        const int64_t q=s.hit_count+s.miss_count;
        if(R9_SAMPLE_MODE==3 && op>=0)frequencyObservation(op,pid,q,0.25);
        if(s.next_op.type=="PROBE" && s.next_op.op_id>=0 &&
            s.next_op.op_id<static_cast<int>(s.operators.size()))
            frequencyObservation(s.next_op.op_id,static_cast<int>(s.next_op.key%p_),q+1,1.0);
    }

    double frequencyReuse(const SystemState& s,int op,int pid,double legacy) const {
        const auto& sample=sampled_[op*p_+pid];
        const double prior=0.1;
        const double probability=(sample.mass+prior)/(sampled_mass_+prior*sampled_.size());
        double reuse=std::min(1.0,16.0*probability);
        if(R9_SAMPLE_MODE==1) {
            const int64_t age=sample.last_clock<0?sampled_clock_+1:sampled_clock_-sample.last_clock;
            reuse/=1.0+static_cast<double>(std::max<int64_t>(0,age))/64.0;
        } else if(R9_SAMPLE_MODE==2) {
            reuse=1.0-std::exp(-64.0*probability);
        } else if(R9_SAMPLE_MODE==4) {
            const double confidence=sampled_mass_/(sampled_mass_+sampled_.size());
            reuse=confidence*reuse+(1.0-confidence)*legacy;
        } else if(R9_SAMPLE_MODE==5) {
            // Condition on the owner, then discount operators not observed
            // recently. Miss-heavy operators do not automatically receive
            // more cache merely because their callbacks are more frequent.
            const double conditional=(sample.mass+prior)/(sampled_op_mass_[op]+prior*p_);
            const int64_t now=s.hit_count+s.miss_count+1;
            const int64_t age=sampled_op_last_[op]<0?now:std::max<int64_t>(0,now-sampled_op_last_[op]);
            const double activity=1.0/(1.0+static_cast<double>(age)/(64.0*std::max(1,p_)));
            reuse=std::min(1.0,16.0*conditional)*activity;
        }
        return reuse;
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
            sampled_.assign(n,SampleFrequency{});
            sampled_op_mass_.assign(s.operators.size(),0.0);
            sampled_op_last_.assign(s.operators.size(),-1);
            sampled_mass_=0;sampled_q_=-1;sampled_clock_=0;

            successor_.assign(n,-1);confidence_.assign(n,0);recent_.assign(n+2,-1);
            recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;confirmed_edges_=0;
            observed_q_ = -1; observed_count_ = 0;
            last_op_ = last_pid_ = stride_ = cached_stride_ = -1; streak_ = 0;
        }
        const int64_t q = s.hit_count + s.miss_count;
        // A miss and its periodic callback may expose the same pending request.
        // Probe ordinals deduplicate those, while preserving real repeated keys.
        frequencyUpdate(s,op,pid);
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
            if(evidence && sampled_mass_>0)reuse=frequencyReuse(s,o.op_id,part.partition_id,reuse);
            if (evidence && scan && o.op_id == op && o.op_id == last_op_) {
                const int delta = (part.partition_id - last_pid_ + p_) % p_;
                reuse = 1.0 - static_cast<double>(step_distance_[delta]) / p_;
            }
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
        active_ = true; update(s,op,pid); std::vector<Action> a;
        release(s,op,pid,s.operators[op].partitions[pid].data_size,a);
        pruneSpills(s,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> a;

        // Pending INSERT only: compare unavoidable immediate victim writes.
        // If every other positive resident is >=4*(target+tuple), spilling
        // the target then appending this tuple has a strictly lower local
        // write volume than spilling any other resident. No suffix guarantee.
        if(s.next_op.type=="INSERT"){
            const int op=s.next_op.op_id;
            if(op<0 || op>=static_cast<int>(s.operators.size()))return a;
            const int pid=static_cast<int>(s.next_op.key%s.num_partitions);
            const auto& target=s.operators[op].partitions[pid];
            const int64_t tuple=s.next_op.tuple_size;
            if(target.in_memory && target.data_size>0 && tuple>0
                && tuple>s.memory_limit-s.memory_used && tuple<=s.memory_limit
                && target.data_size<=s.memory_limit-tuple){
                const int64_t full=target.data_size+tuple;
                if(full<=s.memory_limit/4){
                    bool other=false,certified=true;
                    for(const auto& owner:s.operators)for(const auto& part:owner.partitions){
                        if(!part.in_memory || part.data_size<=0
                            || (owner.op_id==op && part.partition_id==pid))continue;
                        other=true;
                        if(part.data_size<4*full)certified=false;
                    }
                    if(other && certified){
                        active_=true;update(s);
                        a.emplace_back(Action::SPILL,op,pid);return a;
                    }
                }
            }
            return a;
        }
        if (!active_) return a;
        update(s);
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

        if(part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_){
            // All positive residents >M-B are incompatible with known B.
            // Prefetch only when these compulsory evictions alone cover B.
            int64_t free=s.memory_limit-s.memory_used;
            for(const auto& owner:s.operators)for(const auto& item:owner.partitions){
                if(item.in_memory && item.data_size>s.memory_limit-part.data_size){
                    free+=item.data_size;
                    a.emplace_back(Action::SPILL,owner.op_id,item.partition_id);
                }
            }
            if(free<part.data_size)return {};
            a.emplace_back(Action::LOAD,op,pid);return a;
        }
        release(s,op,pid,part.data_size,a); pruneSpills(s,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
};
