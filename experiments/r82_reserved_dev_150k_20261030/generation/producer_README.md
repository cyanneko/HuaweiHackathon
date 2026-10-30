# R82 reserved DEV preparation

Status: all12 DEV cases were generated and fully audited in the explicitly released Root window, taking6.417010 seconds within the frozen30-second budget. All six pairs are complete, with no failure/replacement and no scheduler execution. CPU is RELEASED/active0. The frozen generator and its source were reused without edits.

The panel contains only12 new DEV cases, each150,000 operations: six independent seeds202610310301..306, each with a same-seed ordinary/rare-hot pair. No old TRAIN entry is included. All original R81 defaults are preserved; pressure reverses R81 TRAIN and penalty uses the prescribed+2 Latin rotation.

|Mechanism|Seed|Pressure|Penalty|Rare profiles|
|---|---:|---:|---:|---|
|slow_shared|202610310301|6|1000|none/hot|
|slow_staggered|202610310302|3|1|none/hot|
|fast_shared|202610310303|3|1|none/hot|
|fast_staggered|202610310304|6|100|none/hot|
|burst_shared|202610310305|6|100|none/hot|
|burst_staggered|202610310306|3|1000|none/hot|

Each penalty occurs four times; every mechanism has both rare profiles. These are six independent lineages, not12 independent seeds, and not a full factorial of mechanism/pressure/penalty. Hot profiles affect INSERT as well as PROBE routing, so partition sizes can change. True penalty remains framework/evaluation metadata.

`data_manifest.json` contains only12 valid DEV entries with standardized case_id/split/group(dev12)/input_path_linux/input_sha256/metadata_path/metadata_sha256/stats(operations,probe_count,penalty)/family/lineage_id/parameters. Audit scanned all1,800,000 new operations and verified counts, phases, keys, tuple sizes, partition capacity, header/metadata agreement and full SHA. Maximum partition/M is0.495700583; input bytes total36,559,012. No earlier input body was rescanned. `review.json` binds the full-audit summary, manifest and static source review; `artifacts.json` records their hashes.

Do not inspect R82 policy results on this panel before the R82 candidate identity freezes. This directory contains no performance results and makes no candidate selection.
