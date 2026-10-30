# Final dataset v2 strong-method benchmark plan

> Execution: the user requested an actual benchmark and checks of teammates' latest updates. The testing agent executes this plan directly, coordinates CPU windows through the Main Agent, and writes only in this benchmark directory. Shared Git writes remain with Master.

**Goal:** Compare current strong online methods on all 50 final_dataset v2 eval inputs and give a supported recommendation.

**Architecture:** Freeze exact Git data/source revisions and local experimental policy bytes. Use the unchanged saved official framework with only the scheduler class/factory replaced. Compile all selected methods with identical C++14/O2 settings, run serially in Linux with measured official callback D, preserve every raw result, and aggregate against the same official Naive per input/repeat.

**Tech stack:** Python standard library, existing official-compatible C++ framework, g++ -std=c++14 -O2, WSL Linux, native temporary storage for timed processes.

**Spec:** User requests in this testing chat: benchmark current good methods with GitHub final_dataset, check teammate updates, and report conclusions. Main Agent requests complete 50-case coverage, uncapped scores, distinct experimental labels, no offline R67/R68 in online ranking, and coordinated compute windows.

## Constraints and checks

- Data: datasets commit 33ab5af221069fe8b8832fd77e85563e9997633a, final_dataset/eval VERSION 2.0.0; export only eval and needed metadata, not the 500 train inputs.
- Remote teammate heads checked: Vanius0525 9c755a71b26f5a0937dbbfc7edf68272b3510e72; liunianwww 0c6d963a1fcc364ecdf763c638571358928bab42. Check changes and current source recommendations before finalizing candidates.
- Initial candidates: official Naive, Vanius adaptive and AI, liunian final, Single-Fit phase, R63 Ghost, R65, Clean, FitTie, BBP. Mark Clean/FitTie as ablations and BBP as experimental; document any additions/removals following source review.
- Freeze input, metadata, policy, framework, full translation unit, binary, compiler, and runner identities. No parameter tuning or score-based input selection.
- One serial solver at a time; 60-second timeout per formal invocation. First scheduled scope is 14 methods × 50 inputs × one repeat = 700 cells. Two later repeats require separate scheduling. Incomplete grids remain explicitly incomplete. Checkpoint all completed cells between windows.
- Total_Score includes official callback D; wall time stays separate. Do not use instrumented binaries for performance.
- Validate all five output fields, hit+miss against Probe count, and cost formula with the existing frozen parser. A failed/timeout/missing cell cannot be silently dropped for a full score.
- Primary: sum of original clipped per-case contributions, mean over repeats. With one selected dataset there is no three-member averaging. Also report mean-case contribution, capped raw score, costs/Naive and D, median/P90/worst, W/T/L and all individual cases.

## Tasks

- [ ] Read both teammates' new source revisions; list meaningful source changes and unchanged aliases.
- [ ] Freeze selected current methods and source hashes with Main/Master coordination.
- [ ] Export and independently validate all 50 eval inputs and compute the actual suite identity.
- [ ] Prepare unified framework translation units and a resumable serial runner. Test output/timeout/partial-grid handling with small fixtures before timed runs.
- [ ] In the assigned window compile, smoke-check, and measure the complete case/method/repeat grid.
- [ ] Verify identities and result completeness, aggregate existing raw results, produce per-case CSV and a readable Chinese report, and send Main Agent the conclusion and evidence.

## Review focus

Check latest recommended teammate source rather than old method names; preserve official Naive equal-size sorting; keep full 50-case identity distinct from any smoke subset; retain failed and regressing cases; keep offline future-aware methods outside the online table.
