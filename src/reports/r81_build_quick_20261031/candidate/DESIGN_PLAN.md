# Cold-start BUILD best-fit: approved single-candidate plan

Root approved 2026-10-31. One candidate `BuildBestFit`; no parameter search or promotion.

Only `onMemoryOverflow`: after original `update(s)`, if hit+miss=0, next is not PROBE, all operators are BUILD, and need=required-free_bytes>0, scan all resident positive-size partitions excluding current insert target. Choose the first minimum-bytes partition with bytes>=need. If found, invalidate probability cache and emit one SPILL; otherwise original release fallback. Original prune/record/return remain in place. No changes to PROBE/mixed phase paths or official framework.

Engine facts: SPILL writes current bytes and marks nonresident; later BUILD INSERT writes each new tuple directly; LOAD of BUILD is ignored. Therefore best-fit minimizes immediate write only among eligible single victims. It can trigger later overflow sooner, and future inserts to its selected victim remain disk writes. No total-cost guarantee, no anti-thrashing claim; no future input access.

Files: `tiny.cpp` first specifies differentiating behavior, ties, exclusion, fallback gates and actual official-engine BUILD write semantics. `prepare.py` derives one candidate and exact official TU from immutable named parent. `producer.json` records untested hashes; engineer-owned `tmp/r81_build_eval_20261031/` owns native compilation/tiny RED/GREEN, immutable release and 66-cell run after Root GO.

Checks: compile tiny with `-DEXPECT_PARENT_RED` and require exit3/minimum_single_victim_beyond_parent_top4; compile without and require `TINY_BUILD_PASS cases=10`. Verify exact suffix/prefix and delta. Tiny compilation/execution remains HOLD until Root GO. Production candidate must compile C++14 -O2 CPU only. Tiny is authored before candidate; RED/GREEN execution is deferred until authorized native window.

Experiment fixed by Root: Naive/Full/BuildBestFit; dyna1.0 all12 + stat1.0 eval10, 66 new cells, one repeat, same-round D/Naive, 60s/cell, no retry, 900s total formal window including compilation/check/prepare/run/audit. Dataset means separate, optional50/50 labelled different denominator from old dyna+final leaderboard. No old final72 or ablation rerun. No main replacement.
