# R86 final_dataset 3.0 complete regression contract

Frozen before any scheduler runs on final 3.0. This is a dataset-upgrade comparison, not a new algorithm or parameter search. The user requested complete original dyna/final tests, inclusion of Van, versioned code/results on source/cyanneko, dataset-equal aggregation and explicit decision time/tail metrics.

## Fixed data and methods

- Pin datasets commit e6613435d59690d6dd768813332387108f7e83c2, final tree 35d4f98b7464e62a9a89b606e41d192380788e76, version 3.0.0. Use all 72 eval inputs (22,528,629 operations; 474,874,682 input bytes). All 72 input hashes differ from their final 2.1 parents. Cache in tmp/r86_final3_cache only; never alter tmp/d70, old inputs or historical results.
- Independently export and validate the exact eval-only manifest. The shipped verifier requires all 612 inputs; invoking its unchanged verify_case on all 72 eval files is an eval-only audit, not a new verification of the full 540 TRAIN plus 72 eval package. Preserve publisher whole-package reports with an explicit evidence boundary.
- Keep precisely the eight R85 methods and their original class/TU/ELF bytes, in order: Naive, R75_dense_switch, R80_next_hier_fast100, R80_paired_hier_fast100, R81_op256_cond2048, Van_latest, R85_fast_prior8, R85_hier_anchor. Bind tmp/r85_full_eval/methods.prepared.json SHA256 120ee46d35d3370c05938115b01bffa37f4e12b42df24a0417bceb42def68c83 and the original release/dependency closure. No recompile or source change. Van_latest refers to the pinned paired_penalty100 source SHA256 3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15, verified unchanged at author commit 6ded7022215b80a8edf4170faefe1ca4da16814f.
- Reuse the just-completed full R85 dyna12 records, without relabeling them as newly measured: selection SHA256 ffc39955a180a87768d7360c070b48b4b6490bb4d831edc4f0c2bee4e1bcdd97, rows 635bbe26af4ec3474ca2575e3916903e8ea0d5b8463727e1cdd4cb132698cfe8, finalized summary 69036509482c858261a738384119f77049eac8b5d75f492a4daa29731ef2c4fa. Dyna tree remains 808ce8b11f57a1a96051f22aa572eceb82b1fba0; verify tree, 12 input identities and identical eight methods before reuse. Preserve the R85 same-campaign Naive denominator for every dyna row. No new dyna native runs in R86.

## Execution and completion

- New final run: 72 cases x 8 methods = 576 cells; one repeat; CPU-only Linux; unchanged official framework; original g++ -std=c++14 -O2 builds. Deterministic lexicographic case order and rotated method order, same-campaign Naive per case.
- Root alone releases the native window after both data and runner reviews pass. Internal controller budget 650 seconds, individual cell timeout 60 seconds, serial execution. These are local experiment budgets, not the official total runtime limit. No overlapping benchmark, compile, training, generation or bulk publication. No retry, seed replacement or method removal based on results.
- Bind every input/sidecar/manifest/recipe/validation artifact, source/TU/ELF, scorer, execution helper and plan by SHA256. Probability certificates and whole-stream counts are offline audit metadata and must never enter the scheduler interface.
- Preserve failures, logs and partial results. A full row grid is insufficient: require all expected cells valid, campaign identity and hashes unchanged, controller return success, no active child processes, and explicit finalized completion gate. An error after the last cell remains an incomplete campaign.
- Reuse the frozen R80 execution core and R85 scoring semantics where practical. Add only the new inventory/validation wrapper and explicit historical-dyna reuse contract. Independently reparse official stdout and verify log hashes, total-cost accounting, probe counts, per-case scores, groups, quantiles and denominators before publication.

## Metrics and interpretation

Cost C = simulated IO + evaluator penalty x miss count + measured cumulative decision time D. Scheduler hidden-penalty/future restrictions remain unchanged; fixed proxy100 stays legal. Per-case points are clip(10*(1-C/Cnaive), 0, 10), with the frozen scorer's nonpositive-denominator rule. Also report uncensored raw points, physical cost excluding D, D, cost ratios, P50/P90 nearest rank, worst cases and worse-than-Naive counts. Label every ratio denominator; keep dataset quantiles separate.

Combined score is 0.5*mean(R85 dyna12 points) + 0.5*mean(new final3 eval72 points). Explicitly label historical reuse in the machine-readable combined result and the report. Do not pool 84 cases equally, substitute old final results, or average quantiles. Dataset-upgrade results and R85 final2.1 results get separate columns/sections. New probability contracts are synthetic-data design choices, not guarantees about the official hidden workload. Reused BUILD layouts are already exposed; this is not a blind test.

No global 50-point cap, no hard 2xD veto, no automatic default promotion. One timing repeat has no uncertainty estimate. Keep frozen R75 as the submission default pending a separate promotion decision. This fixed eight-method/two-dataset comparison is not an all-member leaderboard.

## Publication

Master is the sole shared Git writer. Publish protocol, exact code identities, inventory and data/audit provenance, raw logs, per-case/group summaries, tail diagnostics, reuse manifest, review and report to source/cyanneko with immutable links. Reference already published datasets without uploading duplicate inputs. Preserve R84/R85 as final2.1 evidence. Shared default-branch documentation goes through the existing draft PR after the direct-push approval rejection; do not bypass it.
