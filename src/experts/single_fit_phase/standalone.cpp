#include "expert.hpp"
#include "../../../expert_runtime/v1/two_expert.hpp"
class MySpillScheduler : public hj_expert_v1::SingleExpertScheduler<cyanneko_single_fit_phase_v1::Expert,103> {};
