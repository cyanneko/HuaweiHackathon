# R74 formal comparison plan

**Goal:** Compare original VanBest, its p32 prior control, and at most two Root-selected reviewed R74 policies on the same frozen six complete R72 cases.

**Architecture:** Keep old R72 artifacts unchanged. Freeze control source/TU identities in this directory, accept final candidate source/TU/binary identities after Root selection, and validate that only the scheduler changes in the common official framework. Run existing Linux C++14/O2 noninstrumented binaries serially through the verified process-group runner. No compilation or policy execution during preparation.

**Spec:** Main's latest delegation: `tmp/r74_formal_eval` is exclusive; no shared Git writes; no new inputs/holdout/training. Wait for Root's final source freeze, review, and all diagnostic/compilation compute release before launch.

**Fixed data:** Six original R72 full 5M-operation cases; `cases.r72_frozen.json` retains the original bytes and input/meta SHA. No middle slicing, regenerated small-N inputs, or R71 substitution.

**Methods and repeats:** Two controls plus zero to two explicitly selected candidates. Default one execution per method/case; Root must freeze any small repeat count before launch (supported bound 1–3). No score-triggered repeat expansion. Repeats are averaged within each case; six cases never become eighteen independent samples. Timeout is fixed at 180s per execution; failures stay terminal and visible, with no automatic retries.

**Metrics:** Primary comparisons use fresh same-round VanBest and p32 cost ratios, per-case results and mean/P50/P90/worst. Record IO, miss counts, cumulative whole-case D and process wall time. If reporting case-mean-v1 against Naive, use `normalization_reference.r72.json` as an explicitly historical frozen auxiliary reference; no extra Naive run is silently added. Do not label full-case D as per-step latency.

- [x] Snapshot and fingerprint two controls and the original six-case identities; prove common framework skeleton.
- [x] Prepare a fail-closed binder and Linux runner for the final bounded matrix.
- [x] Check duplicate/missing repeat rejection and retention of failed repeats without launching a policy.
- [ ] Wait for Root's final candidates, repeat count, and compute release; freeze the exact campaign before admission.
- [ ] Execute the frozen matrix once, preserve raw outputs and failures, independently reparse and report; send final CPU release and artifact paths to Main.

**Review focus:** Unreviewed/instrumented candidates cannot enter; changed official engine cannot enter; absent repeat/baseline cells never change the denominator; terminal failures never get retried; historical Naive is never described as newly measured.

**Root scope revision before formal execution:** Three selected candidates R74_operator, R74_coverage and R74_size plus the two controls, exactly 30 cells and one run each. No partition candidate or additional repeats. Negative size/coverage results must remain visible. Root authorized compilation and checks now; formal policy execution still waits for final review and complete CPU release after paired B diagnostics.
