# R80 original training result review

PASS:156/156 saved cells,312 stdout/stderr SHA checks, output parsing and identity/ordering checks. Independent group statistics and original advance exactly agree. No scheduler run and no input trace read/rehashed by this reviewer.

|Method|old16 cost ratio|new10 cost ratio|all26 P50|all26 P90|worst|D ratio|
|---|---:|---:|---:|---:|---:|---:|
|R79_adaptive|1.000000|1.000000|1.000000|1.000000|1.000000|1.000000|
|Van_paired_penalty100|1.033826|1.025530|1.027637|1.115828|1.132623|1.578243|
|R80_penalty100|0.994839|1.011821|0.999885|1.036416|1.066342|1.019184|
|R80_next_flat100|1.028827|1.006679|1.015152|1.066080|1.097590|2.364733|
|R80_next_hier100|0.994051|0.965220|0.996612|1.031015|1.039791|1.754603|
|R80_paired_hier100|0.983188|0.956478|0.995015|1.013428|1.018095|2.370936|

Ratios compare Total_Score including D with same-run R79. Physical IO+actual penalty*miss is separately exported; no Naive was run, so no official normalized scores are fabricated. Quantiles are nearest-rank. All groups use their complete denominators.

The original advance admitted only hierarchy under its initial hard D<=2 rule. The user subsequently removed that hard D gate before validation; the original decision is retained as history, not the current candidate selection rule. Lazy follow-up78 is a separate same-input campaign.

Scope:26 valid TRAIN of planned28; two capacity-rejected generated cases remain failures without replacement. New10 contains four complete none/hot pairs and two unpaired none cases; these are not independent random seeds. No validation scores were read.
