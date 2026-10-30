# R81 reserved DEV independent review

PASS:30/30 saved outputs and60 stdout/stderr SHA checks. Independently parsed metrics, actual penalty costs, probe totals, scores including D, all group statistics and nearest-rank quantiles agree. Controller elapsed14.029900 seconds. No native/generator was executed by this reviewer, and no input trace was scanned. TRAIN review scripts and outputs remain unchanged.

All five method records exactly inherit TRAIN. The chosen256 candidate matches the frozen TRAIN advance and source identity. The DEV data contract matches the TRAIN-bound contract; six DEV lineage IDs/input SHA values do not overlap TRAIN, and their six seeds do not overlap the six new TRAIN seeds. Reserved metadata, parameters and stats match the pre-generation frozen manifest.

|Method|DEV6 mean score|Mean D ms|Mean cost/parent|P50|P90=worst|
|---|---:|---:|---:|---:|---:|
|Naive|0.000000000|117.966972|4.311970449|1.828926146|13.786640267|
|R79_adaptive|5.761387241|94.684343|1.019625981|1.008225817|1.048535794|
|R80_next_hier_fast100|5.821736749|91.108265|1.000000000|1.000000000|1.000000000|
|R80_paired_hier_fast100|5.859564377|154.752193|0.998366517|0.997724216|1.024423363|
|R81_op256_cond2048|5.984668531|95.591857|0.968265714|0.970900892|1.001837831|

|256 reference|Score gain|Mean cost ratio|P50|P90=worst|W/L/T|Worst case|
|---|---:|---:|---:|---:|---|---|
|R79_adaptive|0.223281290|0.950456414|0.954622663|1.000963350|5/1/0|r81_dev_slow_shared_p6_pen100_none|
|R80_next_hier_fast100|0.162931782|0.968265714|0.970900892|1.001837831|4/2/0|r81_dev_burst_shared_p6_pen1_none|
|R80_paired_hier_fast100|0.125104154|0.969424962|0.977092155|0.998406140|6/0/0|r81_dev_slow_shared_p6_pen100_none|

The256 candidate has the highest mean score5.984668531 on this six-case DEV sample, gaining0.162931782 versus the hierarchy parent and0.125104154 versus R80 paired. It beats the parent on four costs and loses on two. Worst parent-relative cost is1.001837831(+0.183783%) on r81_dev_burst_shared_p6_pen1_none. Against paired it wins all six costs. These are measured sample comparisons, not universal dominance.

For n=6, nearest-rank P90 is sorted item ceil(.9*6)=6 and equals the maximum; P50 is item3. Scores are equally weighted across six cases using same-run Naive and official zero-cost rules, with D included. Timing is one serial repeat; DEV D is not pooled with TRAIN D.

Boundary: these are six newly seeded150k-operation development cases after candidate selection, not an official hidden test. The fixed DEV alternation couples shared with none and staggered with hot, and rare-hot also affects INSERT routing and partition sizes. Fixed prior64 adds stronger shrinkage at shorter half-life. Original dyna5M and final regression results for R81 have not been established by this evidence, and this review does not authorize default promotion.

Artifacts: dev_review.json, dev_per_case_scores.csv(all six cases/five methods), dev_summary.csv, dev_independent_groups.json, dev_paired.csv/json. dev_artifacts.json binds the independent outputs.
