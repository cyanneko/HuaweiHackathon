# Frozen R81 mechanism ablation design — Root-approved preparation

Date: 2026-10-31. Candidate source text has been generated. No compilation,
native execution, or input-body scanning has been performed during preparation.
Root approved the nine-method design and preparation. Native compilation and
execution remain blocked until Root explicitly releases the exclusive CPU window.
All work belongs under `tmp/r81_ablation_20261031/`; frozen source, old evidence,
official framework, and shared Git are unchanged. No optimization or promotion.

## Parent and question

The question is the conditional contribution of an active mechanism in the final
R81 scheduler, relative to the complete final scheduler, plus the full scheduler's
same-round comparison with official Naive. Seven single-mechanism removals plus Full
and Naive give nine methods. Conditional removal effects are not additive causal
shares of the improvement and must not be summed.

Current readable parent: `tmp/r81_readable_20261031/MySpillScheduler.cpp`, SHA256
`ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65`.
Original parent: `tmp/r81_two_timescale/R81_op256_cond2048/MySpillScheduler.cpp`, SHA256
`7f65114b43dba6d5e3b5744fbee17a0b0f5b97a0d9b1b02702e3da6c8b0fb764`.
Published original commit: `a1ee48aee1af3b561efa2eacc5c68769a9a0dc83`.
Final semantic-name source commit: `3064e270fde0473810cd8c0e57b738ee48356254`;
main publication head: `d10f53b3353725a547a2fbbb8b5ad27e711b8eb7`.
Both known parent binaries have SHA256
`bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1`.
Authoritative new parent: `tmp/r81_named_20261031/MySpillScheduler.cpp`, SHA256
`2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`.
Its semantic macros replace the historical R names. Verify its Full ELF equals
the known parent during compilation. Line numbers
below describe the 849-line readable source, not a promise about later layout.

`R80_MODE=2` is active: `propose(...,2)` uses hierarchical frequency estimates.
`chooseAlternative`/`comparePlans` are inactive (`R80_MODE!=3` returns first).
`R74_SIZE=0` disables its additional size multiplier. Neither dead branch is an
ablation target. `R79_ADAPTIVE` only controls refault fallback, not main `g.share`.

## Frozen nine methods

1. **Naive**: exact official Naive policy already frozen in R87/stat protocol;
   retain official `std::sort` tie behavior. Same-round new measurements.
2. **Full**: exact final R81 behavior; verify same parent ELF where available.
3. **FixedShare075**: replace only `g.share = .75 / (1. + strength)` in
   `refreshSharing` (line 342) with `g.share = .75`. Keep heterogeneity, mass,
   squares, weight2, all sampling, fast operator marginal, and priors. Initial
   and insufficient-evidence sharing are already .75. Both main hierarchy and
   adaptive refault fallback consume the resulting fixed share. This tests
   heterogeneity-adaptive sharing versus fixed sharing, not all pooling versus
   none. Probe proof: unequal partition observations must produce nonzero
   heterogeneity but share .75 in this child and share below .75 in Full.
4. **UnifiedSlow2048**: change only `HASHJOIN_OPERATOR_HALF_LIFE` 256 to 2048,
   leaving partition half-life 2048 untouched. Retain hierarchical structure,
   fast counter machinery, all priors and sharing. This removes the difference
   between next-observation operator and conditional-partition horizons. Risk
   decay 128/512 and coverage decay 256 remain: do not claim all scheduler time
   scales are unified. Probe proof: use a fixed observed history with a gap and
   compare fast mass against the closed-form half-life 2048 value, while slow
   partition masses and sample ordinals agree with Full.
5. **NoPeriodicPrefetch**: in `onPeriodicAdjust`, keep `update`, all validations,
   `analyzeCycle`, and the capacity gate, then return the empty action vector
   before the release/prune/LOAD/record block (before line 843). Disable that
   complete action block; deleting LOAD alone would leave unintended spills.
   Demand `onPartitionMiss` is unchanged. Probe proof: on an eligible periodic
   state Full returns LOAD, this child returns no actions, and both advance the
   same sampling/coverage observation. Trajectories diverge thereafter: extra
   demand misses can expose different later next-op information and callbacks.
   Its effect is the complete periodic-prefetch policy, not isolated IO savings.
