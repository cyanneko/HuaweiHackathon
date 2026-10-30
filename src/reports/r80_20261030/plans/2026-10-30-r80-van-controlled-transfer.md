# R80 Van Controlled Transfer Implementation Plan

> **For agentic workers:** Use subagent-driven development for isolated implementation and independent result review. The user authorized continued optimization and sampled iteration; do not modify frozen R79 or promote a candidate automatically.

**Goal:** Test whether Van's normalized next-frequency objective and paired-plan comparison improve R79 while retaining independent partition evidence and adaptive operator sharing.

**Architecture:** Four controlled candidates from frozen R79. First change only the legal penalty surrogate; then use a normalized next-only probability as the retention estimate, with and without operator sharing; finally compare the existing refault plan with the hierarchical-frequency plan using Van's expected-difference plus uncertainty guard. Raw partition samples remain independent.

**Tech Stack:** CPU only, MySpillScheduler, unchanged official framework, Linux g++ -std=c++14 -O2. Isolated tmp/r80* outputs; Master alone publishes Git changes.

**Spec / authorization:** User: continue learning Van's good ideas to improve score, with sampled iteration and decision-time constraints. Existing baseline source tmp/r79_adaptive_operator/R79_adaptive/MySpillScheduler.cpp SHA256 8eb171503ce6c30d8e99939dffef33b751dd96f7b276c1d4509c090d439d982d. Van paired100 pinned at 28094bdec34ff7110d9f1614703d0b09d383d4a6 in tmp/r79_reference; recheck remote for changes, do not silently change this experiment's reference.

## Approaches and chosen scope

- Penalty-only transfer is cheapest and attributable; fixed 100 microseconds is a heuristic from Van, never the input's hidden true penalty.
- Direct normalized next-frequency transfer supplies a common scale across operators; retain a flat control to distinguish operator sharing from this estimator change.
- Paired plans preserve the refault baseline when a next-probability model gives insufficient evidence. Two proposals add work, so this is an explicitly timed candidate, not presumed free insurance.

Do all four bounded controls. Do not tune coefficients on final_dataset, add a neural network, or run a full suite.

## Candidate definitions

1. R80_penalty100: R79 adaptive with only priority penalty coefficient 1 -> 100; leave next protection and all other literals untouched.
2. R80_next_flat100: same 100 surrogate; for ordinary PROBE victim ranking outside detected scans/cycles, replace refault/visible reuse with 64*p_i. p_i=(c_i+64/N)/(S+64), where c_i and S are independent next sample masses at one common causal clock.
3. R80_next_hier100: same as flat, but p_i=((1-alpha_o)*c_i + alpha_o*S_o/P +64/N)/(S+64), with R79 alpha_o=.75*(1-H_o). H and independent c_i retain the R79 implementation. Operator mass S_o is a sum of raw independent next evidence, never a mixed-heat feedback.
4. R80_paired_hier100: refault penalty100 base action set vs hierarchical-next candidate. Prune both legally, then switch only if immediate_delta+64*mean_delta+2*sd<0. Evaluate the signed difference with **flat** next probabilities, not the hierarchical ranking itself. No switch for non-PROBE operators, detected scan or equal-size cycle. Record actual intents only for the final returned actions.

Frequency queries use q*=max(current Probe ordinal,last accepted next ordinal) so lazy masses share one time and never decay backward. S=sum operator mass at q*, W2=sum operator squared sample weights at q*, n_eff=S*S/W2. Existing stored group/partition times allow an O(K+KP) scan, no stream replay or per-candidate full state copies. A cached probability vector shared by both proposals is preferred.

Paired delta on changed spill IDs: sign=alt-base; coefficient=sign*(bytes/read_bw+bytes/write_bw+100). Immediate adds sign*bytes/write_bw and known-next exposure sign*(bytes/read_bw+100) when applicable. mean=sum p_i*coefficient; second=sum p_i*coefficient^2; sd=64*sqrt(max(0,second-mean^2)/(n_eff+1)). This inherits an IID-inspired uncertainty proxy, not a probabilistic guarantee under policy-selected next sampling. Build/current miss do not increment next frequencies. Keep next ordinal dedup, legal victim protection and final LOAD behavior.

Van's original history proposal ranks using history priority but scores its top4 subsets using frequency priority. Do not call that a pure history control. Our paired base is explicitly the R79 refault planner; document the difference.

## Data and screening

- Reference all16 R79 TRAIN inputs unchanged; generation of 12 new100k TRAIN was frozen before outcomes using 6 seeds x none/hot, penalty1/100/1000. Two rare-hot inputs failed the generator's partition<=M constraint. Preserve failures and original manifest; do not replace seeds or partially test invalid inputs. The current valid training panel is26, not28; report original16/new10 and paired/unpaired status separately.
- Six methods on26 cases: R79, Van, the four controls; serial, one repeat, input/source/binary identities fixed. Active runner watchdog180s, official per-case60s. Score-cost includes actual framework penalty and measured D; physical ratios are a separate diagnostic. With no same-run Naive, do not invent contest normalized scores for training.
- Freeze selection before running. Rank candidates by new10 mean cost ratio to R79, requiring new10 mean<1, old16 mean<=1.05, all26 worst<=1.25, and mean D<=2*R79 as eligibility guards. All26 baseline cost denominators and baseline total D must be positive for eligibility; do not select using a smaller ratio denominator. Keep all results including failures. If none qualify, report that and retain baseline rather than relaxing thresholds after outcomes. Advance at most two eligible candidates.
- Validation uses24 fixed stratified final2.1.0 cases disjoint from the previous R79 final24; use seed r80-final-sample-v1, 9 Zipf/9 hotspot/6 lognormal, tertiles of remaining cases by N. Freeze selection independently of outcomes. Run same-batch Naive/R79/Van plus selected candidates, at most120 cells, serial180s active budget, nearest-rank P50/P90/worst and all individual scores. This is a new sample for this experiment, not guaranteed historically unseen. Do not retune on it.

## Tasks

- [ ] Code audit and precise source mapping; Root review before final implementation freeze.
- [ ] Implement four isolated sources, own production TUs and meaningful tests: probability sums, decay/dedup, independent base, flat-vs-hier limits, no-evidence guard, signed paired differences/next exposure, legal actions and final-only intents.
- [ ] Build C++14/O2 and verify no framework modifications; record all source/TU/ELF identities.
- [ ] Freeze valid TRAIN and sampled validation manifests, retain invalid-generation records; then run serial TRAIN screening.
- [ ] Freeze selected candidates by predeclared rules; run sampled final only after publishing activity pauses for native timing.
- [ ] Independently reparse outputs and recompute per-case/aggregate scores, distributions, D, and failures. Write Chinese report and publish through Master; no default promotion.

## Review focus

- Avoid giving a global probability scale to per-operator-only normalized counts.
- Never use true penalty, future operations, hit identities absent from callbacks, or evaluation labels in the scheduler.
- Existing next data at q+1 must remain causal and not be counted twice by current miss/periodic callbacks.
- Plan comparison must not record unrealized spill/load intents or modify real risk state twice.
- Missing/invalid planned data and failed policy cells must remain visible; do not shrink final score denominator after observing outcomes.
