# Dataset average scoring plan

Spec: ../specs/2026-10-27-dataset-average-score.md

1. Add failing functional tests: discover a fourth member; explicit selection is partial; unequal-sized sets yield equal-weight mean 27.5; empty sets excluded; invalid new member fails; legacy/no-baseline unavailable. Add a direct calculation test for case/repeat/cap order yielding 13.75.
2. Update evaluation/evaluate.py: automatic member discovery, schema 3 selection metadata, per-dataset normalization and final arithmetic mean, clear console output. Keep raw-cost aggregate separate.
3. Run the full small-fixture unittest suite after coordinating the timing slot. No real solver/performance workloads. Read-only review the scoring change.
4. Update public docs and sync main to datasets and source/cyanneko. Preserve all existing source/data bytes and VERSION files.
5. Add the verified frozen R53 scheduler to src/methods/r53 with original-byte hash, provenance and bounded historical results; no binaries or new long streams.
6. Verify Git blobs, push the authorized branches and report commits. R54 data is a separate pending handoff after research-side review.
