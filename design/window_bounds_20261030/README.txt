Scalable offline lower-bound analysis for Task 20

VERIFIED CHECKPOINT (2026-10-30): 10 hand + 30 random formal toys passed;
all 785 member cases computed, zero skipped/errors, all bounds <= the same
case's SDK Score. All 185 old suffix-relaxation raw bounds cross-checked.
suite_verification.json binds members_standalone_r3 / mode113, source and inputs.
The overall C/LB is about 2.679862: the bound is loose and does not certify
near-optimality or attainable savings. Numerical divisions are not machine-certified.
Run the commands below only after all SDK timing has stopped. This directory
does not change the existing offline_bounds_20261030 suffix tool or evidence.

Files
 window_bound.cpp: C++14 two-pass streaming parser, F+E window segment tree,
   independent incompatible-path tree, and whole-case byte conservation.
 verify_window_bound.py: explicit toy/saved-SDK verification; no online solver,
   training, fitting, or SDK timing invocation.
 proof.txt: scope, recurrences, proof and numerical caveats.

Run from the project root after review (Python 3.10+, g++ available):
 python design/window_bounds_20261030/verify_window_bound.py --toys --compile
 python design/window_bounds_20261030/verify_window_bound.py --suite --tag members_r9 --mode 113

The second command reuses the compiled binary. A prebuilt --binary PATH can
replace compilation; its hash is recorded, but external flags are not certified.
Both --toys and --suite are explicit execution modes. Existing report files are
never overwritten: select a fresh --out PATH for repeated evidence. --toy-dir
can similarly select a unique generated toy location. Generated input toys are
local verification artifacts and should not be added to the dataset repository.

Direct offline executable CLI:
 window_bound INPUT.txt [MEMORY_BUDGET_MiB]
The default memory budget is 512 MiB. Estimated working allocation is roughly
64*suffix_probe_count +256*nonempty_partition_count +65536 bytes. A budget excess
or allocation failure yields status=skipped and null bounds, never a fake zero.
Input is read twice; no N-operation vector is stored. The fixed-size suffix
includes every PROBE after the last SWITCH, including empty targets. Runtime
is O(N + n log n + n log Q); memory is O(n+Q). Formal n<=5,000,000 needs about
320 MB for the window tree, plus small fixed overhead. --memory-mib controls
the budget passed by the verifier, and --timeout controls each offline call.

Outputs and checks
The C++ JSON reports int64 read/write byte lower bounds, adjacent F, window E,
joint window and independent path bounds, raw long-double IO bound and a
downward-adjusted numerical lower_bound. The integer values are exact under
the stated proof. Floating-point values are explicitly not machine-certified.

Toy mode first audits formal input legality (M>=64 MiB; tuple<=1 MiB). Ten
manual cases and thirty seeded random Q<=5 cases compare exact integer outputs
with direct O(n^2) window/path recurrences. An independent feasible-cache-mask
S/T DP finds the minimum suffix READ bytes with free initial cache and actual
periodic callback schedule; the new read lower bound must not exceed it.
Fraction arithmetic checks the final bandwidth divisions. Empty/probe-key0,
no suffix, equality at M, alternating full-M blocks, a small bridge between
incompatible blocks, no phantom anchor, and cross-operator prefix are covered.

Suite mode reads the frozen saved 785-case x3 SDK report for a selected --tag
and --mode (defaults members_r9 /113). It audits inputs using the pinned public
auditor, verifies input and metadata hashes against the report manifest, checks
the complete (member,case,repeat) grid, and uses per-case arithmetic mean Score.
It runs ONLY this offline bound executable and compares each result to saved
SDK Score. It also cross-checks raw IO <= the old 185-case suffix relaxation
from offline_bounds_20261030/suite_verification.json; --old-suffix can change
the evidence path but the expected frozen suite identity remains enforced.
Any violation becomes a failed report rather than a silently excluded case.
Explicit resource skips remain visible with nulls and reasons.

Output is portable: relative input/report/source paths and SHA256 identities,
per-case bytes and scores, member/overall coverage, and aggregates on exactly
the SAME computed subset. The report includes sum(C)/sum(LB) and 1-sum(LB)/sum(C),
with undefined ratios represented as null. Different per-case averages are not
substituted for total-cost ratios. All original 785 cases remain accounted for.

This is analysis of a relaxation, not an optimal policy. A gap is at most a
possible-improvement upper bound, never achievable savings. Zero-gap cases do
not certify machine arithmetic. True future/p/B are offline inputs only;
nothing from this analysis is added to an online model or online scheduler.
