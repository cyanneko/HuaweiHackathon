# R78 scale one-deviation teacher: completed diagnostic

Four predeclared TRAIN strata, one anchor each, native R75 continuation after one forced complete ordered action. Execution completed in 14.36 seconds under the single 90-second budget; 4/4 anchors and 11/11 planned branches completed. No retries, replacement anchors, dev evaluation, model training or adapter compilation. `cpu_released.json` records no active children.

| Stratum | Callback index | Raw index | Candidates | R75 suffix regret (us) |
|---|---:|---:|---:|---:|
| fast_shared, pressure 3, O | 413 | 28290 | 3 | 6,289,760.910 |
| fast_staggered, pressure 3, M | 22962 | 81344 | 3 | 3,366,497.255 |
| slow_shared, pressure 12, O | 28 | 3363 | 3 | 0 |
| burst_staggered, pressure 12, M | 35856 | 81938 | 2 | 586,378.755 |

Regret is original R75 forced-action suffix cost minus the least cost among this anchor's at most three tested actions, all with actual R75 continuation. The denominators are four selected anchors / eleven tested branches, including four controls; three anchors have a strictly better tested action. This is a stratified local diagnostic, not natural-frequency evidence, a complete action optimum, or the measured benefit of deploying a changed scheduler.

`config.json` and `selection_protocol.json` freeze input/source/binary identities and selection before any native execution. Minimum selection hash is taken over **all** baseline callbacks of the specified kind, without candidate-count or outcome filtering. `selection.json` freezes restored anchors and candidates before forced branch costs. The final stratum has only two distinct selected actions; it is retained rather than replaced. Candidate feature vectors are recomputed on the final candidate pool to keep rank features consistent.

Native baseline uses the validated fast-ledger binary in non-FAST mode, producing full original-R75 callback trace plus exact final write/read/miss totals in one process. Python reuses the frozen corner helpers to restore only each chosen prefix. It checks callback arguments/q along that prefix and the public physical hash at the selected point; it does not perform every-callback full physical hashes or Python R75-private-state reconstruction. The native forced call checks joint callback identity and private prehash. The auxiliary R65 feature history remains distinct from R75 private history.

All four original-action controls match their baseline final exact ledger, hit count and callback count, with exactly one override. FAST control branches do **not** produce a complete suffix trace equality comparison. Candidate actions are checked at the selected state using the existing strict ordered-action legality helper; the unchanged official engine executes and enforces capacity throughout native continuation. Input phase validity, all-PROBE last callback, successful normal completion, unique END/LEDGER and exact override count are required, otherwise no label is accepted.

Suffix accounting subtracts the exact restored anchor prefix ledger from each native EOF ledger; an M-entry prefix already contains the triggering miss. Integer G uses write_bytes*R + read_bytes*W + misses*penalty*W*R. Reported microseconds divide G by W*R; rounded native stdout IO is only a consistency check. Exact native ledgers rely on the previously validated 89-branch ledger implementation and its runtime preconditions, not an independent Python replay of each new full suffix. Instrumented D is excluded.

Read `report.json`, `results.json`, `selection.json`, individual `anchors/`, `branch_results/`, and `forces/` for machine-readable evidence. The source and binary hashes are frozen in `config.json`. Scope and evidence limits should accompany any downstream label use.
