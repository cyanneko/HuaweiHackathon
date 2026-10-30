# R87 runner ledger

Plan: docs/superpowers/plans/2026-10-30-r87-fixed-share-operator.md, SHA 0e3641da02e86d76ebba01f3c7a0cfaed6ff83a534d8af78f25c0d933eaf8c0d.

Scope: wrapper only; no scheduler implementation, performance, compile, data generation or large input scan. Root prepares/runs. Producer owned by fresh_data. All writes limited to tmp/r87_eval and tmp/r87_runner_review, no Git writes.

Ruling: explicit isolated-directory ownership and no Git mutation override skill worktree/commit mechanics. Retain ledger and all evidence instead of cleanup.

Interface: existing seven exact R85 methods + one new single R87 producer; wait for producer READY and Root approval before release freeze. Dyna12 and final2.1 eval72 both freshly timed, same-round Naive; no historical timing reuse or final3 input.

Task 1 in progress: meaningful parent scorer RED against actual new eight-method row matrix, then configuration-only scorer adaptation; inherit completion/identity protocol checks.

Task 1: RED observed at old R85 scorer's required-paired reference guard on actual new 576-row matrix; adapted config passes new R87 parent-score delta test and inherited full suite on Windows and Linux.

Pre-execution repair: real metadata-only dyna inventory check rejected an overbroad new `<LOCAL_TEMP>` path assertion. Frozen R85 dyna paths actually use original R72 raw cache; final2.1 paths use d70. Preserve both exact historical dictionaries and hashes. Removed that assumption only for dyna; RED traceback retained in inventory_red.stderr. No data files changed.

Environment: first unprivileged WSL Python invocation returned Wsl/E_ACCESSDENIED; authorized elevated WSL pure-Python protocol invocation succeeded. No scheduler/compile/large-input read in either invocation.
