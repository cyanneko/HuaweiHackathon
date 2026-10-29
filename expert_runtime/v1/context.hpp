#ifndef HJ_EXPERT_V1_CONTEXT_HPP
#define HJ_EXPERT_V1_CONTEXT_HPP
#include <cstdint>
#include <vector>
// Official SystemState and Action must be declared before this header.
namespace hj_expert_v1 {
using ExpertId = std::uint16_t;
constexpr ExpertId kNoExpert = 65535;
enum class CallbackKind { Overflow, Miss, Periodic };
struct DecisionContext {
    const SystemState& state;
    CallbackKind kind;
    int op_id;
    int partition_id;
    std::int64_t tuple_size;
    std::uint64_t callback_index;
};
struct DispatchView {
    ExpertId selected_id;
    const std::vector<Action>& actions;
};
}
#endif
