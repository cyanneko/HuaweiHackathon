// Submit this class (and standard-library includes) after the official declarations.
// No input access, engine changes, training, external data, or C++17 features.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
class MySpillScheduler : public SpillScheduler {
    struct History { int64_t previous = -1; int64_t last = -1; double count = 0; };
    struct Victim { int op, pid; int64_t bytes; double priority; };
    std::vector<History> history_;
    std::vector<Victim> victims_;
    std::vector<int> step_distance_;
    std::vector<int> successor_, confidence_, recent_;
    int recent_head_=0, recent_count_=0;
    int64_t graph_version_=0, analyzed_version_=-1;
    bool uniform_cycle_=false;
    bool active_ = false;
    bool build_overflow_ = false;
    int64_t last_overflow_q_=-1; int overflow_streak_=0;
    int p_ = 0, cached_stride_ = -1;
    int64_t observed_q_ = -1, observed_count_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;
    void observe(int op, int pid, int64_t q) {
        if (q <= observed_q_) return;
        const int current_id=op*p_+pid;
        if (q==observed_q_+1 && last_op_>=0) {
            const int previous_id=last_op_*p_+last_pid_;
            if (successor_[previous_id]==current_id) {
                confidence_[previous_id]=std::min(7,confidence_[previous_id]+1);
                if (confidence_[previous_id]==3) ++graph_version_;
            } else {successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;}
        }
        recent_[recent_head_]=current_id;
        recent_head_=(recent_head_+1)%static_cast<int>(recent_.size());
        recent_count_=std::min(recent_count_+1,static_cast<int>(recent_.size()));
        auto& h = history_[op * p_ + pid];
        if (h.last >= 0)
            h.count *= 256.0 / (256.0 + static_cast<double>(q - h.last));
        h.count += 1; h.previous=h.last; h.last = q;
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
            successor_.assign(n,-1);confidence_.assign(n,0);recent_.assign(n+2,-1);
            recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;
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
    void features(const SystemState& s, int op, int pid, int64_t need, int context_op, float* f) const {
        const int id = op * p_ + pid;
        const auto& h = history_[id];
        const int64_t q = s.hit_count + s.miss_count + 1;
        const double age = h.last < 0 ? 1000000.0 : std::max<int64_t>(0, q - h.last);
        const double gap = h.previous < 0 ? 1000000.0 : h.last - h.previous;
        const auto& part = s.operators[op].partitions[pid];
        f[0] = static_cast<float>(static_cast<double>(part.data_size) / s.memory_limit);
        f[1] = static_cast<float>(std::min(16.0, std::log2(1 + age)) / 16);
        f[2] = static_cast<float>(std::min(16.0, std::log2(1 + gap)) / 16);
        f[3] = static_cast<float>(std::min(1.0, h.count / 16));
        f[4] = h.last >= 0 ? 1.f : 0.f;
        f[5] = s.operators[op].phase == Phase::PROBE ? 1.f : 0.f;
        f[6] = op == context_op ? 1.f : 0.f;
        f[7] = static_cast<float>(static_cast<double>(need) / s.memory_limit);
        f[8] = static_cast<float>(static_cast<double>(s.memory_used) / s.memory_limit);
        f[9] = static_cast<float>(std::min(1.0, static_cast<double>(observed_count_) / std::max<int64_t>(1,q)));
        f[10] = static_cast<float>(std::min(8,streak_)) / 8;
        // If a contiguous constant-stride stream is observed, distance in that cycle.
        int distance = p_;
        if (op == last_op_ && streak_ >= 3 && stride_ > 0) {
            distance = step_distance_[(pid-last_pid_+p_)%p_];
        }
        f[11] = static_cast<float>(distance) / p_;
    }

    double neural(const float* f) const {
        static const double W0[12][16] = {{0.6531018019,0.624638617,0.7816463113,0.4997358918,0.7080820203,-0.8066800237,-0.6563507318,0.7147295475,-0.7383183241,1.350916179e-39,-0.378716439,-0.1369892061,-1.101933122,-0.2321365476,0.05265025422,0.5238366723},{0.1581695229,-0.3277945518,0.01952712424,0.01540170237,0.08564252406,-0.2357313931,-0.03296307847,-0.3507801294,0.1130761653,5.864027697e-40,-0.198231712,-0.06566207111,-0.4960745871,-0.5228007436,0.08013014495,0.0006231765146},{0.2414515316,0.3758221865,-0.5797220469,-0.07100173086,-0.1599213332,-0.4071601033,-0.4309327006,-0.1678030491,-0.2046861053,-6.876886227e-40,0.1836039126,0.4431817234,-0.3518283963,-0.2456005216,-0.07905686647,-0.1690536737},{0.1526389271,-0.2799896002,-0.9839074016,0.1706142873,-0.2118939012,0.5822546482,0.1517689824,0.3429069221,-0.1417506635,-1.400921515e-39,0.361682415,0.2132888436,-0.1225298122,0.2013231665,0.219805941,0.5565208197},{0.08266247809,-0.08852398396,0.02582775615,-0.4343286753,-0.02322405018,-0.1539057046,-0.3193012476,0.04922439903,-0.03457937017,-8.839390713e-42,0.3023446798,-0.03990743682,0.1989936382,-0.04190501943,0.1699157804,-0.1732174903},{0.07058208436,0.3361792862,0.3075878322,-0.5075308681,-0.302413404,0.5075145364,-0.2229525596,0.2792608738,-0.005915604532,-4.788012645e-40,-0.05992123857,-0.3686417341,0.2537809014,-0.1244160011,-0.368390739,0.3600500822},{-0.2317559421,0.3582183421,0.1914412826,0.2359718978,0.1777035147,0.3233498633,0.1598876864,0.3295398057,0.3095763624,-3.189089058e-40,0.02719129995,0.3644317687,-0.2897436917,-0.003810165683,-0.2995397449,-0.4425381422},{0.100567162,0.1756885648,0.3517712653,0.2980936468,-0.04205960408,-0.09802603722,-1.088496327,0.2154433876,0.0160005074,-4.077918661e-40,0.04030190781,-0.09788346291,-0.7163475752,0.05067095533,0.128355056,-0.3127172291},{0.204773277,0.2157827765,-0.06384372711,-0.4162923396,0.3817323446,0.04694264382,0.003992237616,-0.0003667846031,0.3367762566,5.613587635e-40,0.05479002371,0.07764849067,0.4438889325,-0.2852328718,0.1927049607,0.08934614807},{-0.7620294094,0.1848054081,0.02075446956,0.2823195755,0.2821425498,-0.2612741292,0.2137778103,-0.1369576752,0.3393775821,5.859935905e-40,-0.2696810067,0.1741891205,-0.05139539763,-0.1291676909,0.136040017,-0.2339528948},{-0.06073271483,-0.3018199503,-0.4968790412,0.193867743,0.2588405013,0.3455654979,0.1506579667,-0.1407705992,0.4417265952,-4.917941038e-40,0.3128001988,0.02664168552,-0.008905096911,0.3300576806,-0.4185212553,0.09328089654},{0.1546471417,-0.4099296033,0.0228667669,-0.1447741389,-0.1134209484,-0.08171503246,0.2845565975,-0.05967737734,0.2841707468,1.037713361e-39,0.1046463698,0.06325894594,0.171750173,0.4521421194,0.2245143205,-0.1906540841}};
        static const double B0[16] = {-0.1832876503,0.1660025418,0.1147060692,0.3302640319,0.128660202,0.1220908016,0.2762263119,0.3317260444,0.2168150246,-0.07666873932,0.3126607537,-0.1807805449,-0.06037419289,-0.249035731,0.301794529,-0.2123807967};
        static const double W1[16] = {0.2428736687,0.2962046564,-0.6735422611,-0.3697238564,0.1380225122,0.7107812762,-0.2596244812,0.2556019127,-0.4260511994,4.763840246e-40,-0.4327972531,0.3689920604,0.3721946478,0.5810942054,-0.2374003083,-0.8203074932};
        double y = 0.4551424086;
        for (int j=0;j<16;++j) {
            double v=B0[j]; for (int i=0;i<12;++i) v+=f[i]*W0[i][j];
            if (v>0) y+=v*W1[j];
        }
        return std::max(0.0,std::min(1.0,y));
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
            if (evidence && scan && o.op_id == op && o.op_id == last_op_) {
                const int delta = (part.partition_id - last_pid_ + p_) % p_;
                reuse = 1.0 - static_cast<double>(step_distance_[delta]) / p_;
            }
            // The true penalty is absent from SystemState. Only its documented
            // lower bound (1 microsecond) is used in this cost-density heuristic.
            double priority = reuse * (1.0 / s.read_bandwidth +
                1.0 / s.write_bandwidth + 1.0 / part.data_size);
            if (build_overflow_ && o.phase==Phase::BUILD) priority+=1e6;
            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;
            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});
        }
        if (evidence && !uniform_cycle_ && !victims_.empty()) {
            auto less = [](const Victim& a,const Victim& b) {
                if (a.priority!=b.priority) return a.priority<b.priority;
                return a.bytes>b.bytes;
            };
            const int cap=std::min<int>(4,victims_.size());
            std::partial_sort(victims_.begin(),victims_.begin()+cap,victims_.end(),less);
            for (int j=0;j<cap;++j) {
                auto& v=victims_[j];float f[12];features(s,v.op,v.pid,need,op,f);
                v.priority=neural(f)*(1/s.read_bandwidth+1/s.write_bandwidth+1.0/v.bytes);
                if (build_overflow_ && s.operators[v.op].phase==Phase::BUILD) v.priority+=1e6;
                if (v.op==next_op && v.pid==next_pid) v.priority+=1e12;
            }
            std::sort(victims_.begin(),victims_.begin()+cap,less);
            int64_t freed=0;
            for (int j=0;j<cap && freed<need;++j) {
                const auto& v=victims_[j];actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
            }
            if (freed>=need) return;
            std::sort(victims_.begin()+cap,victims_.end(),less);
            for (int j=cap;j<static_cast<int>(victims_.size()) && freed<need;++j) {
                const auto& v=victims_[j];actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
            }
            return;
        }
        auto better = [](const Victim& a, const Victim& b) {
            if (a.priority != b.priority) return a.priority < b.priority;
            return a.bytes > b.bytes;
        };
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
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        const int64_t q=s.hit_count+s.miss_count;
        overflow_streak_=(last_overflow_q_==q)?overflow_streak_+1:1;
        last_overflow_q_=q;
        build_overflow_=s.next_op.type=="INSERT" && s.next_op.op_id==op;
        active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a);
        build_overflow_=false;return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        active_ = true; update(s,op,pid); std::vector<Action> a;
        release(s,op,pid,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> a;
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
        if (part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_) return a;
        release(s,op,pid,part.data_size,a); a.emplace_back(Action::LOAD,op,pid); return a;
    }
};