6. **NoNextProtection**: in cycle candidate filtering (line 644) remove only the
   `(o == next_op && pa == next_pid)` alternative; retain protection of current
   requested `(op,pid)`. Remove only the priority `+=1e12` for next target
   (lines 691-692). Keep next variables, sampling, main probability estimation,
   prefetch, required capacity, and current-demand exclusion. Probe proof: a
   fixed state where next is the cheapest otherwise eligible victim must allow
   that victim, including an explicitly seeded cycle route. This may induce
   extra misses/prefetch changes; it is not equivalent to hiding next-op.
7. **UnitMissCost**: replace priority's cost model (lines 684-685) with
   `priority = reuse / part.data_size`; replace subset loss (lines 714-715) with
   `loss += v.priority * v.bytes`. One mechanism changes: replace estimated
   read+write+fixed100 loss with a common unit per missed partition, and omit
   additional subset write cost. Keep next protection, top-four enumeration,
   capacity checks, bytes tie-break, pruning and all predictors. Resource
   density still divides by bytes: do not call this removal of all size use.
   The uniform miss unit is not an estimate of the hidden penalty. Probe proof:
   at fixed state/reuse, priorities equal reuse/bytes and subset loss equals sum
   reuse; varying read/write bandwidth leaves those terms unchanged, whereas
   Full's terms change. Test this on a non-scan/non-cycle state so the active
   cost path is reached. Removing only the density formula would leave the
   active `.25*bytes/write_bandwidth` subset cost and would be incomplete.
8. **NoStructurePolicy**: replace `uniform_cycle_ = (j == n)` in `analyzeCycle`
   (line 618) with false, and replace the local `scan` condition in `propose`
   (line 657) with false. Keep observe/history, successors/confidence,
   confirmed_edges, stride/step distances, recent ring and all samples. Thus
   neither cycle MRU nor scan reuse override can activate; normal hierarchical
   frequency/refault selection takes over. Periodic prefetch no longer receives
   the capacity-overflow exception supplied by a verified cycle. This is an
   explicit combined scan+cycle structure-policy ablation, not separate effects
   of scan and cycle detection. Probe proof: seed confirmed full equal-size
   cycle and a qualifying scan; observe the same learned statistics but false
   effective cycle/scan policy and the normal predictor route in the child.

9. **UniformOperatorMarginal**: in `ensureProbabilities`, replace only
   `(fast_operator_[op].mass + op_prior) / fast_denom` with `1. / k` for marginal.
   Keep counter maintenance, conditional partition estimate, g.share, priors,
   fallback and all observations. This removes operator hotness differences in
   the main probability marginal; it does not remove all hierarchical structure
   or operator information in other fallback paths. Probe proof: on unequal
   operator histories, estimated operator marginal is exactly 1/K while the
   fast counters and conditional partition/sharing state still match Full.

Root approved UnitMissCost exactly as above. Cold-start subset eligibility
`(evidence || read_bandwidth >= write_bandwidth)` remains; this is removal of
heterogeneous read/write/proxy-penalty scoring, not every bandwidth-dependent
branch. No post-result alternative will be selected.

## Implementation and effectiveness gate after approval

Freeze the final parent, seven exact textual deltas, generated source/TU hashes,
official framework/parser hashes, compiler/flags, and binary hashes in a new
manifest. Compile CPU-only `g++ -std=c++14 -O2`; official framework class
replacement only. No future sequence, hidden penalty, input files, or alternate
statistics may enter policy. The parent proxy stays exactly 100.

Before timing, statically check every generated child equals its parent after
reversing exactly its approved delta. Produce a readable patch per method.
Run only tiny synthetic callback tests for the effective changes listed above,
using an independently instrumented test copy to inspect private state. Timing
binaries are uninstrumented; tests do not read benchmark input bodies or select
new policy parameters. A passing small test establishes that a switch works;
it does not establish benchmark benefit. Full and Naive physical metrics will
also be compared with known same-input historical IO/hit/miss after the run;
historical decision time is never reused.

