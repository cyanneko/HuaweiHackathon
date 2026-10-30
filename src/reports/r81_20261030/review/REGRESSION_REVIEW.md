# R81 original-regression independent review

Audit PASS; unqualified replacement is NOT supported. All36 dyna and144 final saved cells and360 stdout/stderr SHA values independently parsed and checked. Same frozen six methods, original sample identities, fresh same-campaign Naive scores including D, groups, nearest-rank statistics and equal-dataset aggregation agree. No failures were dropped. dyna controller elapsed258.515111s, final74.088013s. This reviewer ran no scheduler and scanned no input traces.

|Method|dyna6 mean score|final24 mean score|Dataset-equal mean|dyna D mean ms|final D mean ms|
|---|---:|---:|---:|---:|---:|
|Naive|0.000000000|0.000000000|0.000000000|1908.882|23.661|
|R75|3.899199683|3.250774268|3.574986976|2274.564|32.515|
|R79|3.938151712|3.704013172|3.821082442|2091.157|24.098|
|R80 hierarchy parent|3.911790031|4.090157230|4.000973631|2188.256|19.607|
|R80 paired|3.960550447|3.990961442|3.975755944|4023.430|45.713|
|R81 op256|4.007350852|4.094139825|4.050745339|2215.232|22.994|

Dataset means have exactly50% weight each; no30-case pooling or cross-campaign timing comparison. R81 improves official equal-dataset mean by0.049771708 over parent. However, the predeclared worst-case gate fails: final eval_059_random_zipf costs1.270355441 times parent, above1.25. The mean increase cannot cancel that guard. Retain this as a studied candidate; do not claim an unqualified replacement or automatically change the default.

|Dataset/reference|R81 mean cost ratio|P50|P90|Worst|W/L/T|Worst case|
|---|---:|---:|---:|---:|---|---|
|dyna/R75|0.980600847|0.997193324|1.008916096|1.008916096|4/2/0|train_slow_shared_01|
|dyna/R79|0.985190601|0.996396518|0.999320243|0.999320243|6/0/0|train_fast_staggered_04|
|dyna/R80 hierarchy parent|0.989747171|0.991159931|1.030907450|1.030907450|3/3/0|train_slow_shared_01|
|dyna/R80 paired|0.999237327|0.996410643|1.051075192|1.051075192|5/1/0|train_slow_shared_01|
|final/R75|0.794797019|0.791990069|0.993751488|1.028278145|22/2/0|eval_003_random_zipf|
|final/R79|0.897077730|0.940853301|0.996212933|1.203417946|22/2/0|eval_055_random_zipf|
|final/R80 hierarchy parent|1.011696096|1.000000595|1.038085855|1.270355441|11/13/0|eval_059_random_zipf|
|final/R80 paired|0.972126866|0.985415461|1.079595237|1.175147516|18/6/0|eval_055_random_zipf|

Nearest-rank dyna P90 is the maximum because ceil(.9*6)=6. Dyna improves official mean versus parent4.007350852 vs3.911790031, but has3 wins and3 losses; worst parent-relative cost is1.030907450 on train_slow_shared_01. Final has only11 wins versus13 losses against parent, cost-ratio mean1.011696096, despite its tiny official score gain0.003982595.

|Sample|R81 mean C/Naive|Parent mean C/Naive|Official clipped score delta|Unclipped score delta|
|---|---:|---:|---:|---:|
|dyna|0.599264915|0.608820997|0.095560821|0.095560821|
|final|0.616638149|0.604528617|0.003982595|-0.121095320|

Equal-dataset unclipped score delta is-0.012767249, whereas the official clipped-score delta is+0.049771708. The official scoring rule remains authoritative; the raw statistic diagnoses downside hidden by its zero floor. Both are reported rather than changing the metric after observing results.

Concrete counterexample eval_059_random_zipf (N1,048,576): R81 total cost40,557,097.47 vs parent31,925,787.19 vs Naive28,516,968.09. Both official scores clip to0. Their raw scores are−4.222093086 and−1.195365191, so the−3.026727895 raw difference disappears from the official case difference. Physical IO+penalty*miss is40,453,578.32 vs31,861,241.50; D is103,519.16 vs64,545.70 microseconds. Thus the regression is mainly physical cost, not solely decision time.

Other final declines include eval_003_random_zipf(+5.3245% cost vs parent, score−0.476725220) and eval_080_random_lognormal(+3.8086%, score−0.218259372). eval_065_random_hotspot is also zero for both methods; R81 slightly improves its raw loss, which clipping also hides. All30 per-case raw/clipped comparisons are exported in regression_raw_clipped_cases.csv.

Scope: dyna existing_eval6 and original R80 final24 are exposed regression samples, not blind tests, full12/full72 coverage, or the full GitHub suite. R81 identity remained the TRAIN-selected256 candidate without post-result parameter changes. Single serial repeat and six-case dyna tails limit conclusions. No new inference of unbiased next sampling or pure time-constant causality is warranted.

Evidence: regression_review.json; dyna_regression_per_case.csv; final_regression_per_case.csv; regression_member_equal_scores.csv/json; regression_paired.csv/json; regression_raw_clipped_cases.csv and groups.csv/json. regression_artifacts.json binds reviewer artifacts.
