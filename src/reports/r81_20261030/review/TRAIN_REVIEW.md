# R81 TRAIN independent review

PASS: all228 cells and456 stdout/stderr SHA values checked independently. Raw output parsing, per-case probe totals, real penalty physical costs, costs including decision time D, exact case/method identities and rotated order, full denominators, family/penalty groups, nearest-rank quantiles, and advance all agree. Controller time92.965786 seconds; no cells were dropped. Reviewer ran no native/generator and read no input traces or DEV results.

Selection is based on new-TRAIN same-run Naive case-mean score, not mean cost ratio. Both candidates meet the frozen guards;256 wins on new-TRAIN mean score6.075025022 versus512 score6.060171211. D is included in cost and score; no hard D veto.

|Method|old26 mean score|new12 mean score|all38 mean score|all38 D mean ms|
|---|---:|---:|---:|---:|
|Naive|0.000000000|0.000000000|0.000000000|85.235660|
|R79_adaptive|4.485317540|5.847822243|4.915582183|74.831006|
|R80_next_hier_fast100|4.513718688|5.910884402|4.954928913|77.136108|
|R80_paired_hier_fast100|4.583882602|5.961445719|5.018902534|125.171506|
|R81_op256_cond2048|4.720494178|6.075025022|5.148240761|78.707039|
|R81_op512_cond2048|4.694022350|6.060171211|5.125437780|77.728832|

|Candidate|New score gain vs parent|Old26 score gain|Worst all38 cost/parent|Eligible|
|---|---:|---:|---:|---|
|R81_op256_cond2048|0.164140620|0.206775490|1.013786381|True|
|R81_op512_cond2048|0.149286809|0.180303663|1.007299040|True|

|Candidate/group|Mean cost/parent|P50|P90|Worst|W/L/T|
|---|---:|---:|---:|---:|---|
|R81_op256_cond2048/all38|0.964394136|0.976027136|1.001013598|1.013786381|32/6/0|
|R81_op256_cond2048/old26|0.963775456|0.973966766|1.000621458|1.009006075|23/3/0|
|R81_op256_cond2048/new12|0.965734608|0.978114887|1.002582384|1.013786381|9/3/0|
|R81_op512_cond2048/all38|0.967952553|0.978394528|1.000000104|1.007299040|34/4/0|
|R81_op512_cond2048/old26|0.967852887|0.975671438|0.998560869|1.003621753|24/2/0|
|R81_op512_cond2048/new12|0.968168496|0.980308414|1.000000104|1.007299040|10/2/0|

For both variants the worst all38 case is r81_train_burst_shared_p3_pen1000_hot:256 cost+1.3786%,512 cost+0.7299% versus parent. The256 version wins32/38 costs, while512 wins34/38; the higher new-TRAIN mean score still selects256 under the frozen rule. This is not uniform dominance.

Scope: old26 are previously exposed regression TRAIN; fresh12 are six same-seed none/hot pairs, not12 independent seed draws. Hot profiles alter INSERT and PROBE routing and partition sizes. Reserved DEV has not been evaluated or inspected in this review. One-repeat TRAIN screening supports candidate selection only, not generalization or default promotion. The fixed64 prior gives faster counts stronger shrinkage, so changes cannot be attributed solely to response time.

Evidence: train_review.json, train_per_case_scores.csv(all38 rows/all6 methods), train_groups.csv and train_independent_groups.json, train_paired.csv/json. artifacts.json binds all reviewer outputs. The source runner field uncapped_sum is a sum of clipped per-case scores; actual unclipped cost reductions are separately exported.
