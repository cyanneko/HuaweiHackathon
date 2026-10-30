# R81 frozen data panel

All18 newly generated cases passed complete input audit:12 TRAIN and6 reserved DEV, each150,000 operations. Generation plus full audit took9.926349 seconds. No generator failure, replacement seed, scheduler execution or training occurred. CPU is released. New inputs total2,700,000 operations and54,751,717 bytes; maximum partition/M is0.6339820772. Old26 inputs are references only and were not rescanned or modified.

Use `train_manifest.json` for the38-case training panel and `reserved_dev_manifest.json` only after candidate identity freezes. `data_manifest.json` combines all44 entries and must be filtered by split before evaluation. Every entry provides case ID, split, Linux input/metadata paths, input/metadata SHA, normalized operations/probe_count/penalty stats, family, group, lineage and parameters. New TRAIN group is `new12`, DEV is `dev6`, and old references are `old26`.

|Mechanism|TRAIN seed|Pressure|Penalty|DEV seed|Pressure|Penalty|DEV rare|
|---|---:|---:|---:|---:|---:|---:|---|
|slow_shared|202610310101|3|1|202610310201|6|100|none|
|slow_staggered|202610310102|6|100|202610310202|3|1000|hot|
|fast_shared|202610310103|6|100|202610310203|3|1000|none|
|fast_staggered|202610310104|3|1000|202610310204|6|1|hot|
|burst_shared|202610310105|3|1000|202610310205|6|1|none|
|burst_staggered|202610310106|6|1|202610310206|3|100|hot|

Each TRAIN row has an ordinary/rare-hot pair sharing every parameter and seed except `rare`. The12 TRAIN files represent six independent new seed lineages, not12 independent seeds. DEV has six distinct seeds disjoint from TRAIN. Input SHA sets are also disjoint. Penalties1/100/1000 occur four times each in TRAIN and twice each in DEV. Latin rotation moves each mechanism to a different penalty across splits; this is not a full factorial design. DEV's predeclared none/hot alternation aligns with shared/staggered, so DEV alone cannot isolate rare effects from phase. Rare hot changes both INSERT and PROBE routing and hence partition sizes, not only access frequency. True penalty is evaluation metadata, not a new policy feature.

Defaults remain K8/P64/M64MiB/B127, write100/read80, build fraction0.4, partition-speed0.0025, partition-profile slow, and windows1000. Pressure3/6 avoids the previously known extreme12 configuration without changing the generator probability model. The original26 retain their old paired-lineage definitions and two original rejected R80 hot inputs remain rejected; nothing was regenerated to fill those gaps.

Before generation, `config.json`, `commands.json` and `selection.json` bound the exact18 configurations and generator/script SHA. `pre_interface_revision/` preserves the initial static freeze; the later standard-interface adjustment did not change any seed or generator parameter. Generation used the stricter frozen30-second internal limit within Root's later60-second authorization.

Audit scanned every new operation, checked type/phase/keys/size, per-operator build/probe header counts, all switches, exact N, all partition bytes, maximum partition capacity, requested/realized pressure, metadata agreement and SHA. Old26 comes directly from the frozen R80 evaluator selection, with its SHA retained and earlier manifest supplying parameters/lineage. No DEV policy scores have been produced or read.

`new_cases.csv` gives all18 detailed identities and counts. `generation_audit_summary.json` binds the final manifests. `source_review.json` records the separate read-only R81 formula/test coverage review; no native tests were repeated by this reviewer.
