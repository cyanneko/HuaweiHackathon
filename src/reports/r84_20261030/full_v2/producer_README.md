# R84 full original-data regression: pre-execution v2

Scope: all 12 dyna inputs (original train6/dev3/holdout3) and all 72 final v2.1.0 eval inputs. Both are exposed regression scopes. No final train, inde_dataset or other member is silently included.

Seven frozen methods: Naive, R75_dense_switch, R79_adaptive, R80_next_hier_fast100, R80_paired_hier_fast100, R81_op256_cond2048, Van_latest. Expected matrices: 84 and 504 cells. Official per-cell timeout60s; separate internal controller budgets900/600s; serial one repeat. No retry/resume. All existing artifacts use exclusive create and remain immutable.

Static inventory has only metadata SHA, manifest-declared input SHA, file-size checks and six historical source/TU checks. It does not replace Root's full input hashing. Master/Root proof is fixed to remote datasets commit `d144cdd1c3b78f9a73702b4facb382e6a3e31212`; the cached commit remains `01e9de234cc735bc442f020c8b1b503d961543db` and the two selected dataset trees are unchanged; latest means its captured verification, not later remote movement. All seven ELF identities are rechecked during Linux prepare/run.

Van's immutable standard producer is ready at `tmp/r84_van_build/producer.json`; its reviewed proof adapter is `tmp/r84_van_build/latest_proof.json`. The captured latest source commit is `d92ceb0262b556eb57aae61127d062174ffe6016`, branch `source/Vanius0525`, path `src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp`. The exact source/TU/ELF match the previously compiled Van_paired_penalty100, so this is verified reuse, not new compilation. Environment disclosure is pinned from `tmp/r84_van_build/environment.json`, while the original build record remains authoritative for the reused binary. The adapter schema is:

```json
{
  "status": "VERIFIED_LATEST_SUBMITTABLE_AT_CAPTURE",
  "method_name": "Van_latest",
  "source_commit": "<40 hex immutable source commit>",
  "source_branch": "<verified author branch>",
  "source_repo_path": "<exact submit class path in that commit>",
  "source_sha256": "<exact submitted class bytes SHA256>",
  "unmodified_class_behavior": true,
  "evidence_path": "<workspace-relative Master original identity proof>",
  "evidence_sha256": "<SHA256 of that proof>"
}
```

Root execution commands from Linux workspace root, after producer/release/test proof is ready:

```sh
python3 tmp/r84_full_eval_v2/regression.py prepare dyna
python3 tmp/r84_full_eval_v2/regression.py prepare final
python3 tmp/r84_full_eval_v2/regression.py run dyna --cpu-window-released
python3 tmp/r84_full_eval_v2/regression.py run final --cpu-window-released
python3 tmp/r84_full_eval_v2/regression.py combine
```

Run only under Root's exclusive CPU window; preparation hashes all84 inputs before timing. The unchanged execution core performs additional per-case input integrity hashes during each controller window, so controller wall time includes them; reported D is native framework callback time, not that wall time. Each window gets fresh same-window Naive. The core uses its historic `r80_` executable-cache directory prefix, but the cache key is this new immutable R84 selection SHA and every binary is rehashed.

`release.json` freezes the runner, scorer, protocol tests, final static review, latest-version proofs and environment disclosure before bind/prepare. All of these hashes enter each selection's dependencies and are rechecked before execution.

Primary per-dataset aggregate is `finalized_summary.json`, gated by `completion_gate.json`. The unchanged core `summary.json` and `completion.json` remain visible. This extra gate prevents a controller error after the last native cell from being mistaken for a complete run. Incomplete windows keep logs, rows, missing/invalid lists and null overall aggregate. No historical partial run is substituted.

Scores are per-case `clip(10*(1-C/B),0,10)`, except official C<=0 or B<=0 gives0. C includes physical IO + actual evaluation penalty*miss + D. Raw cost reduction and negative raw points remain visible. Undefined ratio denominators are counted, never disguised as defined observations. Quantiles use nearest rank and retain each dataset's own denominator; they are not averaged across datasets.

`combined_dataset_equal.json` averages the 12-case dataset mean and the72-case dataset mean with weights0.5/0.5. It never pools84 point cases. No automatic promotion or all-member/hidden-score claim follows. Master later maps these exact pre-run file/binary hashes to published artifact commits via an external manifest, without changing frozen selections or results.

V1 is preserved byte-for-byte. Its method bind succeeded, but dyna prepare failed before input hashing/selection/campaign because Windows dependency keys used backslashes. V2 canonicalizes only workspace-relative dependency keys, rejects collisions, and still compares the entire inventory. It also pins the approved newer remote proof; every case, input SHA, metadata SHA and parameter remains identical. The already-bound seven-method dictionary is copied unchanged, so no new bind, compilation or scheduler execution occurred. See failed_preparation.json and inventory_revision.json.
