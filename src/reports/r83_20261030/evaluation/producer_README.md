# R83 runner

Only `experiment.py`, `test_protocol.py`, review/release records are new. It imports unchanged R80 execution/parser helpers; no scheduler build or implementation change. `prepare` verifies all source/TU/ELF and framework identities, data audit/release signatures and evaluator dependencies. It hashes metadata only; actual execution core checks each large input SHA before and after running that case.

Original plan plus user amendment are pinned by exact SHA. TRAIN is all valid declared12 ×8 methods (96 cells if complete). DEV is all valid declared6 ×8 methods (48 cells if complete), independent of whether TRAIN diagnostic choice is empty. Both have180s controller watchdog and60s official per-cell wall limit, one serial repeat. DEV remains development validation, observed after execution.

Root runs these commands from Linux with the shared workspace mounted; implementer did not prepare or run them:

```text
python3 ${WORKSPACE}<LOCAL_TEMP> prepare train
python3 ${WORKSPACE}<LOCAL_TEMP> run train --cpu-window-released
python3 ${WORKSPACE}<LOCAL_TEMP> prepare dev
python3 ${WORKSPACE}<LOCAL_TEMP> run dev --cpu-window-released
```

The `run` flag is an explicit Root CPU-window assertion, not automatic permission to contend with another run. Selection files and campaign outputs are immutable; no silent repeat/resume. DEV verifies TRAIN campaign, complete cells, summary/rows/choice, exact method dictionaries and same data manifest. Its candidate subset is always all eight under the amendment.

`summary train|dev` independently reruns the local arithmetic over saved rows and validates an existing summary, or writes one only if absent. This summary never invokes schedulers.

Scores use same-run Naive and include D. Diagnostic choose considers only R79, paired R80, R81op256 and the two R82 variants; at most two need strict mean-score improvement over R80 hierarchy, positive defined Naive/parent denominators and worst cost/parent≤1.25. Ties use lower D then name. There is no D hard veto or old38 veto, and diagnostic selection never promotes the default.

Outputs preserve clipped score, raw unbounded improvement, physical IO+penalty×miss, D, ratios/P50/P90/worst, dynamic/IID and bandwidth groups, each lineage, and low/high changes only for complete pairs. Missing generator cases/failures and expected18 counts remain in selection/summary. Sample mean is not claimed equal to equal-lineage mean if a planned TRAIN pair is incomplete. R82 DEV12 remains untouched.
