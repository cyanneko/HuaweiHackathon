# R75 phase-entry candidate (isolated from frozen R74)

Baseline: `../r74_fast/R74_fast_operator.policy.cpp` (`R74_MODE=2`, `R74_SIZE=0`).

## Change and statistical interpretation

On the first callback that exposes each operator in PROBE, enter its nonempty on-disk partitions into the risk set at the current public ordinal `q = hit_count + miss_count`. Each operator's partitions are scanned once. On an initial miss callback, exclude that callback's target from new entry; an already active episode can still complete normally. Confirm prior action intents before discovery. BUILD partitions and empty partitions are excluded. Periodic discovery also works before the scheduler has seen any overflow/miss, while preserving that inactive branch's empty actions and unchanged demand observations.

This records **conditional residual waiting after discovery**, not elapsed time since SWITCH or BUILD spill. SWITCH can occur without a callback, so its ordinal is unknown. No historical exposure is imputed. Initial-miss exclusion prevents a fabricated zero-wait completion. The existing prefetch confirmation path right-censors an episode at the issued LOAD ordinal. Repeated callbacks cannot reopen initial entries, and other operators' later phase transitions do not reset existing episodes.

The estimator remains a decayed constant-hazard heuristic. Discovery is callback-dependent and prefetch censoring is policy-dependent, so unbiased recovery of the original full waiting-time distribution is not claimed. Pooling entry cohorts with ordinary PROBE-spill episodes is an explicit modeling assumption. Initial entry may increase pooled exposure and affect priorities; any score improvement or regression requires a later coordinated evaluation.

No hidden penalty, N, or B is read. The 1 us penalty proxy, 64-request risk prior, exponential/LUT equations, observed-demand blend, victim ordering, and prefetch/action rules are unchanged. Additional storage is O(K) flags. Each callback checks O(K) phase flags; partition discovery totals O(KP) over the run, on top of the existing algorithm. First inactive periodic initialization can add setup cost and may bring initialization earlier. No runtime performance claim is made.

## Files

- `R75_phase_entry.policy.cpp`: single submission policy; append after official declarations.
- `R75_phase_entry.cpp`: complete translation unit, same framework as R74.
- `generate.py`: reproduce the two outputs from frozen R74 and create SHA256 manifest.
- `test_phase_entry.cpp`: new callback/entry behavior tests.
- `test_policy.cpp`, `test_risk.cpp`, `test_decay.cpp`: copied R74 regression tests.
- `test_policy_include.hpp`: generated test-only access wrapper; production visibility is unchanged.

## Verification

All compiled with WSL g++ `-std=c++14 -O2 -Wall -Wextra`.

- RED: new tests compiled against R74 and returned exit 1 with 14 expected missing-entry failures.
- GREEN: new phase-entry tests and all three copied regression tests passed (exit 0).
- Complete translation unit compiled successfully.
- Replacing the generated policy with its baseline reproduces the entire baseline translation unit after newline normalization, confirming no framework modifications.

New tests cover discovery through miss, periodic (including inactive), and overflow; first miss exclusion; initial other-disk subsequent miss and residual exposure; duplicate callbacks; zero-size exclusion; BUILD exclusion and delayed phase entry; prefetch right censoring; cross-operator discovery during a BUILD overflow.

No benchmark, training, dataset sweep, official timing, or Git operation was run. WSL printed its environment's localhost proxy notice; the compiler itself produced no warnings.
