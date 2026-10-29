#pragma once
// Test-only declarations matching the saved official interface; no engine.
#include <cstdint>
#include <string>
#include <vector>
enum class Phase { BUILD, PROBE };
struct PartitionState { int partition_id=-1; std::int64_t data_size=0; bool in_memory=true; };
struct OperatorState { int op_id=0; Phase phase=Phase::BUILD; std::vector<PartitionState> partitions; };
struct PendingOp { std::string type; int op_id=-1; std::int64_t key=0, tuple_size=0; };
struct SystemState {
    std::int64_t memory_used=0, memory_limit=0;
    int num_partitions=0;
    double write_bandwidth=1, read_bandwidth=1;
    std::int64_t hit_count=0, miss_count=0, total_io_bytes=0;
    std::vector<OperatorState> operators;
    PendingOp next_op;
};
struct Action {
    enum Type { SPILL, LOAD } type;
    int op_id, partition_id;
    Action(Type t, int o, int p):type(t),op_id(o),partition_id(p){}
};
class SpillScheduler {
public:
    virtual ~SpillScheduler() = default;
    virtual std::vector<Action> onMemoryOverflow(const SystemState&,int,int,std::int64_t)=0;
    virtual std::vector<Action> onPartitionMiss(const SystemState&,int,int)=0;
    virtual std::vector<Action> onPeriodicAdjust(const SystemState&)=0;
};
