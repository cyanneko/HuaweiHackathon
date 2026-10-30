# R70 first usable train teacher portfolio

Priority update from Root: deliver the verified 24-train teacher manifest before new parameter sweeps or million reruns. No NN fitting here; Root coordinates training only after generation/verification.

- Only `tmp/r70_inputs/manifests/train.generated.json`, 24 whole train cases. Never dev or holdout labels.
- Existing future FIF, cost-aware and size-time single-first; existing Root interval density/short/sqrt_time only when no INSERT occurs after any PROBE. Mixed cases explicitly skip static methods.
- Actual official Naive/R65 baselines retained as complete feasible guards, not approximated with a Python ID tie.
- Evaluate all supported complete methods; choose by exact integer G; independently compact-official replay the selected complete winner before final teacher manifest emission.
- Per-case outer budget 30s, total 720s, nonformal algorithm wall time; source/input/config frozen; preserve verified A on failure/timeout. Short output `tmp/r70` avoids known Windows long-path issue.
- API `Context(case, deadline).chooser(method)` and `complete_rollout(case, method, context, deadline)` preserve method parameters and full witnesses. Actual C++ baselines remain witness-only.
- No future data enters NN features here; no Q or unchosen-alternative cost labels. Every output is best-found, not proven optimal.
