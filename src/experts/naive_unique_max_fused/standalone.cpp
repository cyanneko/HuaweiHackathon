#include "expert.hpp"
#include "../../../expert_runtime/v1/two_expert.hpp"
class MySpillScheduler : public hj_expert_v1::SingleExpertScheduler<cyanneko_naive_unique_max_fused_v1::Expert,104> {};
