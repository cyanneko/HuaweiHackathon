# R85 data review

PASS 18/18: TRAIN12 + reserved DEV6, 18 independent seeds. Generation+streaming audit 29.716069s /90s. CPU RELEASED, active0. No solver/training.

Operations 2,700,000; input bytes 55,241,149; max partition/M 0.800000000 at r85_train_07_random_zipf. Actual pressure range [1.2023094957694411, 3.1469872891902924]. Zero failures/replacements; requested seeds and all frozen parameters retained.

Dynamic TRAIN shared cases all request pressure1.25 and staggered all request pressure3. Phase and pressure are confounded; pressure×bandwidth balance does not remove this. DEV uses different seeds/parameters and is not a matched phase intervention. Do not infer phase causality.

Dynamic R72 naturally samples operator/partition counts; IID frozen constructor preallocates partition bytes/build counts, shuffles INSERT then SWITCH barrier and IID probes. Separate tracks, not the same stochastic model. Rare-hot affects both INSERT/PROBE and partition bytes.

Requested and actual pressure differences are natural realizations, preserved without correction. Dynamic rare-hot affects build sizes as well as probe traffic. The two tracks are distinct models. This fractional coverage is not a matched causal experiment; independent seed DEV is not independent distribution/OOD or a fresh official blind test.

Complete input bodies were streamed during generation using pinned audit code. This separate review verifies small artifacts, stats, metadata/log/trace hashes and contracts; it does not claim a second independent body scan.

|Case|Build|Probe|Actual pressure|Max partition/M|
|---|---:|---:|---:|---:|
|r85_train_01_slow_shared|59999|89999|1.248941123|0.260968640|
|r85_train_02_slow_staggered|48923|101073|2.725796890|0.020958353|
|r85_train_03_fast_shared|59999|89993|1.248554558|0.009552627|
|r85_train_04_fast_staggered|60400|89598|2.960416928|0.029528424|
|r85_train_05_burst_shared|59999|89997|1.252257637|0.020139460|
|r85_train_06_burst_staggered|67345|82647|3.146987289|0.247733280|
|r85_train_07_random_zipf|60000|89996|3.000000000|0.800000000|
|r85_train_08_random_hotspot|60000|89992|1.250000000|0.044117853|
|r85_train_09_random_lognormal|60000|89998|3.000000000|0.243981492|
|r85_train_10_random_zipf|60000|89992|1.250000000|0.337982610|
|r85_train_11_random_hotspot|60000|89998|3.000000000|0.145744618|
|r85_train_12_random_lognormal|60000|89996|1.250000000|0.054643050|
|r85_dev_13_slow_staggered|58309|91683|1.202309496|0.011515127|
|r85_dev_14_fast_shared|59999|89997|3.004716471|0.503020108|
|r85_dev_15_burst_staggered|63877|86121|1.240404163|0.012572739|
|r85_dev_16_random_zipf|60000|89998|3.000000000|0.799999997|
|r85_dev_17_random_hotspot|60000|89996|1.250000000|0.063488889|
|r85_dev_18_random_lognormal|60000|89992|3.000000000|0.286283165|
