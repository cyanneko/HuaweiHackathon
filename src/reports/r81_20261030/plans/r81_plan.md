# R81: Independent fast operator and slow partition distributions

The user requests continued iteration after the R80 report, including original dyna regression, and prioritizes final score including decision time. R80 has completed. Its hierarchy is best on final24 and the equal-weight two-dataset sample, but paired is best on dyna6. No default is changed automatically.

## Frozen experiment design

Parent: `tmp/r80_lazy_transfer/R80_next_hier_fast100/MySpillScheduler.cpp`, SHA256 `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`. Leave all parent/framework bytes unchanged. Read the formula and observability review in `tmp/r81_reference/two_timescale_design.md` (SHA256 `abbe570425c0cbd132a0475e8ff590aee39e64f9ee21105714816101d8d95205`).

Produce exactly two variants, `R81_op256_cond2048` and `R81_op512_cond2048`, under `tmp/r81_two_timescale`. Preserve independent slow partition counts and heterogeneity at half-life 2048; add independent deduplicated visible-next operator counts F with half-life 256 or 512. At common probe ordinal q*, replace only the operator marginal:

`p(o,p) = (F_o + 64/K)/(F + 64) * ((1-a_o)c_op + a_o*S_o/P + 64/(KP))/(S_o + 64/K)`.

Keep a=.75*(1-H), the 64-request prediction horizon, 100us proxy, candidate search, BUILD/scan/cycle guards and finalized-action accounting unchanged. No paired or wider subset search in this experiment. The fixed64 prior shrinks the faster mass more strongly; explicitly report this confound rather than claiming a pure time-constant ablation. Do not tune the prior in this round.

Fast counts update only on accepted next ordinals, not on current misses or hypothetical alternatives; use common monotone q* clocks. Add O(K) marginal preparation and lazy per-partition queries, no resident-only normalization, no feedback of mixed heat into raw counts. Do not read hidden penalty, future input, total N or private framework state.

## Verification and ownership

Implementation agent owns only `tmp/r81_two_timescale`. Root owns evaluation and report. Data agent owns only `tmp/r81_data_panel`. Master remains sole shared Git writer. Run no performance jobs outside Root's released serial window.

Before performance, test direct-decay probability oracles, nonnegativity/normalization and operator marginal sums, conditional independence, duplicate next/current-miss cases, future-to-current clock monotonicity, empty/K1/P1/long-gap/epoch-wrap cases, a 2048 test-only identity oracle, hotspot switching and rapid reversal, and inherited callback/action legality plus BUILD/scan/cycle guards. Expected-red evidence should identify the missing fast marginal in the parent. Linux C++14/O2 builds, source/TU/framework hashes, complete test logs and release manifest. Compile/test budget 90 seconds, no repeated hidden retries; preserve failures and state any fix.

## Data and screening

Reuse 26 frozen R80 TRAIN as regression. Prepare 12 new TRAIN and 6 fresh reserved DEV, all 150k operations, from independently seeded slow/fast/burst x shared/staggered generators with ordinary and rare within-operator hot profiles. Freeze exact seed/config list before generation. Keep generated failures as failures, no outcome-driven replacements. Data agent provides metadata and full input audits; no algorithm performance during generation.

Run TRAIN only first, using same-run Naive, R79, R80 hierarchy parent, R80 paired and the two new variants (6 methods). If all 12 new inputs validate, 38 x 6 = 228 cells; otherwise explicitly report the smaller valid panel. Every cell uses the unchanged official framework, CPU serial, one repeat, 60-second official per-case wall limit and 240-second internal controller budget. D is included in cost and score; no hard D-ratio veto.

Primary new-candidate selection: highest new-TRAIN mean `case-mean-v1` score relative to same-run Naive, greater than parent; old26 mean-score decline no more than 0.05 points; all-TRAIN worst total-cost/parent <=1.25; complete valid cells and denominators required. If eligible, advance at most one variant, breaking exact score ties by lower D then name. Report old26 and new12 separately, score gains and raw unclipped improvements, median/P90/worst cost ratios and D. Do not conflate mean cost/R79 with contest mean score; they need not rank methods equally.

Only after candidate identity freezes, run fresh DEV6 with Naive/R79/parent/paired/chosen variant (30 cells if one advances). If no candidate passes, publish the failure and proceed to a separate algorithmic idea. Old final24 and original dyna6 remain explicitly exposed regression panels; no blind-test claim. To justify promotion beyond sampled dev, use a separately declared regression check with same-run baselines and equal weighting of dataset-level means. Do not change default from TRAIN scores.

## Deliverables

R81 report with exact formulas, fixed inputs/identities, failed attempts, all per-case scores, aggregate definitions, timing and limitations. Publish via Master after independent review, alongside R80's completed dyna supplement. Continue into the next controlled experiment instead of stopping after a report, as requested by the user.
