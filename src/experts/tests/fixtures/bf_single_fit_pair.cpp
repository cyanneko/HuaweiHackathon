#include "../../best_fit_fast/expert.hpp"
#include "../../single_fit_phase/expert.hpp"
#include "../../../../expert_runtime/v1/two_expert.hpp"
// Test fixture only: default public BF/NG pair remains unchanged.
class MySpillScheduler : public hj_expert_v1::TwoExpertScheduler<
    cyanneko_best_fit_fast_v1::Expert,101,
    cyanneko_single_fit_phase_v1::Expert,103,
    hj_expert_v1::FixedSelector<103>> {};
