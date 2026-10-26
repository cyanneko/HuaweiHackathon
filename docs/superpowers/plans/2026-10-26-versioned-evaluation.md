# Versioned Evaluation Implementation Plan

Historical implementation plan. On 2026-10-27 the user removed the requirement for all three datasets: evaluate only available nonempty sets, record their exact versions, and list skipped members. The current spec and evaluator supersede the original three-member availability constraint below.

> **For agentic workers:** Use superpowers:executing-plans to implement the following tasks inline.

**Goal:** Run three members' evaluation sets and bind every report to their exact versions.

**Architecture:** A standard-library CLI snapshots three versioned directories, validates and executes each case, and writes an auditable report. Common tooling lives on main and is inherited by datasets and source/cyanneko.

**Tech Stack:** Python 3.10+, unittest, Git, GitHub CLI.

**Spec:** ../specs/2026-10-26-versioned-evaluation.md

## Global Constraints

- Exactly three members, configurable names; defaults cyanneko, member2, member3.
- No dependency installation or migration of original research files.
- Raw cost only, no claim of official normalized score or action-level verification.
- Empty or failed evaluation cannot yield a successful overall score.

## Review Focus

- Same VERSION with changed case bytes must change suite ID.
- Train-only changes must not change suite ID.
- Empty/missing data, missing VERSION and malformed candidate output must fail.
- Program failure/timeout or mutation of snapshot must invalidate results.
- Output collisions must preserve existing reports and input files.

## Task 1: Implement the batch evaluator

Files: evaluation/evaluate.py, evaluation/tests/test_evaluate.py.

- [x] Write CLI tests using real temporary datasets and small subprocess candidates. Cover all five review risks, three-version output, successful aggregate, stdin and filename input.
- [x] Run unittest and observe missing evaluator failures.
- [x] Implement snapshot discovery, hashes, input audit, subprocess execution, metric validation and non-overwriting JSON reports.
- [x] Run the full repository unittest suite and fix failures.

## Task 2: Publish the collaboration scaffold

Files: README.md, evaluation/README.md, evaluation/DATA_SPEC.md, branch-specific dataset placeholders and src/README.md.

- [x] Document command syntax, cost meaning, VERSION maintenance and fingerprint comparison.
- [x] Commit main; create datasets with three train/eval pairs and VERSION files; create source/cyanneko from main.
- [x] Create private cyanneko/HuaweiHackathon and push the three branches.
- [x] Verify remote visibility, branches, common files and dataset directory tree.

## Verification record

- 22 unittest cases passed on Windows / Python 3.13; no research workload was timed.
- Three remote branches verified; repository PRIVATE and default main.
- Three empty train/eval directory pairs created, eval VERSION initialized to 0.1.0.
- Default protocol is official-2026-10-26; explicit legacy mode remains available.
- Read-only review findings for per-invocation input/program identity and timeout cleanup were reproduced and fixed.
