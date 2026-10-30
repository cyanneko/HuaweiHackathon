# Independent R75 final review

No blocking correctness issue found in the reviewed changes. Both source candidates were read only; no candidate edits, benchmark, training, Git operation, or physical-diagnostic sweep was performed.

## Final candidate and evidence boundary

The final candidate is `R75_dense_switch.policy.cpp`. It differs from balanced in precisely one line: coverage >= .75 selects visible weight 1, while lower coverage selects .25. Balanced uses continuous interpolation between these values.

**Dense-switch is a targeted revision after inspecting fresh development examples and their diagnostic results. These examples are now development evidence, not untouched validation.** The functional checks here do not measure score or runtime improvement and do not establish generalization.

## Findings

- Cache lifetime: `release` clears all validity flags immediately before the priority scan. The earlier insufficient-need and uniform-cycle returns never read this cache. Each operator's first eligible candidate lazily advances its pool and caches the mean. Later candidates in the same scan cannot mutate pool events. Another callback at the same q may add a pool event through `update`; its subsequent priority scan resets validity and observes the new denominator.
- Dense branch: `refaultReuse` returns visible score before touching risks or caches. This defers integration, rather than dropping it: active exposure later integrates the full elapsed interval through `advance`; confirmed actions and miss completions still update episodes. Dense scans clear validity first, so a later sparse scan cannot reuse the previous sparse prior.
- Decay consistency: partition code uses tau=512 in both the exponential and integrated exposure; operator code uses tau=128 in both. Tests compare each against analytic exposure and dense versus sparse advancement.
- Visibility: implementation consumes the existing public state and next operation. It does not read hidden penalty, N, or B. The penalty proxy remains 1 microsecond. Longer/shorter risk horizons and heavier operator weighting are explicit heuristic choices.
- Legal actions and next protection: release/prune/record/load flow is unchanged. The next partition retains its existing +1e12 priority protection and the cycle path retains explicit exclusion. This is inherited best-effort protection when memory constraints require spilling, not a new absolute guarantee. Original callback tests execute returned actions and check memory limits; the new next-protection fixture also passes.
- No phase-entry discovery changes from the separate earlier R75 experiment are present in these candidates.

## Executed verification

Compiler: WSL g++ `-std=c++14 -O2 -Wall -Wextra`.

Balanced:
- Complete TU compilation succeeded.
- Original R74 callback, risk, and LUT tests passed.
- Added same-q cache invalidation, tau=512/128 analytic and callback-frequency integration, dense-guard residual exposure, and next-protection tests passed.

Dense-switch:
- Complete TU compilation succeeded.
- Original callback tests passed.
- Added tests passed for normalized coverage .749, .75, .751; sparse q10 -> dense q20 -> sparse q30 cache transition; same-q event cache invalidation; both risk integrals; dense-to-sparse exposure; and next protection. The risk/LUT implementation is byte-identical to balanced; those standalone tests were not redundantly rerun.

The compiler produced no warnings. WSL emitted its environment localhost-proxy notice. Test files and generated review translation units are retained in this directory and its `dense_switch` subdirectory. All compile/test processes have finished.

## Reviewed source SHA256

- R75_balanced.policy.cpp: `99a5deb2cdeb2459339ac7f07c5bd37f44191ece08415599fdf26b7a3b151ac5`
- R75_dense_switch.policy.cpp: `cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458`
