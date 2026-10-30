# R83 mixed coverage panel data review

PASS: 18/18 cases, 12 TRAIN + 6 reserved DEV; 31.757884s of 90s budget. CPU RELEASED / active0. No scheduler run or policy result read.

Total 2,700,000 operations, 54,883,188 input bytes. Maximum partition/M=0.540772233. Actual pressure range=[1.0999361425638199, 2.002444416284561].

TRAIN has six independent seed lineages with bandwidth 1/64 body-identical pairs, not twelve independent seeds. DEV has six separate seeds and bandwidth8. All six TRAIN body/operation/partition-stream comparisons pass. No failures or replacement seeds.

Original R72 dynamic model unchanged. IID track independently preallocates build bytes/counts before shuffled INSERT, SWITCH barrier and IID PROBE; not the same count-sampling model.

This is an explicitly separate coverage track: nine dynamic files and nine IID files. IID exact build-byte/count allocation must not be described as the original naturally sampled dynamic model. Rare hot affects INSERT and PROBE and therefore bytes, not a pure access-only intervention.

Complete input streaming validation occurred in generation. This review checks its recorded counts/identities, small metadata/log hashes, frozen sources and paired contracts; it does not claim an independent second full-body scan. Prior checks use recorded SHA/seed/lineage from named manifests, not a new scan of historical inputs. DEV is reserved until candidate freeze; no policy outcome exists in this data work.

| Case | Build | Probe | Actual pressure | Max part/M |
|---|---:|---:|---:|---:|
| r83_train_b01_slow_shared_bw1 | 59999 | 89999 | 1.09993614 | 0.05639914 |
| r83_train_b01_slow_shared_bw64 | 59999 | 89999 | 1.09993614 | 0.05639914 |
| r83_train_b02_fast_staggered_bw1 | 58574 | 91422 | 1.11539520 | 0.14069981 |
| r83_train_b02_fast_staggered_bw64 | 58574 | 91422 | 1.11539520 | 0.14069981 |
| r83_train_b03_burst_shared_bw1 | 59999 | 89993 | 2.00244442 | 0.00965662 |
| r83_train_b03_burst_shared_bw64 | 59999 | 89993 | 2.00244442 | 0.00965662 |
| r83_train_b04_random_zipf_bw1 | 60000 | 89998 | 2.00000000 | 0.54077223 |
| r83_train_b04_random_zipf_bw64 | 60000 | 89998 | 2.00000000 | 0.54077223 |
| r83_train_b05_random_hotspot_bw1 | 60000 | 89996 | 1.25000000 | 0.09385756 |
| r83_train_b05_random_hotspot_bw64 | 60000 | 89996 | 1.25000000 | 0.09385756 |
| r83_train_b06_random_lognormal_bw1 | 60000 | 89992 | 1.25000000 | 0.06604832 |
| r83_train_b06_random_lognormal_bw64 | 60000 | 89992 | 1.25000000 | 0.06604832 |
| r83_dev_b01_slow_shared_bw8 | 59999 | 89999 | 1.10055335 | 0.04736005 |
| r83_dev_b02_fast_staggered_bw8 | 67143 | 82853 | 1.18841889 | 0.14824178 |
| r83_dev_b03_burst_shared_bw8 | 59999 | 89993 | 2.00124083 | 0.00643089 |
| r83_dev_b04_random_zipf_bw8 | 60000 | 89998 | 2.00000000 | 0.54077223 |
| r83_dev_b05_random_hotspot_bw8 | 60000 | 89996 | 1.25000000 | 0.07425027 |
| r83_dev_b06_random_lognormal_bw8 | 60000 | 89992 | 1.25000000 | 0.03761236 |

Dynamic rare-hot target pressure is 1.10; actual TRAIN pressure is 1.115395199507475 (both bandwidth legs), DEV pressure is 1.1884188875555992. These are unchanged random-model realizations, not a reason to resample.

DEV uses independent seeds under the same predeclared mechanism/shape parameters. In particular IID Zipf structure is determined by the same family parameters; seed independence does not imply independent distributions or OOD. This panel is reserved development validation, not a blind official test set.

Split/lineage/seed checks PASS: TRAIN and DEV seed sets and lineage sets are disjoint; all 18 input SHAs are unique and absent from the declared prior manifest registry. Prior checks do not imply exhaustive knowledge of all historic seeds.
