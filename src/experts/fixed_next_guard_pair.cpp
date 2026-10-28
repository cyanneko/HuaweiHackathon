#include "best_fit_fast/expert.hpp"
#include "next_guard_fast/expert.hpp"
#include "../../expert_runtime/v1/two_expert.hpp"
// Fixed next-guard selection, retaining both registered experts' lifecycle.
class MySpillScheduler : public hj_expert_v1::TwoExpertScheduler<
    cyanneko_best_fit_fast_v1::Expert,101,
    cyanneko_next_guard_fast_v1::Expert,102,
    hj_expert_v1::FixedSelector<102>> {};
