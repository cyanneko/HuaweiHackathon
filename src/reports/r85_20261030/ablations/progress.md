# R85 implementation ledger
Plan: docs\superpowers\plans\2026-10-30-r85-prior-and-anchor-ablations.md
Pre-flight: independent parents; shared official declarations and callback tests only.
Ruling: use authorized tmp/r85_ablations isolation, no Git writes/commits or workspace deletion. Root will perform independent review.
Tests frozen before production generation. Red A uses frozen R81; red B uses frozen old paired to expose its non-hierarchy empty-evidence anchor.
RED: prior oracle fails frozen R81 numeric probability; empty-evidence hierarchy-anchor assertion fails frozen old paired. Full stdout/stderr retained.
GREEN: both official TUs and all directed tests PASS. Parent source/TU/ELF unchanged; no strategy performance runs. Independent Root review follows release.