## Complete frozen evaluation matrix

Primary data at fixed commit `c65c7b32b06a5764ce9ad4881133a3c6eb33ed17`:

* dyna 1.0.0, all 12, tree `808ce8b11f57a1a96051f22aa572eceb82b1fba0`;
* final 2.1.0, eval all 72, tree `41197783dd577dfccf5b007a6ece67cbfb241e4b`.

Add stat 1.0.0 eval all 10 as an independent supplementary table, using the
existing `tmp/r81_stat_eval/protocol.json` case manifest/audit identities. It is
already observed, not a blind holdout. No final3 or other member data.

Nine methods × (12+72+10) × one repeat = **846 new cells**, serial CPU only.
Each suite uses lexicographic cases; rotate the fixed nine-method order left
by case index modulo nine. Fresh same-suite Naive denominator, fresh D for
every cell. Retain split/family labels. No sample substitution, retry/resume,
larger performance search, or automatic promotion.

Reuse R87 runner/guard design in new independent files and preserve old files.
Prepare all selections and source/ELF/input/metadata identities before timing.
Complete input SHA checks occur once in preparation, not during this design.
Stat uses the same nine-method core and full-grid gates after adapting its
case metadata; it must not silently inherit the old two-method/three-repeat
shape or old interpolation quantile rule.

Hard total wall allowance is **2200 s**, starting at the first formal native
preparation attempt, including compilation, tests, input preparation, all three
campaigns and finishing. Review waiting before that attempt is excluded. Local
loop caps are dyna 1000 s, final 500 s, stat 450 s; the global deadline always
takes priority. The remaining 250 s is preparation/finishing headroom, not a
separate additive allowance. Each cell timeout is min(60 s, remaining local and
global budget). Expected native time scaled from eight to nine methods is about
787.5+342+303.75=1433.25 s, not a completion guarantee. Report actual phase clocks.
If any budget/timeout/failure occurs, preserve the full planned denominator and
failure rows, publish incomplete status, and stop. Never shrink to successful
cells or call an incomplete matrix the formal score. Root may reserve these
budgets only after checking the Master CPU window.

## Scoring and deliverables

Official cumulative cost is defined as `C = IO + input_penalty*Miss + measured_D`.
Use the native stdout `Total_Score` field as authoritative C. Rounded printed
components only support a tolerance accounting check; never substitute their
reconstruction for C. This is a functional-policy ablation retaining state
maintenance and observations to reduce confounding; D differences do not measure
all computation that could be removed with the disabled module. Main attribution
uses same-round physical IO+miss cost and score, with measured D also reported.
Per-case score is `clip(10*(1-C/C_Naive),0,10)` where C and baseline are positive;
otherwise zero, with undefined denominator counted explicitly. Also retain raw
unclipped `10*(1-C/C_Naive)` and negative improvements. Primary result is
`(mean_score_dyna12 + mean_score_final72)/2`, never a pooled 84-case mean.
Stat10 remains separate. Full-minus-ablation score differences use the same
case and same-round Naive. Report both cost ratios and physical ratios.

Deliver per-cell metrics/status/evidence CSV, full per-case table, dataset and
family/original-split means, uncapped/raw points, IO, miss cost, real D, total
cost, P50/P90/worst ratios with nearest-rank `ceil(q*n)`, all negative cases,
source/TU/ELF/framework/parser/runner/input identities, stdout/stderr hashes,
campaign/selection/completion/finalization gates, and CPU-release evidence.
Require exact planned valid grid plus successful controller return even after
last cell, zero changed artifacts, no controller error and no active children.

One repeat supports descriptive measured D, not a stable timing superiority
claim. Request additional fixed repeats only if D becomes central to the
argument. An inactive mechanism on a suite may show no physical change; report
that without inventing a contribution. These are exposed local synthetic cases,
not official hidden tests. Ablation evidence and an algorithm/complexity account
can support an innovation submission, but cannot guarantee the innovation score.
