# R74: causal refault risk added to frozen VanBest

This is an isolated implementation artifact. It does not modify the frozen baseline, engine, Git repositories, hidden penalty, or training data. No performance benchmark or training was run by the implementation task. Functional compilation and assertions passed; performance and score effects remain to be measured by the parent task.

## Files and ablations

- `R74_partition.policy.cpp`: confirmed PROBE-phase spill-to-miss risk per partition; fixed 75% refault / 25% original visible-demand blend where refault evidence exists.
- `R74_operator.policy.cpp`: additionally shrink partition waiting estimate toward pooled operator risk, and mix 25% pooled operator risk into 75% partition risk.
- `R74_coverage.policy.cpp`: additionally adapt the original visible-demand weight from 15% to 85% according to recent *periodic next-PROBE* coverage.
- `R74_size.policy.cpp`: independent size-protection ablation on top of coverage; multiplies the eviction priority by `sqrt(1 + partition_bytes / max(1, memory_limit/(K*P)))`.
- Each corresponding `.cpp` contains the unmodified official-compatible framework surrounding that policy.
- `MySpillScheduler.cpp` is a copy of the coverage policy, for submission after official declarations. It is not a standalone executable framework.
- `generate.py` reproduces the four variants from frozen `tmp/dataset_score_audit_20261030/benchmark/sources/VanBest.policy.cpp` and `VanBest.cpp` plus `risk.hpp`.
- `source_hashes.json` records SHA256 for all four policy/framework variants.

The first three variants preserve VanBest's existing size/cost mechanisms: the priority contains inverse bandwidths plus the unchanged **1 microsecond proxy divided by bytes**, and subset loss includes `priority * bytes + 0.25 * bytes / write_bandwidth`. Thus VanBest already charges larger partitions' write cost. The fourth ablation adds explicit size protection; it must not be used to attribute improvement solely to refault learning.

## Clock, confirmation, and censoring

The only time coordinate is `q = hit_count + miss_count`, measured in completed/started PROBE ordinals. The official engine increments `miss_count` before `onPartitionMiss`. A miss and its following periodic callback can expose the same `next_op`, whose ordinal is `q+1`. Existing VanBest observed-demand deduplication remains unchanged. Refault completion is separately updated on the real miss, even if that demand was already seen through `next_op`.

Only returned, post-pruning SPILL/LOAD intents are saved. At the next callback, the intended partition must have the expected size and resulting residency before statistics change. A confirmed PROBE-phase SPILL opens a disk episode at the issuing callback's q. An actual miss closes it with one event. A confirmed prefetch LOAD closes it at the issuing LOAD q **without a miss event**. Long open episodes contribute exposure lazily, even without a return. Ignored actions do not open/close an episode.

BUILD spills are deliberately excluded. Their first miss after SWITCH is therefore not a refault sample in R74. There is no attempt to infer an unobserved phase-transition instant or interpret the repeated q=0 BUILD callbacks as rapid reuse. All phases' legal public state and all original VanBest choices remain available, but the new estimator covers confirmed evictions during PROBE only.

## Estimator and dimensions

For each partition and operator, maintain decayed exposure `E` (partition-PROBE ticks), miss events `F` (dimensionless), episode-start mass, active ghost count `A`, and last update ordinal. For elapsed `d`:

```
f = exp(-d / 512)
E <- E*f + A*512*(1-f)
F <- F*f
```

The operator's A is its number of active ghosts, so E sums each partition's at-risk Probe exposure; it is not merely global elapsed time. The formula is exact for piecewise constant A under continuous exponential forgetting, and is independent of callback frequency. Its e-folding horizon is 512 PROBEs. Event-driven begin/end operations first advance to their timestamp, then adjust A and optionally increment F. Empty statistics skip the exponential.

The smoothed partition mean waiting estimate is `(E + prior_mean)/(F + 1)`, in PROBEs, equivalent to inverse smoothed event/exposure hazard. The default prior mean is 64 PROBEs; operator modes use the operator's `(E_op + 64)/(F_op + 1)` instead. Risk maps into VanBest's dimensionless reuse scale as `64/(64 + mean_wait)`. The mapping scale 64 matches VanBest's existing age scale, but is a fixed heuristic, not a calibrated probability or measured time. No completed-episode-only average is claimed.

Operator variants mix 75% partition risk and 25% pooled operator risk. If neither applicable partition nor operator has any episode evidence, use original VanBest visible-demand reuse unchanged. There is no claim that partitions within an operator are statistically exchangeable; the pooling is a heuristic prior.

## Coverage adaptation

Only unique `q+1` next-PROBE ordinals seen in `onPeriodicAdjust` enter coverage. Miss callbacks, including their own legal peek, do not increase this coverage. The coverage tracker is independent of the original demand observer, so a periodic peek already seen by a miss callback still counts once as periodic visibility.

Coverage is an exponentially decayed unique-peek mass with 256-PROBE horizon, normalized by the corresponding finite-run dense coverage mass and clipped to [0,1]. Coverage modes set original-demand weight to `0.15 + 0.70*coverage`; fixed modes use 0.25. Both use original VanBest demand estimates (misses and legal next_op observations); aggregate hit_count never supplies fictitious hit keys. The normalization uses public Probe count, not hidden periodic interval B or total operation_count. Startup and mixed BUILD/PROBE schedules can affect this proxy.

## Preserved behavior and limitations

- The hidden true miss penalty is never read or inferred from input/output; all variants retain the original 1us proxy.
- VanBest's equal-size verified-cycle fast path, stride logic, lookahead protection, prefetch criteria, shortlist subset search, heap fallback, and prune behavior remain. The cycle fast path bypasses the new scoring, an intentional inherited limitation.
- Miss observations are selected by the policy. Next-op prefetch causes **informative censoring**: a known imminent demand is loaded before it can miss. Therefore this estimates policy-conditional realized refault risk, not unbiased demand intensity or a counterfactual miss distribution without prefetch.
- BUILD spills, engine behavior outside legal callbacks, hidden hit identities, and unseen future accesses are not learned.
- Size protection can prefer multiple small victims and does not guarantee fewer bytes or lower runtime; it is isolated for empirical attribution.
- Exponential operations add constant-factor cost. Complexity alone is not a decision-time result.

## Complexity and validation

New callback work processes only the previous returned action list, plus O(1) miss and next-peek bookkeeping. No new whole-state periodic scan is added. Per-candidate risk is fused into the existing release scan. Pooled operator state advances at most once per q, and common coverage calculations occur once per release. Storage is O(KP + K + returned-actions). Existing selection worst-case complexity is unchanged; active trained candidate histories may require one exponential each when q advances.

Validated with `g++ -std=c++14 -O2 -Wall -Wextra`:

1. All four complete official-framework files compile.
2. `test_risk.cpp`: cold ongoing exposure, completed misses, prefetch censoring, pooled exposure, same-q idempotence, callback-frequency invariance. The initial empty exposure implementation failed the cold-exposure assertion before implementation; final test passes.
3. `test_policy.cpp`: intent versus actual execution, ignored spill, confirmed spill/refault, prefetch censor at issuance time, BUILD exclusion, cross-callback dedup, consecutive same-key different-q demand, miss-only coverage exclusion, and pre-observed ghost demand followed by real refault. The coverage correction was verified with a failing miss-only-coverage assertion before the fix, then passed.

`run_tests.sh` regenerates artifacts, compiles tests, runs assertions, and compiles all four full programs. It runs no dataset benchmark and records no timing comparison.
