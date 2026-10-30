# Final R74 LUT verification handoff

Closed: 18/18 valid, zero failures/timeouts, no compile, no warmup, one process per case/method. CPU released; no command remains running. No further experiments are scheduled.

Same-round operator mean cumulative D: 2.309314768s slow → 2.101556233s fast, ratio0.910034553, reduction8.9965%; all six cases faster. Printed IO/hit/miss exactly match on all six pairs. First-call LUT initialization stays inside callback timing.

Fast coverage mean cumulative D is2.249936865s. Comparison to the prior slow coverage2.426957838s is cross-round auxiliary only (ratio0.927060549). Preserve the negative train_burst_shared_05 cross-round D ratio1.168157434. Printed physical metrics match the historical coverage on all six cases. This is not a per-action trace audit.

Every actual run was below the problem's60s wall limit; maximum5.885780s. The180s value is an internal watchdog, not the official limit.

Final artifacts:

- `report_zh.md`, `report.json`: complete D and physical comparison, including per-case values.
- `per_run18.csv`: all18 original five metrics and actual wall time.
- `completion_verification.json`, `conclusion_facts.json`: raw SHA/identity/parser/cleanup checks and exact result values.
- `slow_evidence_preserved.json`: prior R74 artifact fingerprints unchanged.
- `raw_archive_manifest.json`, `artifact_manifest.json`: final file hashes.
- `raw_results18.zip`:115 files,102031 bytes, SHA-256 `1cf11042ee7999b61450e7537069c54cb371fe5ce90a9011d0db2dbcc909a4bb`; all archived member bytes/SHA verified. Contains all18 raw cells, selected source/TU snapshots and key evidence.

The local raw archive preserves original runtime command paths. Use the repository owner's portable export separately for publication and preserve original raw bytes. Route this completed handoff through Main to Master for archiving.
