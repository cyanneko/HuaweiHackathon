# R80 final independent review

PASS. Independently parsed all78 follow-up TRAIN and120 final outputs and verified396 stdout/stderr SHA values, complete grids, identities, process results, probe counts, physical costs, and Total_Score including decision time D. All published summary groups and nearest-rank quantiles agree. Review ran no scheduler and did not read or hash input traces.

|Stage|Cells|Active controller seconds|Reviewer log SHA checks|
|---|---:|---:|---:|
|Original TRAIN|156|62.367128|312|
|Lazy TRAIN with fresh R79|78|30.663274|156|
|Disjoint final sample24|120|60.205982|240|

These are three separate serial campaigns. They must not be represented as one same-round timing comparison. The first-stage pair failed its original2x D screening rule; this is not evidence of algorithm failure. The user removed that hard veto before validation, while preserving D in costs and cost/regression guards. Frozen lazy-training selection e0ce3dfa already contains that revision; its campaign began1793361899.528, before final1793361987.280. The final selection binds the revised advance SHA55827fc7. Both fast implementations reproduce all26 parent input/IO/hit/miss observables; this is not a full every-action trace.

Scores are24-case equal means of clip(10*(1-C/Naive),0,10) with official C<=0 or Naive<=0 mapping to zero. All actual Naive costs were positive. Costs include D; displayed D means below convert microseconds to milliseconds.

|Method|Mean score|D mean ms|Cost/Naive mean|P50|P90|Worst|
|---|---:|---:|---:|---:|---:|---:|
|Naive|0.000000000|22.877394|1.000000|1.000000|1.000000|1.000000|
|R79|3.704079354|22.136933|0.706300|0.541514|1.168201|2.158410|
|Van|3.846528394|31.323254|0.676789|0.537000|1.206659|1.928044|
|paired_fast|3.991113096|43.610283|0.644542|0.565359|0.994922|1.709974|
|hier_fast|4.090298060|18.837660|0.604504|0.554041|0.917510|1.205194|

|Candidate/reference|Mean cost ratio|P50|P90|Worst|W/L/T|Worst case|
|---|---:|---:|---:|---:|---|---|
|hier_fast/R79|0.890393|0.940520|1.006118|1.211224|20/4/0|eval_055_random_zipf|
|hier_fast/Van|0.923176|0.966808|1.031732|1.127033|15/9/0|eval_055_random_zipf|
|paired_fast/R79|0.919655|0.920781|1.031311|1.053144|19/5/0|eval_080_random_lognormal|
|paired_fast/Van|0.955180|0.980905|1.047452|1.057056|16/8/0|eval_003_random_zipf|

|Family|Cases|R79 score|Van score|paired_fast score|hier_fast score|
|---|---:|---:|---:|---:|---:|
|random_hotspot|9|4.979520550|5.233523489|5.261182852|5.349308544|
|random_lognormal|6|4.630386999|4.436055828|4.962352313|5.076312865|
|random_zipf|9|1.811099728|2.066515009|2.073550527|2.173944374|

hier_fast has the highest mean score in this single-repeat24-case sample: +0.386219 versus R79 and +0.243770 versus Van. It is not better on every metric: its Cost/Naive P50 is0.554041 versus R79 0.541514, and its worst R79-relative case eval_055_random_zipf is1.211224 (+21.12%). paired_fast has lower mean score but smaller worst R79-relative degradation1.053144 (+5.31%). No claim of full72 ranking, unseen-test performance, universal dominance, or real end-to-end disk speed is supported.

The source summary key uncapped_sum is misleading: it sums clipped scores. The exported per-case CSV separately preserves actual uncapped cost reduction1-C/Naive, including negatives.

Evidence: lazy_final_review.json binds source reports and CSV hashes; final_per_case_scores.csv contains all24 rows and five methods; final_family_scores.csv contains family aggregates; final_paired.csv/json contains paired comparisons. Original train review remains separate in TRAIN_REVIEW.md. Final24 contract entry SHA checks are in final_contract_entry_review.json.
