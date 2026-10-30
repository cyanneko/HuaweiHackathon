# R80.1 Probability Query Follow-up

The first frozen26x6 screening completed156/156 valid. Hierarchical next sampling improved new10 mean cost to0.965220 of R79; paired hierarchical sampling reached0.956478 but its D ratio2.370936 failed the initial2x gate.

Before any R80 final validation, the user instructed: decision time may be somewhat longer; primarily judge final score. Therefore retain D in Total_Score and report timing, but explicitly remove the hard2x D gate. Preserve the original screening advance.json as historical evidence. No change to official60-second case limit or180-second controller budget.

Static performance observation: the eager cache computed probability for every partition, including disk-resident objects that cannot be eviction victims. Create isolated lazy variants of hierarchical and paired planners in tmp/r80_lazy_transfer. Keep all formulas, clocks, priors, candidate search, uncertainty threshold and actual-intent logic unchanged. Aggregate operator statistics once per release; query per-ID probability on demand, with uint64 epochs and explicit rollover invalidation, so valid candidates and changed-action IDs share cached values. Retain exact decay lookup and cold-mass shortcut.

Tests: original eager behavior must fail an on-demand-query expectation; exact all-ID probability oracle, epoch rollover, inherited legality/guard tests, and400-step old/new callback-action comparisons. Compilation/testing capped60s. Original R80/R79 files remain frozen.

Follow-up benchmark: same26 frozen TRAIN inputs, fresh R79 baseline plus two lazy derivatives =78 cells. Serial CPU. Require input SHA and exact printed Total_IO_Time/Hit_Count/Miss_Count equal to the respective first-stage parent on every case; this observable check is not an every-action trace. If equivalence fails, preserve failure and retain the old family implementation. Select the lower measured normalized-D implementation for each equivalent family; single-repeat timing is provisional. Keep new10 mean<1, old16 mean<=1.05, all26 worst<=1.25 and full ratio denominators as screening guards, but no hard D ratio veto per new user direction.

At most two eligible families proceed to the already frozen24-case validation, with same-run Naive/R79/Van. Do not run or inspect validation outcomes before candidate identities freeze. All final scores include D. Never relax thresholds silently or overwrite first-stage results.

Files: tmp/r80_eval/lazy_followup.py reuses the frozen serial runner without editing it; tmp/r80_lazy_eval holds immutable selection/results/equivalence/revised advance. Main report docs/20261030_R80借鉴Van的受控实验.md must explain both the initial gate and the user-requested revision.
