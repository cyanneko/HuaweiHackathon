#pragma once
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <algorithm>
#include <cstdint>
#include <cassert>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <memory>
#include <tuple>

/* ===== 数据结构定义 ===== */

enum class Phase { BUILD, PROBE };

struct PartitionState {
    int partition_id;
    int64_t data_size;   // 当前数据总大小（字节）
    bool in_memory;      // 是否在内存中
    PartitionState() : partition_id(-1), data_size(0), in_memory(true) {}
};

struct OperatorState {
    int op_id;
    Phase phase;
    std::vector<PartitionState> partitions;  // P个分区
};

struct PendingOp {
    std::string type;      // "INSERT" / "SWITCH" / "PROBE" / ""（无后续操作）
    int op_id;             // 算子ID，type为空时无意义
    int64_t key;           // INSERT/PROBE时的key，SWITCH时无意义
    int64_t tuple_size;    // INSERT时的元组大小，其余操作无意义
    PendingOp() : op_id(-1), key(0), tuple_size(0) {}
};

struct SystemState {
    int64_t memory_used;
    int64_t memory_limit;
    int num_partitions;
    double write_bandwidth;    // 字节/微秒
    double read_bandwidth;     // 字节/微秒
    int64_t hit_count;
    int64_t miss_count;
    int64_t total_io_bytes;
    std::vector<OperatorState> operators;
    PendingOp next_op;         // 下一个待处理操作
};

/* ===== 调度动作 ===== */

struct Action {
    enum Type { SPILL, LOAD } type;
    int op_id;
    int partition_id;
    Action(Type t, int o, int p) : type(t), op_id(o), partition_id(p) {}
};

/* ===== 调度器抽象基类 ===== */

class SpillScheduler {
public:
    virtual ~SpillScheduler() = default;

    // 场景1：INSERT导致内存溢出时调用
    virtual std::vector<Action> onMemoryOverflow(
        const SystemState& state,
        int op_id, int partition_id, int64_t tuple_size) = 0;

    // 场景2：PROBE需要加载磁盘分区时调用
    virtual std::vector<Action> onPartitionMiss(
        const SystemState& state,
        int op_id, int partition_id) = 0;

    // 场景3：周期性调度，每处理B个操作后调用
    virtual std::vector<Action> onPeriodicAdjust(
        const SystemState& state) = 0;
};

/* ===== 朴素调度器（基线实现）===== */

class NaiveSpillScheduler : public SpillScheduler {
public:
    // 内存溢出时：选择最大的in_memory分区落盘，直到释放足够空间
    std::vector<Action> onMemoryOverflow(
        const SystemState& state,
        int op_id, int partition_id, int64_t tuple_size) override {

        std::vector<Action> actions;
        int64_t needed = tuple_size;
        int64_t available = state.memory_limit - state.memory_used;

        // 收集所有in_memory分区，按data_size降序排列（排除当前正在插入的目标分区）
        std::vector<std::tuple<int64_t, int, int>> candidates;
        for (const auto& op : state.operators) {
            for (const auto& part : op.partitions) {
                if (part.in_memory && part.data_size > 0 &&
                    !(op.op_id == op_id && part.partition_id == partition_id)) {
                    candidates.emplace_back(part.data_size, op.op_id, part.partition_id);
                }
            }
        }
        std::sort(candidates.begin(), candidates.end(),
                  [](const auto& a, const auto& b) { return std::get<0>(a) > std::get<0>(b); });

        for (const auto& cand : candidates) {
            if (available >= needed) break;
            int64_t sz = std::get<0>(cand);
            int oid = std::get<1>(cand);
            int pid = std::get<2>(cand);
            actions.emplace_back(Action::SPILL, oid, pid);
            available += sz;
        }
        return actions;
    }

    // Probe未命中时：选择最大的in_memory分区落盘腾出空间，然后加载目标分区
    std::vector<Action> onPartitionMiss(
        const SystemState& state,
        int op_id, int partition_id) override {

        std::vector<Action> actions;
        int64_t needed = state.operators[op_id].partitions[partition_id].data_size;
        int64_t available = state.memory_limit - state.memory_used;

        if (available < needed) {
            std::vector<std::tuple<int64_t, int, int>> candidates;
            for (const auto& op : state.operators) {
                for (const auto& part : op.partitions) {
                    if (part.in_memory && part.data_size > 0 &&
                        !(op.op_id == op_id && part.partition_id == partition_id)) {
                        candidates.emplace_back(part.data_size, op.op_id, part.partition_id);
                    }
                }
            }
            std::sort(candidates.begin(), candidates.end(),
                      [](const auto& a, const auto& b) { return std::get<0>(a) > std::get<0>(b); });

            for (const auto& cand : candidates) {
                if (available >= needed) break;
                int64_t sz = std::get<0>(cand);
                int oid = std::get<1>(cand);
                int pid = std::get<2>(cand);
                actions.emplace_back(Action::SPILL, oid, pid);
                available += sz;
            }
        }

        actions.emplace_back(Action::LOAD, op_id, partition_id);
        return actions;
    }

    // 朴素策略：不做主动调整
    std::vector<Action> onPeriodicAdjust(const SystemState& state) override {
        return {};
    }
};

