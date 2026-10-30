# R80 dyna6 independent result review

PASS: all30 saved outputs and60 stdout/stderr SHA values independently checked. Five frozen method identities and the pre-existing six-case order match. Actual penalty, hit/probe totals, physical IO+penalty*miss, Total_Score including D, six-case score means, and nearest-rank statistics match the runner. Controller elapsed226.028268 seconds is below360; individual successful process times are below60 seconds. No scheduler/generator or input trace scanning was performed by this reviewer.

|Method|final24 score|dyna6 score|Dataset-equal score|dyna D mean seconds|
|---|---:|---:|---:|---:|
|Naive|0.000000000|0.000000000|0.000000000|1.907049|
|R79|3.704079354|3.938158013|3.821118684|2.064980|
|Van|3.846528394|3.641675684|3.744102039|3.775528|
|paired_fast|3.991113096|3.960574660|3.975843878|3.930962|
|hier_fast|4.090298060|3.911797494|4.001047777|2.096276|

dyna6 uses six equal case weights and its same-run Naive. The combined value is exactly(final24 mean+dyna6 mean)/2, not an equal-case average over30 cases. Decision timing stays separated by campaign in the CSV.

On dyna6, hier_fast3.911797494 is below R79 3.938158013 by0.026360519; paired_fast3.960574660 is highest, exceeding R79 by0.022416646. hier_fast is highest in the requested equal-dataset combination4.001047777, narrowly above paired_fast3.975843878. This does not establish universal superiority.

|Candidate/reference|Mean cost ratio|P50|P90=worst|W/L/T|Worst case|
|---|---:|---:|---:|---|---|
|hier_fast/R79|0.995719643|0.992609106|1.037002888|4/2/0|train_fast_staggered_04|
|hier_fast/Van|0.934967704|0.907258151|0.997380227|6/0/0|train_fast_staggered_04|
|paired_fast/R79|0.986239919|0.998224569|1.008689671|4/2/0|train_fast_staggered_04|
|paired_fast/Van|0.926206433|0.913293297|0.998222788|6/0/0|dev_burst_staggered_09|

Nearest-rank P90 with six cases uses ceil(0.9*6)=6, so it equals the maximum. P50 is the third sorted ratio, not the average of the middle two. Both new methods beat Van on all six costs, but each loses to R79 on two. hier_fast worst/R79 is1.037002888(+3.70%) and paired_fast worst/R79 is1.008689671(+0.87%), both on train_fast_staggered_04.

The mean hier/R79 cost ratio being below1 while its mean normalized score is lower is not a contradiction: per-case ratio-to-R79 and score normalized by per-case Naive use different denominators. The official score is the requested selection metric.

Scope: previously exposed dyna1.0.0 existing_eval6 regression, original train4/dev2, six of12 inputs; no blind-test or full-dataset claim. The fixed final24 sample is also a sample, and timing is one serial repeat per campaign. All scores include measured D; these simulated IO/miss costs are not real disk end-to-end timings. Original inputs/candidates/results were not modified.

Outputs: dyna6_per_case_scores.csv contains all six cases and five methods with score/cost/physical/IO/hit/miss/D and uncapped cost reduction. member_equal_scores.csv/json gives both member means and exactly50% weights. dyna6_paired.csv/json gives all requested paired comparisons. dyna_independent_groups.json contains all per-family groups. review.json contains result bindings; artifacts.json contains SHA256 for every review output.
