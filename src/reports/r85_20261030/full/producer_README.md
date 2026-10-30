# R85 complete original-data regression

Eight immutable methods, in order: Naive, R75_dense_switch, R80_next_hier_fast100, R80_paired_hier_fast100, R81_op256_cond2048, Van_latest, R85_fast_prior8, R85_hier_anchor. Both candidates remain included regardless of new-panel TRAIN/DEV scores. A's direct parent is R81; B's is R80 hierarchy. Van is the captured author commit d92ceb0262b556eb57aae61127d062174ffe6016 with the unchanged previously verified class/TU/ELF, not a promise about future branch heads.

Data: all original dyna12 and all final eval72. Expected grids96/576, total672. Master proof `tmp/pub82/r85_dataset_metadata_proof.json` fixes datasets commit c65c7b32b06a5764ce9ad4881133a3c6eb33ed17. The selected trees match R84; no other dataset or final train is included. A changed selected tree blocks preparation until a newly reviewed inventory is frozen. Original split labels are retained; these datasets are exposed regression evidence.

Only source/metadata identities and small synthetic tests are prepared here. Root must execute complete-input/header/ELF preparation for both datasets before either measured window:

```sh
python3 tmp/r85_full_eval/regression.py prepare dyna
python3 tmp/r85_full_eval/regression.py prepare final
python3 tmp/r85_full_eval/regression.py run dyna --cpu-window-released
python3 tmp/r85_full_eval/regression.py run final --cpu-window-released
python3 tmp/r85_full_eval/regression.py combine
```

CPU serial, one repeat, official60s/cell; internal total controllers1100s dyna and650s final. Root coordinates an exclusive quiet window. The unchanged core rehashes inputs around each case and includes this in controller wall time; D remains the framework's cumulative callback microseconds. No retry, failed-case trimming, source changes or historical result substitution. Every run first checks both selections against the frozen eight method dictionaries and complete inventory fields, not just their mutual equality or counts.

Score uses fresh same-window Naive: clipped10*(1-C/B) with official nonpositive C/B zero-score rule. C includes IO + actual evaluation penalty*miss + D. Raw negative improvement, physical cost, D, defined denominators, nearest-rank P50/P90/worst and all named-reference comparisons are separate. Both candidates have explicit direct-parent labels; Van comparisons remain available. No2xD veto or automatic promotion.

Primary dataset result: `finalized_summary.json` plus `completion_gate.json`. Missing/invalid/duplicate cells, changed dependencies, failure after the last cell or any wrapper exception cannot yield a complete aggregate. Wrapper exceptions preserve INCOMPLETE gate and rethrow; combine requires PASS gates. Raw core output is retained unchanged. `combined_dataset_equal.json` averages the12-case dataset mean and72-case dataset mean with50% each; never a pooled84-case mean or pooled ratio. This is not an all-member leaderboard or hidden-score forecast.

Frozen release dependencies include both plans, dataset proof, source/TU identity contracts, original build/environment disclosure, R85 producer/tests, scorer, protocol tests and static review. Linux prepare rechecks every ELF. Root/Master later add immutable publication-commit mapping externally without rewriting the frozen run. No R84 results were copied; the reused source core, scorer mathematics and inventory references remain attributable.
