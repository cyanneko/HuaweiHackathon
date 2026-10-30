# R79 final_dataset 2.1.0 stratified sample

Current scope supersedes the initial full72 request: **24 cases × 5 methods × one repeat = 120 cells**, serial CPU. This is an initial sample measurement, not a full72 result or ranking. No train/diagnostic/dyna/2.0 inputs are added.

Dataset/evaluator pinned commit: `f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246`. Evaluation VERSION is 2.1.0. Source rules and the actual parser/normalizer are copied byte-for-byte under `dependencies/` from that commit, rather than inherited from an older branch's aggregation.

Selection uses all72 declared eval entries, without consulting scores. Within each family, sort `(operations, case_id)` and split at integer floor boundaries `j*n//3`. Within each size tertile, choose the smallest SHA256 of UTF8(`r79-final-sample-v1` + case_id). Zipf/hotspot each select3 per tertile; lognormal selects2. Totals are9/9/6. Cases execute in case_id order; each case rotates the fixed method order left by case_index modulo5. `selection.prepared.json` records every stratum population/member and selected hash before any native execution.

Five methods are official Naive, frozen R75, independent-fixed75, adaptive R79, and frozen Van paired_penalty100. Their source/TU hashes and common official-framework skeleton were checked during preparation. Runtime rechecks ELF/source/TU identities and copies only tiny binaries to an existing Linux-native benchmark directory. Inputs reuse the supplied cache; no500MB input copy or regeneration is done.

Execution cannot start until `selection.json` and `input_gate.json` bind the Master input-pass contract and completed panel CPU release. The original user and Root have authorized this experiment; this gate is an artifact/CPU readiness check, not an additional approval request.

Each cell retains process metadata, stdout/stderr hashes and parsed metrics. Official per-case wall limit is60s. The controller separately caps its campaign at180s; a child clipped by remaining controller time is marked controller interruption, not an official60s timeout. Failures do not remove later planned methods/cases or shrink the denominator. The controller does not retry failed cells or automatically resume a partial campaign. STOP_REQUESTED or a signal preserves existing cell artifacts and kills owned child processes.

Primary score uses Total_Score = IO + penalty×misses + measured D. Current pinned evaluator computes `clamp(10*(1-C/B),0,10)`, with C=0 or B=0 scoring0. Each method requires its full24-case valid matrix with same-batch Naive before its main aggregate is available. Missing/failed cells give unavailable/null main aggregates; a separately labeled failure-zero diagnostic retains denominator24 only when all24 Naive baselines are valid. It is never presented as a complete valid local ranking.

Outputs include per-case scores/costs/D, unbounded sum of case scores, case mean, physical cost, score and cost-ratio P50/P90/worst (nearest-rank percentiles), failures and missing counts. Instrumented diagnostic timing is not used. One repeat leaves timing noise unresolved; this sample cannot predict the full72 or official hidden-case score. The underlying2.1.0 collection includes previously exposed regression inputs, so this is not claimed to be an untouched blind test.

Preparation checks: `python test_parsing.py`, CLI help and Python syntax only; these execute no scheduler. `run.py --summarize-only` is also read-only with respect to policy execution.
