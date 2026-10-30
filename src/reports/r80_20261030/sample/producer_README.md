# R80 validation24 frozen sample

Pinned release: final_dataset2.1.0 at f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246. The full72 input/metadata SHA contract is inherited from tmp/r79_final_eval/root_input_contract.json. Current HEAD/latest datasets are not used. No scheduler or historical score was read/executed by this preparation.

Exclude exactly the previous R79 final24 first. Remaining families: Zipf19, hotspot19, lognormal10. Within each remaining family sort by (N,case_id); tertile j spans floor(j*n/3) through floor((j+1)*n/3)-1. Select minimum SHA256(UTF8("r80-final-sample-v1"+case_id)), no delimiter; ties by case_id. Take3/3/2 per respective family per tier, yielding9/9/6 and24 total. The selection was fixed before R80 candidate results.

All24 actual headers match N/penalty/probe totals, operator headers and metadata parameters. Metadata SHA and corresponding all72 Root contract SHA entries match. No full input content was rehashed; published semantic validation is inherited. Both case-ID and input-SHA intersections with previous24 are empty. Selected total operations:6,990,356. This sample is new to the R80 experiment, not claimed to be historically unseen or an official hidden test set. Do not retune on it.

|case_id|family|remaining-N tier|N|
|---|---|---:|---:|
|eval_003_random_zipf|random_zipf|1|184856|
|eval_004_random_zipf|random_zipf|0|140042|
|eval_005_random_lognormal|random_lognormal|0|153632|
|eval_015_random_hotspot|random_hotspot|0|190955|
|eval_023_random_hotspot|random_hotspot|1|287467|
|eval_024_random_zipf|random_zipf|1|210701|
|eval_025_random_zipf|random_zipf|0|95052|
|eval_026_random_hotspot|random_hotspot|0|178709|
|eval_039_random_lognormal|random_lognormal|0|138418|
|eval_042_random_hotspot|random_hotspot|0|169724|
|eval_047_random_zipf|random_zipf|0|78260|
|eval_051_random_zipf|random_zipf|1|182907|
|eval_052_random_zipf|random_zipf|2|311591|
|eval_055_random_zipf|random_zipf|2|515558|
|eval_059_random_zipf|random_zipf|2|1048576|
|eval_065_random_hotspot|random_hotspot|1|272568|
|eval_066_random_hotspot|random_hotspot|1|198823|
|eval_068_random_hotspot|random_hotspot|2|369663|
|eval_076_random_hotspot|random_hotspot|2|520849|
|eval_077_random_hotspot|random_hotspot|2|408579|
|eval_078_random_lognormal|random_lognormal|1|194708|
|eval_079_random_lognormal|random_lognormal|2|498627|
|eval_080_random_lognormal|random_lognormal|2|369156|
|eval_084_random_lognormal|random_lognormal|1|270935|

selection.json contains exact case IDs, parameters, relative/absolute Linux input paths, input/metadata SHA, selection hashes, all stratum candidates, dataset_identity and the pinned Root contract path/SHA. No methods are selected here; bind eligible TRAIN-screened candidates in the later evaluation contract. config.json freezes the algorithm/exclusions/release and preparation-script SHA. cases.csv supplies a compact table.

Selection SHA: `38a8d93e23c33c174942648a828def2172089c728a3ee06f51a6aff34c4d8c90`. Root all72 contract SHA: `f7377bfc29ac5f23e09252d02923d5226f812b581c93809b51370437da3c787a`.
