# R79 16-case TRAIN diagnostic result

64/64 completed; independent raw-output audit PASS (128 log SHA checks). Native loop until CPU release 16.086s; runner including closing identity checks/report 16.738s, within60s. Serial, repeats1, no replacement/retry. CPU RELEASED/active0. All frozen artifacts unchanged.

The 16 inputs contain unchanged previously viewed R78 TRAIN8 plus new TRAIN8 (four same-seed none/hot pairs). No dev or holdout. Every method ran the same frozen inputs. Van_paired100 is the output label for producer Van_paired_penalty100, latest supplied Van reference; it is not a clean one-feature R75 ablation.

Main cost is simulated physical IO + actual penalty*miss, excluding D. Actual penalty100 for all inputs. Ratios below use same-case same-run R75; lower is better. Means are equal-case means of ratios, not ratios of cost sums. P50/P90 use linear interpolation q*(n-1). No same-run Naive: no normalized score is claimed.

|Method|mean/R75|P50|P90|worst|best|W/L/T|mean cumulative D, us (nonformal)|
|---|---:|---:|---:|---:|---:|---|---:|
|R75|1.000000000|1.000000000|1.000000000|1.000000000|1.000000000|0/0/16|65861.804|
|R79_independent_fixed75|0.988526117|0.997935041|1.028845818|1.089837099|0.838195057|10/6/0|66626.131|
|R79_adaptive|0.971955373|0.996004065|1.004010498|1.065278313|0.689794126|12/4/0|64815.454|
|Van_paired100|1.003214432|1.013671078|1.096871791|1.118179381|0.748967638|7/9/0|100987.748|

Adaptive mean physical cost improves2.804463% vs R75, but this is a training diagnostic. Its best case is new burst_staggered p3 hot (ratio.689794126, improvement31.020587%); its worst is new fast_shared p3 hot (ratio1.065278313, regression6.527831%). Fixed best is the same burst-hot case (.838195057), worst new fast_shared p3 none (1.089837099). Van best is burst-hot (.748967638), worst existing burst_staggered p3 (1.118179381).

|Adaptive relative to|mean|P50|P90|worst|W/L/T|
|---|---:|---:|---:|---:|---|
|R75|0.971955373|0.996004065|1.004010498|1.065278313|12/4/0|
|fixed|0.982210164|1.000484828|1.006494964|1.032286336|7/9/0|
|Van|0.970122897|0.971837077|1.013120318|1.092586473|11/5/0|

The adaptive-vs-fixed mean ratio .982210164 supports an average gain in this panel, while7 wins/9 losses shows it is not a consistent per-case improvement. This contrast isolates the two delivered modes more directly than comparing either to R75; R75-to-fixed also changes the independent estimator. No per-callback weights were instrumented, so this run alone does not prove which observed weight change caused any gain.

|Group|N|fixed/R75 mean|adaptive/R75 mean|Van/R75 mean|adaptive W/L/T vs R75|
|---|---:|---:|---:|---:|---|
|all16|16|0.988526117|0.971955373|1.003214432|12/4/0|
|existing8|8|0.985589054|0.979832350|1.026572646|7/1/0|
|new8|8|0.991463179|0.964078396|0.979856219|5/3/0|
|none12|12|0.998193325|0.984814306|1.029276154|9/3/0|
|hot4|4|0.959524490|0.933378573|0.925029267|3/1/0|
|pressure3|8|0.981041344|0.946337319|0.989808511|6/2/0|
|pressure12|8|0.996010889|0.997573427|1.016620354|6/2/0|

The panel has12 none +4 hot, so all16 is not an equal-weight none/hot comparison. In hot4, Van mean ratio .925029267 is lower than adaptive .933378573; adaptive does not win every group. Pressure12 adaptive/fixed mean ratio is1.001594501. Paired inputs share seeds, operator counts and total bytes; hot affects both INSERT/PROBE routing and partition sizes, so none/hot differences are not pure access-frequency effects. The new8 represent four new random lineages, not eight independent seeds.

|Case|fixed/R75|adaptive/R75|Van/R75|
|---|---:|---:|---:|
|r78_scale_train_fast_shared_p3|0.956854799|0.941939648|0.983917693|
|r78_scale_train_fast_shared_p12|1.005121309|1.005371677|1.042311884|
|r78_scale_train_fast_staggered_p3|0.944578613|0.946654815|0.925097720|
|r78_scale_train_fast_staggered_p12|0.999316922|0.998631130|1.029148704|
|r78_scale_train_burst_staggered_p3|1.025731533|0.987342479|1.118179381|
|r78_scale_train_burst_staggered_p12|0.997892260|0.999398830|1.006949992|
|r78_scale_train_slow_shared_p3|0.957239175|0.960623294|1.086583629|
|r78_scale_train_slow_shared_p12|0.997977822|0.998696929|1.020392163|
|r79_train_fast_shared_p3_none|1.089837099|0.976416558|0.973556123|
|r79_train_fast_shared_p3_hot|1.031960102|1.065278313|0.975005951|
|r79_train_fast_staggered_p12_none|1.003232031|1.002390304|1.032813734|
|r79_train_fast_staggered_p12_hot|0.974873346|0.984090420|0.983894969|
|r79_train_burst_staggered_p3_none|1.003934371|1.002649319|1.107159952|
|r79_train_burst_staggered_p3_hot|0.838195057|0.689794126|0.748967638|
|r79_train_slow_shared_p12_none|0.996603969|0.997656695|1.025202876|
|r79_train_slow_shared_p12_hot|0.993069456|0.994351434|0.992248508|

per_case.csv retains physical cost, IO, real penalty, hits/misses, all reference ratios, negative improvements, D, total including D and wall. report.json also retains four matched-pair contrasts per method. Existing8 original R75 physical costs exactly reproduce the previous R78 scale run; D values are deliberately not treated as reproducible.

Environment recorded after the run: Intel(R) Core(TM) i7-14700HX, Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.35. All policy binaries are existing C++14/O2 and uninstrumented; fixed serial method order, one repeat. D is measured cumulative decision time, but this is a diagnostic window rather than formal repeat-controlled timing; do not infer statistically reliable CPU speed differences from these means.

Independent verifier does not import runner or execute policies. It reparses64 stdout, checks128 stdout/stderr SHA, full16x4 grid, input/binary/source identity references, integer hit/miss closure, real penalty and physical cost, rounded total ledger (0.015001us tolerance), per-case ratios, all group statistics and matched-pair contrasts. Input/source/TU/binary hashes were verified before and after execution. Official framework prefix/suffix equality was verified after CRLF normalization only, while preserving original byte SHA identity.

No promotion or threshold tuning follows from this run. The new mechanism pairs were frozen before candidate costs, but all16 remain TRAIN/development diagnostics; the existing8 were previously viewed and the four new pairs are dependent. The worst-case regression and adaptive-vs-fixed9 losses remain part of the evidence.

Data manifest SHA: `d8ac91523dfb242051f13cdc0a77fe62b00955bc0e81fdfdfdd2c5fd1ffa71a9`.
Producer SHA: `6522a912da33450e8b5f7dfd6a9ae12b4439adf35ff1deec05926d9bbd9df4a4`.
Selection SHA: `1e2be357e4b8c337fc07b1fbf9c8e274e72019c5832df2f45475035e800d1d17`.
Report SHA: `729853818ca80f5523841ace478ca29c8200f54e222c76e74f8ba01722b657aa`.
