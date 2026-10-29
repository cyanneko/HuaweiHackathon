#pragma once
#include <cmath>
// Generated from a frozen R61 cost tree; BF101=0, SF103=1.
static inline int r61_tree_choose(const double* x) {
  for (int i=0;i<16;++i) if (!std::isfinite(x[i])) return 0;
  if (x[4] <= 0.0003326743608340621) {
    return 0;
  } else {
    return 1;
  }
}
