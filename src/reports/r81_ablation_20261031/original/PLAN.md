# R81 Frozen Ablation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Root delegated implementation to this agent; shared Git is owned by Master.

**Goal:** Produce a reviewable, full nine-method R81 ablation evidence matrix without optimizing the final algorithm.

**Architecture:** Exact child-source deltas from the named frozen parent; targeted synthetic mechanism checks; reuse the frozen R87 execution and completion logic in an independent wrapper. Bind all three complete selections before timing and require both full-grid and controller gates.

**Tech Stack:** Python standard library, official C++14 framework, g++ -O2, serial Linux CPU.

**Spec:** `tmp/r81_ablation_20261031/DESIGN.md`

## Global Constraints

All artifacts under this folder; do not edit parent, historical evidence, framework or shared Git. Nine methods × 94 full cases = 846 new cells, one repeat, no retry/resume, no tuning/promotion. Total formal wall budget2200s inclusive; local caps1000/500/450s and per-cell60s, global deadline first. D newly measured. Old dyna12/final72 each mean then50/50; stat10 separate. Native compilation and runs require Root's explicit window.

## Review Focus

* A source drift must fail before child generation; hash and exact reverse-delta tests own this.
* A dead/miswired switch must fail targeted synthetic mechanism tests before performance.
* Missing/failed/duplicated cells must retain846 planned denominator and forbid official aggregate.
* An exception after the last valid row must fail finalization despite a full row grid.
* A changed dependency or surviving child must fail the completion gate; no reused D.

### Task 1: Exact children and tests

Files: `generate.py`, `sources/*`, `patches/*`, `test_sources.py`, `effectiveness.cpp`, `source_manifest.json`.
Interface: `generate.generate() -> manifest`; child policy/TU paths and hashes consumed by runner.

- [ ] Write static tests for seven exact deltas, source identity, method order and no altered framework.
- [ ] Implement deterministic generation with exact-one replacement assertions and reversible deltas.
- [ ] Generate only text/source artifacts; run Python static tests without native compilation.
- [ ] Write tiny synthetic C++ checks covering each disabled action/formula and retained state.
- [ ] Root reviews the exact patches and tests before opening native window.

### Task 2: Frozen full contract and runner

Files: `runner.py`, `scoring.py`, `test_protocol.py`, `release.preparation.json`.
Interface: `runner.freeze()` binds source/meta-only case manifests; `runner.attempt()` compiles, tests, prepares all inputs, runs all suites and finalizes once after GO.

- [ ] Reuse R87 metadata inventories and official helper/parser; adapt stat10 from its existing manifest.
- [ ] Add global deadline, source/framework/ELF/input gates, no retry/resume, rotated9 order and exact method/case list checks.
- [ ] Test negative/undefined score, equal-suite means, invalid/missing/duplicate grid and final-cell exception guards using tiny metadata-only fixtures.
- [ ] Freeze code/dependency hashes in preparation release and report compile/native counts0.

### Task 3: Authorized formal attempt and evidence

Files: `GO.json`, `attempt.json`, `build/*`, `{dyna,final,stat}/*`, `REPORT.md`, `per_case.csv`, `verification.json`.

- [ ] After Root opens CPU window, begin2200s clock, compile exact flags and verify Full ELF parent equality.
- [ ] Run tiny effectiveness checks, then prepare all94 full input identities and selections before timing.
- [ ] Run serial108+648+90 cells with fresh Naive and D; stop/retain failures and planned denominator.
- [ ] Reparse five metrics and source/output hashes read-only; require controller success after last row and active children0.
- [ ] Export all cases, raw/clipped scores, IO+miss/D, losses and suite P50/P90/worst; compare known Full/Naive physical metrics only.
- [ ] Report primary50/50 and separate stat, conditional nonadditive contributions, observed data and timing limits.

No commits by this agent. The plan was self-reviewed against the design, including all seven switches, full matrix, budgets and all completion gates.
