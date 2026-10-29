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
    int forced_mode_ = -1;
    int p_ = 0, cached_stride_ = -1;
    int64_t observed_q_ = -1, observed_count_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;
    void observe(int op, int pid, int64_t q) {
        if (q <= observed_q_) return;
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
    int learnedGate(const float* f) const { return (f[8] <= 0.02894643322 ? 4 : (f[7] <= 0.001790364564 ? (f[1] <= 0.09250000864 ? 4 : 2) : (f[11] <= 0.978761971 ? (f[6] <= 0.1950375512 ? (f[6] <= 0.1888011992 ? 0 : 4) : (f[3] <= 0.3582887948 ? 0 : 2)) : 2))); }
    void release(const SystemState& s, int op, int pid, int64_t required,
                 std::vector<Action>& actions) {
        const int64_t free_bytes = s.memory_limit - s.memory_used;
        if (required <= free_bytes) return;
        const int64_t need = required - free_bytes;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE") {
            next_op = s.next_op.op_id; next_pid = static_cast<int>(s.next_op.key % p_);
        }
        float gf[12]; gateFeatures(s,op,pid,required,gf);
        const int mode = forced_mode_ >= 0 ? forced_mode_ : learnedGate(gf);
        const int64_t now = s.hit_count + s.miss_count + 1;
        const bool evidence = s.hit_count + s.miss_count > 0;
        const bool scan = mode != 1 && streak_ >= 6 && stride_ > 0 &&
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
            if (evidence && mode == 2) reuse = 0;
            if (evidence && mode == 3) reuse = h.last < 0 ? 0.0 :
                1.0 / (1.0 + static_cast<double>(std::max<int64_t>(0,now-h.last)));
            if (evidence && mode == 4) reuse = h.last < 0 ? 1.0 :
                1.0 - 1.0 / (1.0 + static_cast<double>(std::max<int64_t>(0,now-h.last)));
            // The true penalty is absent from SystemState. Only its documented
            // lower bound (1 microsecond) is used in this cost-density heuristic.
            double priority = reuse * (1.0 / s.read_bandwidth +
                1.0 / s.write_bandwidth + (mode == 5 ? 256.0 : 1.0) / part.data_size);
            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;
            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});
        }
        std::sort(victims_.begin(), victims_.end(), [](const Victim& a, const Victim& b) {
            if (a.priority != b.priority) return a.priority < b.priority;
            return a.bytes > b.bytes;
        });
        int64_t freed = 0;
        for (const auto& v : victims_) {
            if (freed >= need) break;
            actions.emplace_back(Action::SPILL, v.op, v.pid); freed += v.bytes;
        }
    }
public:
    void forceMode(int mode) { forced_mode_ = mode; }
    void prepareFeatures(const SystemState& s,int op,int pid,int64_t required,bool miss,float* f) {
        update(s,miss ? op : -1,pid); gateFeatures(s,op,pid,required,f);
    }
    void gateFeatures(const SystemState& s,int op,int pid,int64_t required,float* f) const {
        int n=0, seen=0; double total=0, maximum=0, build_bytes=0, count=0, age=0;
        const int64_t q=s.hit_count+s.miss_count+1;
        for (const auto& o:s.operators) for (const auto& p:o.partitions) {
            if (!p.in_memory || p.data_size<=0) continue;
            ++n;total+=p.data_size; maximum=std::max(maximum,static_cast<double>(p.data_size));
            if (o.phase==Phase::BUILD) build_bytes+=p.data_size;
            const auto& h=history_[o.op_id*p_+p.partition_id];
            if (h.last>=0) { ++seen;count+=std::min(16.0,h.count);age+=std::min<int64_t>(1024,std::max<int64_t>(0,q-h.last)); }
        }
        f[0]=static_cast<float>(static_cast<double>(required)/s.memory_limit);
        f[1]=static_cast<float>(static_cast<double>(s.memory_limit-s.memory_used)/s.memory_limit);
        f[2]=static_cast<float>(n)/512;
        f[3]=static_cast<float>(maximum/std::max(1.0,total));
        f[4]=static_cast<float>(build_bytes/std::max(1.0,total));
        f[5]=static_cast<float>(seen)/std::max(1,n);
        f[6]=static_cast<float>(count/(16*std::max(1,n)));
        f[7]=static_cast<float>(age/(1024*std::max(1,seen)));
        f[8]=static_cast<float>(std::min(1.0,static_cast<double>(observed_count_)/q));
        f[9]=static_cast<float>(std::min(8,streak_))/8;
        f[10]=s.next_op.type=="PROBE" ? 1.f : 0.f;
        f[11]=static_cast<float>(static_cast<double>(s.hit_count)/q);
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        update(s); std::vector<Action> a; release(s,op,pid,z,a); return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        update(s,op,pid); std::vector<Action> a;
        release(s,op,pid,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        update(s); std::vector<Action> a;
        if (s.next_op.type != "PROBE") return a;
        const int op=s.next_op.op_id;
        if (op < 0 || op >= static_cast<int>(s.operators.size())) return a;
        const int pid=static_cast<int>(s.next_op.key % p_);
        const auto& part=s.operators[op].partitions[pid];
        if (s.operators[op].phase != Phase::PROBE || part.in_memory ||
            part.data_size > s.memory_limit) return a;
        release(s,op,pid,part.data_size,a); a.emplace_back(Action::LOAD,op,pid); return a;
    }
};
