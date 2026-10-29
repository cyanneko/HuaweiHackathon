// Generated standalone C++14 scheduler. Only callback-visible information is used.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
#ifdef L1_COLLECT
#include <iostream>
#endif
class MySpillScheduler : public SpillScheduler {
    struct History { int64_t last = -1, previous = -1; double count = 0; };
    struct Item { int op, pid, id; int64_t size; double rank; bool next; };
    std::vector<History> history_;
    std::vector<Item> items_;
    std::vector<int> selected_;
    int partitions_ = 0;
    int64_t last_observed_ = -1;
    int64_t observed_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;
    int64_t last_stream_q_ = -1;
    void init(const SystemState& s) {
        const int n = static_cast<int>(s.operators.size()) * s.num_partitions;
        if (static_cast<int>(history_.size()) != n || partitions_ != s.num_partitions) {
            history_.assign(n, History{}); partitions_ = s.num_partitions;
            last_observed_ = -1; observed_ = 0;
            last_op_ = last_pid_ = stride_ = -1; streak_ = 0; last_stream_q_ = -1;
        }
    }
    void observe(int op, int pid, int64_t q) {
        if (q <= last_observed_ || op < 0 || op * partitions_ + pid >= static_cast<int>(history_.size())) return;
        auto& h = history_[op * partitions_ + pid];
        if (h.last >= 0) h.count *= 256.0 / (256.0 + static_cast<double>(q - h.last));
        h.count += 1; h.previous = h.last; h.last = q;
        if (q == last_stream_q_ + 1 && op == last_op_) {
            int delta = (pid - last_pid_ + partitions_) % partitions_;
            if (delta != 0 && delta == stride_) ++streak_;
            else { stride_ = delta; streak_ = 1; }
        } else { stride_ = -1; streak_ = 0; }
        last_op_ = op; last_pid_ = pid; last_stream_q_ = q;
        last_observed_ = q; ++observed_;
    }
    void begin(const SystemState& s, int current_op = -1, int current_pid = -1) {
        init(s);
        const int64_t q = s.hit_count + s.miss_count;
        if (current_op >= 0) observe(current_op, current_pid, q);
        if (s.next_op.type == "PROBE" && s.next_op.op_id >= 0 &&
            s.next_op.op_id < static_cast<int>(s.operators.size()))
            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % s.num_partitions), q + 1);
    }
    void features(const SystemState& s, int op, int pid, int64_t need, int context_op, float* f) const {
        const int id = op * partitions_ + pid;
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
        f[9] = static_cast<float>(std::min(1.0, static_cast<double>(observed_) / std::max<int64_t>(1,q)));
        f[10] = static_cast<float>(std::min(8,streak_)) / 8;
        // If a contiguous constant-stride stream is observed, distance in that cycle.
        int distance = partitions_;
        if (op == last_op_ && streak_ >= 3 && stride_ > 0) {
            int at = last_pid_;
            for (int j = 1; j <= partitions_; ++j) {
                at = (at + stride_) % partitions_;
                if (at == pid) { distance = j; break; }
            }
        }
        f[11] = static_cast<float>(distance) / partitions_;
    }
    // MODEL_BEGIN
    
    // MODEL_END
    double reuse(const float* f) const {
        if (!f[4]) return 0;
        return f[3] / (1.0 + std::pow(2.0,f[1]*16.0) / 64.0);
    }
    void choose(const SystemState& s, int op, int pid, int64_t bytes, std::vector<Action>& out) {
        int64_t free_bytes = s.memory_limit - s.memory_used;
        int64_t need = bytes > free_bytes ? bytes - free_bytes : 0;
        if (!need) return;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE") {
            next_op = s.next_op.op_id; next_pid = static_cast<int>(s.next_op.key % partitions_);
        }
        items_.clear();
        for (const auto& o : s.operators) for (const auto& p : o.partitions) {
            if (!p.in_memory || p.data_size <= 0 || (o.op_id == op && p.partition_id == pid)) continue;
            bool next = o.op_id == next_op && p.partition_id == next_pid;
            float f[12]; features(s, o.op_id, p.partition_id, need, op, f);
            double prob = reuse(f);
#ifdef L1_COLLECT
            std::cerr << "FEATURE " << (s.hit_count + s.miss_count) << ' ' << o.op_id << ' ' << p.partition_id;
            for (float x : f) std::cerr << ' ' << x;
            std::cerr << '\n';
#endif
            // Missing penalty is not visible: use its documented lower bound, 1us.
            double rank = prob * (1.0/s.read_bandwidth + 1.0/s.write_bandwidth + 1.0/p.data_size);
            if (next) rank += 1e12;
            items_.push_back({o.op_id,p.partition_id,o.op_id * partitions_ + p.partition_id,p.data_size,rank,next});
        }
        std::sort(items_.begin(), items_.end(), [](const Item& a, const Item& b) {
            if (a.rank != b.rank) return a.rank < b.rank;
            if (a.size != b.size) return a.size > b.size;
            return a.id < b.id;
        });
        // Greedy by predicted harm per freed byte. Favor a cheap fitting victim
        // only among the same risk tier; never trade a hot object for a few bytes.
        int64_t freed = 0;
        for (const auto& x : items_) {
            if (freed >= need) break;
            out.emplace_back(Action::SPILL,x.op,x.pid); freed += x.size;
        }
    }
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        begin(s); std::vector<Action> a; choose(s,op,pid,z,a); return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        begin(s,op,pid); std::vector<Action> a;
        choose(s,op,pid,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        begin(s); std::vector<Action> a;
        if (s.next_op.type != "PROBE") return a;
        int op=s.next_op.op_id;
        if (op < 0 || op >= static_cast<int>(s.operators.size())) return a;
        int pid=static_cast<int>(s.next_op.key % partitions_);
        const auto& p=s.operators[op].partitions[pid];
        if (s.operators[op].phase != Phase::PROBE || p.in_memory || p.data_size > s.memory_limit) return a;
        choose(s,op,pid,p.data_size,a); a.emplace_back(Action::LOAD,op,pid); return a;
    }
};
