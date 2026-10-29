#include "../../best_fit_fast/expert.hpp"
#include "../../naive_unique_max_fused/expert.hpp"
#include "../../../../expert_runtime/v1/two_expert.hpp"
// Isolated test fixture only. The public default101/102 pair is unchanged.
class MySpillScheduler : public hj_expert_v1::TwoExpertScheduler<
    cyanneko_best_fit_fast_v1::Expert,101,
    cyanneko_naive_unique_max_fused_v1::Expert,104,
    hj_expert_v1::FixedSelector<104>> {};
