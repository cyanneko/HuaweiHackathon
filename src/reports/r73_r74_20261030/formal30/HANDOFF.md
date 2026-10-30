# R74 slow-version formal comparison handoff

Complete: 30/30 valid, zero failures/timeouts, five methods × original six full R72 cases × one run. Controller wall time 140.314s. CPU released; no command remains running. No compilation, training, added candidate or repeat occurred in this formal execution.

Final artifacts:

- `conclusion_zh.md` and `conclusion_facts.json`: interpreted findings and exact comparison values.
- `report_zh.md`: all 30 per-case IO/miss/total-cost/D/wall measurements and distributions against both fresh controls.
- `report.json` and `per_run.csv`: complete structured and tabular values.
- `completion_verification.json`: official-parser/raw SHA/identity checks, unchanged six input/meta identities, cleaned process ownership and independently recomputed summary values.
- `negative_diagnostic_evidence.json`: separate historical synthetic_09 physical-cost regression, independently recomputed as 1.9940132867 at penalty1000. This is not one of the 30 formal measurements.
- `raw_archive_manifest.json`: hashes for all original raw files.
- `raw_results30.zip`: 177 files including 30 raw cells, selected source/TU snapshots and reporting artifacts; 155953 bytes; SHA-256 `067fb55514fef6f0f371839eda5181b8e3025a00627288f4fd57a01dcada5a49`. Every archive member was checked against its original bytes/SHA.
- `artifact_manifest.json`: final report/archive fingerprints.

Root producer and release were bound before launch. The R74 modes retain the original prior1 term; p32 is a separate control. Naive was not retimed and is labeled as an auxiliary historical R72 reference throughout.

Original policies, selection, precommit, raw outputs and report JSON remain preserved. Synthetic `diagnostic_report_checks` fixtures and unused compile-only preparation code are excluded from formal results and from the raw-results archive. The local archive preserves original runtime command paths; repository publication should use the owner's portable export separately, without rewriting raw evidence.

Any LUT follow-up is a separate new campaign under `tmp/r74_fast_eval`, pending final identities and Root compute release. It does not modify or append to this completed 30-cell campaign.
