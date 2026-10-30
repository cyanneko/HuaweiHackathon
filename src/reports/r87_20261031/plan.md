# R87: one lightweight Fixed-share operator mixture

This plan implements the user's continuing request to improve the mathematical scheduler, borrow useful Van ideas, include Van in full comparisons and keep decision time visible. Latest steering is authoritative: **primary data are original dyna1.0 all12 and final2.1 eval72**, as defined in docs/评测数据版本约定_20261030.md. Final3/R86 is supplementary only.

## Hypothesis and one fixed candidate

R85 exposed a tradeoff: the faster operator marginal with prior8 improved dynamic dyna but hurt the static final2.1 family averages. Try an online mixture of fast and slow operator forecasts, driven by predictive performance on legally observed next-PROBE labels. Do not combine this with the earlier noise-discrepancy gate, modify the conditional partition estimator, run an alpha sweep, or introduce a neural network.

Primary reference: Herbster and Warmuth (1998), *Tracking the Best Expert*, author PDF https://mwarmuth.bitbucket.io/pubs/J39.pdf, Figure1 and Section3. Use the sharing-to-other-experts convention. The categorical adaptation and scheduler design are ours; prediction-loss guarantees are not IO/miss/decision-cost guarantees. Proposal and independent reasoning review are in tmp/r86_reference/fixed_share_operator_proposal.md and fixed_share_review_addendum.md.

Candidate name R87_fixedshare_op. Parent is the immutable R85_fast_prior8 class, SHA256 a0ebc08399a8cd8c039dae59a779231df0c35306af3ea3269df3067c321779b5. Only the operator marginal and small supporting statistics change. Keep slow half-life2048, fast half-life256, fast prior8.009479828345365, slow prior64, adaptive conditional pooling, horizon64, proxy100, action checks and framework unchanged.

## Exact online update

Maintain two independent persistent global observed masses Tfast/Tslow and a common last clock, plus the fast-expert weight w initially0.5. Existing ensureProbabilities totals are temporary query sums and must not be repurposed as these persistent masses.

For a genuinely new accepted next-PROBE ordinal q, perform the following before incrementing either selected operator count:

1. Preserve the existing ordinal dedup rule. No repeated/old ordinal may update predictive loss, share, weight or counts. Pure lazy decay of existing statistics is not a new learning trial.
2. Advance both global masses and the selected operator's fast/slow masses to the same q using the existing decay factors; never rewind from an accepted next q+1 to current miss q.
3. Compute positive forecasts for the observed operator o from pre-insertion counts: pF=(fast[o]+8.009479828345365/K)/(Tfast+8.009479828345365); pS=(slow[o]+64/K)/(Tslow+64).
4. Set r=w*pF/(w*pF+(1-w)*pS); then w=alpha+(1-2*alpha)*r with alpha=1/256. This directly evaluates the log-loss multiplicative update at learning rate1 without log/exp calls for expert weights. Share once per accepted observation, not per global step or skipped observation.
5. Add the accepted observation once to both global masses and the existing selected operator/partition counts. Keep counts and cache invalidation coherent.

At the ordinary common probability query clock, mix operator probabilities w*pF_query+(1-w)*pS_query, where the two query forecasts use their matching prior and decay scale. Multiply by the unchanged slow conditional partition distribution. No extra K*P scan and no second spill proposal. Independent persistent totals support O(1) extra work per accepted observation; existing O(K) query aggregation may be retained. Reset masses, common clock and w when dimensions reset. Use finite/nonnegative defensive guards; do not claim numerical bit identity to either endpoint policy.

Known-next information is legal, but its predictive score must use counts excluding that label. Observed labels are selected by policy-dependent callbacks: the predictive comparison is on that realized observation sequence, not all hidden hits or independently simulated policy trajectories. Learning a better probability forecast may still worsen the size/bandwidth-dependent spill objective.

## Correctness before timing

Work only in new tmp/r87_fixedshare and its test/review folders; do not edit old classes, caches, reports or shared Git. Preserve exact parent and normalized official-framework hashes; build CPU-only with g++ -std=c++14 -O2.

Create meaningful deterministic tests before implementation and retain an expected pre-change failure where applicable. Tests must check actual integrated scheduler statistics, not merely a duplicated update formula: pre-insertion scoring, duplicate ordinal, irregular gaps and common-clock oracle, K1, identical forecasts from w0.5, recovery toward0.5 from a nonuniform weight when forecasts agree, normalized probabilities and weight bounds, global totals matching independently summed weighted observations, and dimension reset. Use small hand-built observations/long-gap cases, no benchmark-sized training. A uniform-pool recurrence or score-after-insertion implementation must fail the relevant oracle. Test access scaffolding must never enter the submission class or official runtime.

One bounded compile/test window of90 seconds after Root release, preserving all failures and logs; do not auto-retry a timeout or alter source after freezing a tested producer without a new version. Compile the official TU, verify framework identity and save compiler/environment/ELF/source/TU identities. Producer release must be READY before performance preparation. Root and an independent reviewer inspect the final changes.

## Full primary comparison, frozen before candidate performance

Use eight methods: Naive, R75_dense_switch, R80_next_hier_fast100, R81_op256_cond2048, Van_latest, R85_fast_prior8, R85_hier_anchor, R87_fixedshare_op. Existing methods preserve their exact R85 identities. R80 paired's earlier complete R85 results remain available; it is not part of this focused new comparison. No candidate is removed based on early performance.

All dyna12 plus all final2.1 eval72, fixed datasets commit c65c7b32b06a5764ce9ad4881133a3c6eb33ed17, trees808ce8b11f57a1a96051f22aa572eceb82b1fba0 and41197783dd577dfccf5b007a6ece67cbfb241e4b. This round reruns its chosen controls and candidate together:96+576 new cells, one repeat, serial rotated method order, same-campaign Naive. No final3 inputs or reused D in the primary R87 comparison. Internal execution-loop budgets1100 seconds dyna/650 seconds final, per-cell60 seconds; setup/teardown hashing is outside some loop accounting. No concurrent heavy work. No performance retries, seed replacement or source changes after results begin.

Reuse the established execution core/completion guards; adapt only fixed method configuration and immutable inventory/producer binding in a new wrapper. Prepare and hash both complete selections before timing. Require every expected valid row, unchanged dependencies, successful controller return even after the last cell, zero active children and finalized gates. Preserve failures and partial evidence.

Cost includes simulated IO, evaluator miss penalty and actual cumulative D; scheduler sees neither hidden penalty nor future sequence. Report per-case clipped10-point score and raw, each dataset mean,50/50 combined objective, D, physical costs, nearest-rank P50/P90, worst and worse-than-Naive counts. Direct parent comparison is R87 versus R85_fast_prior8; also report against R80 hierarchy, R81 and Van. Include all cases and tail counterexamples. No global50cap, no2xD hard veto, no default promotion, no official-hidden-distribution claim. A single timing run has no uncertainty estimate.

Master remains the sole shared Git writer. Publish exact version, protocol, source, result logs, per-case/group summaries and report on source/cyanneko; keep failed candidates. The existing draft PR handles shared default-branch documentation. Preserve the old-data-primary / new-data-supplement distinction in the evaluation index.
