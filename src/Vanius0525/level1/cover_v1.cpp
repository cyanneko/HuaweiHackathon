// C++14 / standard library. Submit only this file after the official declarations.
#include <algorithm>
#include <vector>
#include <cstdint>

class MySpillScheduler : public SpillScheduler {
    struct Candidate {
        int op, pid;
        int64_t size;
        bool next;
    };
    std::vector<Candidate> candidates_;
    std::vector<int> order_, best_, trial_;

    // Minimize immediate write bytes; add exact visible next-request read cost.
    // This is a bounded candidate search, not an exact subset-sum solver.
    void evict(const SystemState& s, int target_op, int target_pid,
               int64_t bytes, std::vector<Action>& out) {
        const int64_t free_bytes = s.memory_limit - s.memory_used;
        const int64_t need = bytes > free_bytes ? bytes - free_bytes : 0;
        if (!need) return;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE" && s.next_op.op_id >= 0 &&
            s.next_op.op_id < static_cast<int>(s.operators.size())) {
            next_op = s.next_op.op_id;
            next_pid = static_cast<int>(s.next_op.key % s.num_partitions);
        }
        candidates_.clear();
        for (const auto& op : s.operators) {
            for (const auto& p : op.partitions) {
                if (p.in_memory && p.data_size > 0 &&
                    !(op.op_id == target_op && p.partition_id == target_pid)) {
                    candidates_.push_back({op.op_id, p.partition_id, p.data_size,
                        op.op_id == next_op && p.partition_id == next_pid});
                }
            }
        }
        const int n = static_cast<int>(candidates_.size());
        order_.resize(n);
        for (int i = 0; i < n; ++i) order_[i] = i;
        std::sort(order_.begin(), order_.end(), [&](int a, int b) {
            if (candidates_[a].size != candidates_[b].size)
                return candidates_[a].size < candidates_[b].size;
            if (candidates_[a].op != candidates_[b].op)
                return candidates_[a].op < candidates_[b].op;
            return candidates_[a].pid < candidates_[b].pid;
        });
        best_.clear();
        double best_cost = -1;
        int64_t best_bytes = 0;
        auto consider = [&]() {
            int64_t released = 0;
            double cost = 0;
            for (int i : trial_) {
                released += candidates_[i].size;
                cost += static_cast<double>(candidates_[i].size) / s.write_bandwidth;
                if (candidates_[i].next)
                    cost += static_cast<double>(candidates_[i].size) / s.read_bandwidth;
            }
            if (released < need) return;
            if (best_cost < 0 || cost < best_cost ||
                (cost == best_cost && (released < best_bytes ||
                 (released == best_bytes && trial_.size() < best_.size())))) {
                best_cost = cost;
                best_bytes = released;
                best_ = trial_;
            }
        };
        // Both with and without the next request, for feasible soft protection.
        for (int guard = 0; guard < 2; ++guard) {
            trial_.clear();
            // Best single-fit. Sorted order makes the first eligible fit cheapest.
            for (int x : order_) {
                if (guard && candidates_[x].next) continue;
                if (candidates_[x].size >= need) {
                    trial_.push_back(x); consider(); trial_.clear(); break;
                }
            }
            // Two monotone orders; bounded by 2*need if all selected sizes < need.
            for (int direction = 0; direction < 2; ++direction) {
                trial_.clear();
                int64_t sum = 0;
                for (int j = 0; j < n && sum < need; ++j) {
                    int x = order_[direction ? n - 1 - j : j];
                    if ((guard && candidates_[x].next) || candidates_[x].size >= need) continue;
                    trial_.push_back(x); sum += candidates_[x].size;
                }
                consider();
            }
        }
        // Exact best two-item cover in O(n) after sorting; avoid n^2 pair search.
        int l = 0, r = n - 1;
        while (l < r) {
            const auto& a = candidates_[order_[l]];
            const auto& b = candidates_[order_[r]];
            if (a.size + b.size >= need) {
                trial_.clear(); trial_.push_back(order_[l]); trial_.push_back(order_[r]);
                consider(); --r;
            } else ++l;
        }
        for (int i : best_)
            out.emplace_back(Action::SPILL, candidates_[i].op, candidates_[i].pid);
    }
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s, int op, int pid,
                                         int64_t tuple_size) override {
        std::vector<Action> out;
        evict(s, op, pid, tuple_size, out);
        return out;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s, int op, int pid) override {
        std::vector<Action> out;
        evict(s, op, pid, s.operators[op].partitions[pid].data_size, out);
        out.emplace_back(Action::LOAD, op, pid);
        return out;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> out;
        if (s.next_op.type != "PROBE") return out;
        int op = s.next_op.op_id;
        if (op < 0 || op >= static_cast<int>(s.operators.size())) return out;
        int pid = static_cast<int>(s.next_op.key % s.num_partitions);
        const auto& p = s.operators[op].partitions[pid];
        if (s.operators[op].phase != Phase::PROBE || p.in_memory ||
            p.data_size > s.memory_limit) return out;
        // The next input is known exactly. Execute its mandatory LOAD now;
        // no intervening input can pollute the prefetched partition.
        evict(s, op, pid, p.data_size, out);
        out.emplace_back(Action::LOAD, op, pid);
        return out;
    }
};
