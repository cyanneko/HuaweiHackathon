#include "tiny.generated.hpp"

static void require(bool ok, const char* message) {
    if (!ok) {
        std::cerr << "TINY_FAIL: " << message << '\n';
        std::exit(3);
    }
}

static SystemState state(std::vector<int64_t> sizes = {20, 100, 90, 80, 70, 60}) {
    SystemState s;
    s.memory_used = 0;
    s.num_partitions = static_cast<int>(sizes.size());
    s.write_bandwidth = s.read_bandwidth = 1.;
    s.hit_count = s.miss_count = s.total_io_bytes = 0;
    OperatorState op;
    op.op_id = 0;
    op.phase = Phase::BUILD;
    for (int i = 0; i < s.num_partitions; ++i) {
        PartitionState p;
        p.partition_id = i;
        p.data_size = sizes[i];
        op.partitions.push_back(p);
        s.memory_used += sizes[i];
    }
    s.operators.push_back(op);
    s.memory_limit = s.memory_used;
    return s;
}

static bool same(const std::vector<Action>& a, const std::vector<Action>& b) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i)
        if (a[i].type != b[i].type || a[i].op_id != b[i].op_id
            || a[i].partition_id != b[i].partition_id) return false;
    return true;
}

static void fallback(SystemState s, int64_t required, const char* label) {
    baseline::MySpillScheduler parent;
    candidate::MySpillScheduler changed;
    require(same(parent.onMemoryOverflow(s, 0, 0, required),
                 changed.onMemoryOverflow(s, 0, 0, required)), label);
}

struct BuildWriteProbe : SpillScheduler {
    std::vector<Action> onMemoryOverflow(const SystemState&, int, int, int64_t) override {
        return {Action(Action::SPILL, 0, 1)};
    }
    std::vector<Action> onPartitionMiss(const SystemState&, int, int) override { return {}; }
    std::vector<Action> onPeriodicAdjust(const SystemState&) override {
        // The official engine must ignore this BUILD LOAD.
        return {Action(Action::LOAD, 0, 1)};
    }
};

int main() {
#ifdef EXPECT_PARENT_RED
    baseline::MySpillScheduler first;
#else
    candidate::MySpillScheduler first;
#endif
    auto s = state();
    auto a = first.onMemoryOverflow(s, 0, 0, 50);
    require(a.size() == 1 && a[0].type == Action::SPILL && a[0].op_id == 0
            && a[0].partition_id == 5, "minimum_single_victim_beyond_parent_top4");

    candidate::MySpillScheduler ties;
    a = ties.onMemoryOverflow(state({20, 100, 90, 80, 60, 60}), 0, 0, 50);
    require(a.size() == 1 && a[0].partition_id == 4, "stable_traversal_tie");

    candidate::MySpillScheduler exclude;
    a = exclude.onMemoryOverflow(state({80, 100, 90, 70, 60, 20}), 0, 0, 75);
    require(a.size() == 1 && a[0].partition_id == 2, "exclude_current_insert_target");

    candidate::MySpillScheduler resident;
    s = state();
    s.operators[0].partitions[5].in_memory = false;
    s.memory_used -= 60;
    s.memory_limit = s.memory_used;
    a = resident.onMemoryOverflow(s, 0, 0, 50);
    require(a.size() == 1 && a[0].partition_id == 4, "exclude_already_spilled");

    fallback(state(), 101, "no_single_fit_original_fallback");
    s = state();
    s.hit_count = 1;
    fallback(s, 50, "observed_probe_original_fallback");
    s = state();
    s.next_op.type = "PROBE";
    s.next_op.op_id = 0;
    s.next_op.key = 5;
    fallback(s, 50, "pending_probe_original_fallback");
    s = state();
    auto other = s.operators[0];
    other.op_id = 1;
    other.phase = Phase::PROBE;
    s.operators.push_back(other);
    s.memory_used *= 2;
    s.memory_limit = s.memory_used;
    fallback(s, 50, "mixed_phase_original_fallback");
    s = state();
    s.memory_limit += 100;
    fallback(s, 50, "no_overflow_empty_fallback");

    HashJoinEngine engine(100, 2, 1., 1., 100, 1,
                          std::unique_ptr<SpillScheduler>(new BuildWriteProbe));
    engine.addOperator(0);
    engine.processInsert(0, 0, 60);
    engine.processInsert(0, 1, 40);
    engine.processInsert(0, 0, 20); // spill existing 40 bytes
    engine.processInsert(0, 1, 10); // already-spilled BUILD writes new 10 bytes
    std::ostringstream output;
    auto* previous = std::cout.rdbuf(output.rdbuf());
    engine.printResult();
    std::cout.rdbuf(previous);
    require(output.str().find("Total_IO_Time: 50.00\n") != std::string::npos,
            "official_build_spill_plus_direct_insert_write");
    require(output.str().find("Hit_Count: 0\n") != std::string::npos
            && output.str().find("Miss_Count: 0\n") != std::string::npos,
            "official_build_load_ignored_no_probe_counts");
    std::cout << "TINY_BUILD_PASS cases=10\n";
}
