# R84 static review

Static contract checks and synthetic scoring tests PASS. This is not a performance-result review: no scheduler, compiler, full input scan, or formal prepare was run by this review.

Inventory includes exactly dyna12 (original train6/dev3/holdout3, 60,000,000 operations, 1,170,613,062 bytes) and final eval72 (28 hotspot, 28 zipf, 16 lognormal; 22,528,629 operations, 474,874,705 bytes). Metadata SHA, declared input SHA, file sizes and original split labels agree with the published manifests. Root prepare must still hash every complete input and verify its header.

Master's fixed datasets proof identifies commit `01e9de234cc735bc442f020c8b1b503d961543db`, dyna tree `808ce8b11f57a1a96051f22aa572eceb82b1fba0`, final tree `41197783dd577dfccf5b007a6ece67cbfb241e4b`. Both match the earlier cached data trees. This review independently checked the local metadata and proof SHA; it did not make a second network query or claim that later remote revisions cannot occur.

All six historical method dictionaries match the immutable R81 regression reference. Source and TU SHA and normalized official framework skeleton checks pass. All ELF hashes remain gated in Linux prepare. Van_latest is separately bound to the latest verified submit-ready class and immutable source commit through a producer/release/test/proof contract; identity-equivalent reuse is allowed and must not be described as fresh compilation.

The seven-method protocol is 84 dyna cells and 504 final cells, serial one repeat, official60s/cell, internal900/600s. The wrapper reuses the frozen process core without editing it. Its independent scorer handles both dyna and final as same-window Naive-scored regression, never the old TRAIN branch. D is measured in microseconds and included in total cost; physical IO+actual penalty*miss, negative raw improvement, clipped scores, reference ratios and nearest-rank quantiles remain separate.

Synthetic checks cover C/B zero rules, D accounting, missing/invalid/duplicate/unknown cells, negative raw improvement hidden by clipping, nearest-rank P90 for n6/n12, undefined ratio counts, equal weighting of the12-case and72-case means, and incomplete combination. An extra `finalized_summary.json` and completion gate prevent a controller error after the last native cell from passing solely because all rows exist. Original core outputs remain unchanged.

No 84-case pooled mean is used. Completeness requires all seven methods on the identical case set, successful controller termination, and unchanged identities. Failures and missing cells remain visible. The two complete dataset means each receive50%; quantiles stay separate. Original dyna holdout is already exposed regression, not a fresh blind test. There is no automatic default promotion or all-member leaderboard claim.

Executable commands and proof schema are in `tmp/r84_full_eval/README.md`. Remaining gates before timing are the Van identity binding and Root's complete-input/ELF prepare. The static review does not waive those gates.
