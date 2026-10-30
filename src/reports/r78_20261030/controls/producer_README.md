# Temporary R78 single-fit controls

Frozen parent: `tmp/r75_release/MySpillScheduler.cpp`, SHA256 `cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458`. Parent bytes unchanged. These are diagnostic heuristic controls, not promoted replacements.

- `R78_build0_singlefit`: only Overflow with `hit_count+miss_count==0` attempts the single-fit rule. This is a q=0 gate, not an additional phase gate.
- `R78_overflow_singlefit`: all Overflow callbacks attempt the same rule.

Compute `need=z-(memory_limit-memory_used)`. When positive, choose the smallest positive resident non-target partition whose size reaches need; equal sizes use ascending `(op_id,partition_id)`. Exclude the next operation's partition when its type is PROBE, op index valid, operator phase PROBE, and partition count positive. If no fit or need is nonpositive, invoke the unchanged original release path. The original fallback retains its original next-partition scoring semantics; the new strict exclusion is specific to the single-fit attempt.

Only the Overflow callback's release selection changes. Existing activation, update, pruneSpills and record of the resulting actions remain. Miss, Periodic, prior/refault, dense-switch, bookkeeping and official engine bytes remain unchanged. A selected fast-path spill naturally skips original release's scoring/cache work; no extra cleanup or other scoring change was added.

The full translation units use the existing frozen R74 official-framework prefix/suffix, with only the scheduler replaced by each variant. Production binaries are uninstrumented C++14/O2. Public test headers expose members only for the small tests; they are not used in production binaries. Binary/source/TU identities are in producer.json; release.json binds producer and test evidence.

TDD: the original R75 fails the first minimal-fit assertion, then both variants pass the same targeted test suite. No performance measurements or training were run. The focused cases cover minimum fit, stable equal-size op ordering, next and target protection, nonresident exclusion, no-fit fallback, no needless spill, q>0 A original behavior, actual spill intent confirmation, and BUILD exclusion from PROBE risk.
