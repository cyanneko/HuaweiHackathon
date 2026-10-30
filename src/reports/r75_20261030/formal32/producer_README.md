# R75 formal evaluation preparation

Static preparation only. No compilation, policy process, WSL startup, warmup, or performance test has been started. Old R73/R74 evidence and R72 holdout remain untouched.

Reuse the already verified `common.py` and serial `run_formal.py`; this copy changes only the campaign gate, case count (8), maximum method count (4), native output prefix and first-case wall-budget multiplier. No new evaluation framework or test suite is introduced.

The input set is the original six complete R72 cases plus:

- `r75_large_04_slow_staggered`: K8/P16, B10000, 5M operations, requested pressure6, actual5.999549.
- `r75_large_06_burst_staggered`: K4/P64, B17, 5M operations, requested pressure12, actual12.276227.

These two are same-seed paired scale checks of medium fresh04/fresh06. Only the external N parameter was changed; the generator recomputes phase thresholds and planned tuple size from N. They are not literal extensions of the medium text streams, extra independent seeds, official tests, or holdout cases. Do not combine medium/large pairs as independent repetitions. Report the original-six and paired-two subgroups clearly alongside any full-eight summary.

`cases.prepared.json` records the eight input/meta identities and parser-only counts. Absolute Linux paths in the supplied large-data manifest are normalized to workspace-relative paths. New metadata SHA values were checked; large input bytes were not reread during preparation. Full input hashes are checked by the runner when execution is authorized. Evaluator counts/penalties never become policy arguments.

Final method IDs, source/TU/ELF fingerprints, selection and precommit remain unbound. Root must freeze at most four methods and one run per method/case, then explicitly release diagnostic/compilation compute and Master Git/upload/large-file activity. No executable `cpu_release.json` exists yet. The maximum matrix is32 cells; no extra methods or repeats are added automatically.

Keep actual per-process wall time distinct from cumulative decision time. The60s problem wall limit is checked explicitly;180s is only the internal watchdog. Failures and every original output remain visible and are not retried or silently excluded.

No eight-case Naive-normalized score can be reported without eight matched baseline references. Historical six-case Naive data must not silently stand in for the full eight-case result. Primary comparisons should use Root's selected same-round baseline and preserve all eight cases.
