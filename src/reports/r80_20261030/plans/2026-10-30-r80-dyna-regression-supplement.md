# R80 dyna_dataset regression supplement

The user explicitly requested evaluation on the original dyna_dataset after the final24 result. Preserve all candidate/source/parameter identities from R80 final24, and do not retune using either result.

Original dyna_dataset1.0.0 has12 cases, not24. Each has5 million operations. Its Git tree at datasets2eea302960533713ac0b3ed65c5514006c351920 equals the fixed f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246 tree (808ce8b11f57a1a96051f22aa572eceb82b1fba0), as checked by Master. Bind the fixed f25 dataset manifest/version/metadata and rehash chosen cached raw inputs before execution.

To follow the user's sampled-iteration preference, reuse the score-independent existing_eval6 list already recorded before R80: train_slow_shared_01, dev_slow_staggered_07, train_fast_shared_03, train_fast_staggered_04, train_burst_shared_05, dev_burst_staggered_09. This covers slow/fast/burst x shared/staggered and consists of original train4/dev2. It is an exposed regression sample, not an untouched holdout. Do not relabel the original splits or use it for training in this run.

Same five frozen policies as final24: official Naive, R79 adaptive, Van paired100, R80 paired hierarchical fast100, R80 hierarchical next fast100. Six cases x five methods=30 cells; serial CPU, one repeat, rotated method order. Official per-case wall limit remains60s. Set internal controller budget360s before execution because the6 inputs total30 million operations. This budget is not an official scoring limit or a changed case timeout. Preserve any failure rather than shrinking the denominator.

Reuse the frozen R80 runner via tmp/r80_eval/dyna_followup.py, separate outputs tmp/r80_dyna_eval/final. Score each input using same-run Naive and actual D, then take6-case mean. Report dyna and final separately. Cross-dataset comparison is (dyna6_mean + final24_mean)/2 for each method; it is a two-sample/two-dataset diagnostic, not the full GitHub member-suite average. Never compute the misleading pooled30-case mean as the requested primary result.

Independent review must reparse all30 outputs, verify60 log hashes, score/ratio tails, identities, sample membership and dataset-level equal weighting. Append a dyna supplement to the report; do not overwrite the original final24 results or claim full dyna12 coverage. Master publishes the frozen sources, new training data and negative results once the supplement is ready.
