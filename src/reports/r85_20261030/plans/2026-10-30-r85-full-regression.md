# R85 complete original-data regression contract

Frozen before observing any R85 performance. This extends the R85 independent-ablations plan and implements the user's requests for complete original dyna/final tests, inclusion of Van, and versioned protocol/results/code publication on source/cyanneko.

## Fixed scope

- Every original dyna case: 12 cases, 5 million operations each. Every case in the latest verified final eval snapshot: currently 72 cases. Use the R84 inventory as the exact starting reference; verify remote dataset commit and both tree identities before selection. If either selected tree changed, stop preparation and explicitly freeze the new inventory before any run; do not silently reuse the old set or merge old/new results.
- Eight fixed methods in this order: Naive, R75_dense_switch, R80_next_hier_fast100, R80_paired_hier_fast100, R81_op256_cond2048, Van_latest, R85_fast_prior8, R85_hier_anchor. R79 is not part of this new ablation comparison; its complete R84 results remain available. Neither R85 candidate is dropped based on TRAIN/DEV performance.
- Reuse the exact R84 verified source/TU/ELF identities for six controls and the frozen R85 producer for both candidates. Van_latest is the fixed author branch version d92ceb0262b556eb57aae61127d062174ffe6016 with paired_penalty100.cpp SHA3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15, not a claim that a moving branch can never advance. Only scheduler-class changes; unchanged official framework, CPU-only g++ -std=c++14 -O2.
- One repeat per case/method, sequential execution, deterministic rotated method ordering as in the frozen execution core. Same-run Naive denominators. Case timeout60 seconds; total controller budgets1100 seconds for dyna and650 seconds for final. These are experiment-controller budgets, not claims about official total contest limits. No concurrent benchmark, compile, generation, training or bulk publication during measured windows.
- Prepare both full selections and hash every input/header before measured execution. Keep all invalid/timeout/error cells and logs. No retry or replacement to improve the score. The campaign remains incomplete if the controller errors after the last cell, if any identity changes, if any expected cell is absent/duplicated, or if any cell is invalid. Finalized summary plus completion gate is authoritative.

## Metrics and interpretation

Cost C = simulated IO time + evaluation penalty times miss count + measured cumulative decision time D. The scheduler never receives the hidden evaluation penalty or the future operation sequence. Its fixed proxy100 remains unchanged.

Per-case clipped points are max(0,min(10,10*(1-C/Naive))); nonpositive denominators follow the fixed scorer contract and must be disclosed. Raw points10*(1-C/Naive), physical cost excluding D, D, and cost ratios are reported separately. P50/P90 use nearest rank. Include per-case results, arithmetic dataset means, worse-than-Naive count, candidate/parent and candidate/Van comparisons, family breakdowns and worst tails. A's direct parent is R81; B's direct parent is R80 hierarchy. All ratios must label their denominator.

The combined objective is 0.5*mean_dyna_points + 0.5*mean_final_points, not a uniform84-case average and not a pooled cost ratio. The uncapped raw result is separate from the clipped per-case sum; there is no global50-point cap. No2xD hard veto. One repeat has timing noise; physical-cost changes may help distinguish algorithmic changes from D noise but do not establish causal superiority.

Both original datasets are exposed regression evidence. New TRAIN12/DEV6 diagnostics and original-data results remain separate. Do not call this an official score, blind generalization result, all-member leaderboard, or automatic promotion. Preserve frozen R75 default. Report failures as well as successes.

## Publication

Master remains the sole shared Git writer. Publish this protocol, exact inventories and input hashes, source/TU/ELF/compile/environment identities, raw stdout/stderr, per-case scores, summaries, completion gates, independent reviews and a human-readable report on source/cyanneko. Link immutable code and artifact commits in the shared evaluation index. Do not edit or relabel historical R84.
