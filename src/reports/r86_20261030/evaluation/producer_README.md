# R86 final3 complete regression

Eight unchanged R85 method dictionaries/classes/TUs/ELFs. New native work is only final_dataset 3.0.0 all 72 eval cases (576 cells, serial, one repeat, 650 s controller / 60 s per cell). R85 dyna12 is historical reuse, including its original same-campaign Naive and measured D; it is not rerun. No algorithm change, network training, new input generation, result-driven selection, or default promotion.

Data commit e6613435d59690d6dd768813332387108f7e83c2, final tree 35d4f98b7464e62a9a89b606e41d192380788e76. The independent data agent scanned all 72 eval streams and actual parent sidecar BUILD layouts. The stored publisher 612-case report is separate evidence; we did not rerun train540. Root prepare hashes every new input and checks source/TU/ELF and headers before timing. Probability certificates and offline future counts never enter scheduler arguments: the unchanged core passes only the txt input path to the frozen ELF.

The scorer is an exact byte copy of R85 scoring.py. Per-case costs include measured cumulative D. Both datasets use their own same-campaign Naive. Combined points are half of each dataset mean, never a pooled84 average. Quantiles remain per dataset. Combined `actual_D_total_us` preserves scorer semantics (historical plus new D); explicit `new_measurement_D_total_us` and `historical_reused_D_total_us` prevent it being mistaken for newly measured R86 work.

The inventory uses exact schema4 manifest entries and sidecars, not inferred numeric IDs or final2.1 stats. It verifies all72 new SHA declarations against export and audit evidence. The full original R85 dependency closure, frozen data audit/release, current fixed-tree proof and Van same-source evidence are pinned. Van evidence commit is 6ded7022215b80a8edf4170faefe1ca4da16814f; original eight method dictionaries remain byte-identical, with no fabricated new compilation.

## Root operation order (Linux, workspace root)

Only after runner release is READY:

```bash
python3 -B tmp/r86_eval/check_static.py
python3 -B tmp/r86_eval/regression.py prepare
```

After Root grants the exclusive native window:

```bash
python3 -B tmp/r86_eval/regression.py run --cpu-window-released
python3 -B tmp/r86_eval/regression.py combine
```

There is deliberately no dyna run mode. Do not call the old core directly. `run` verifies full case/method dictionaries and frozen dependencies. `combine` requires successful finalized gates and rechecks historical/new campaign identities, summaries and all rows. A last-cell controller failure, missing/invalid grid, changed identity or active process prevents a complete aggregate. Files use exclusive creation; no silent retries/resume or overwrites. Preserve any incomplete result; do not delete failed cells. Historical dyna logs remain under tmp/r85_full_eval/dyna and are referenced, never copied or relabeled.

`test_protocol.py` and `check_static.py` are pure Python contracts, with no scheduler execution. They cover identity/old-version mutation, missing rows/cases, mismatched reuse methods, dependency normalization/collision and real small-file hash mutation, equal dataset weighting, zero-cost score, nearest-rank quantiles, and a complete synthetic grid followed by a controller exception.

Run static preparation/checks in the formal WSL Python interpreter as well. An initial Windows static-only attempt rejected 39 last-bit floating aggregate differences (Python sum-version behavior); it produced no selection or campaign. `windows_static_attempt.json` preserves that evidence. The strict whole-summary equality gate and historical summary bytes were retained; the same Linux interpreter reproduces them exactly. This was not an algorithm or native-run failure.

Exposure: new PROBE streams reuse previously exposed BUILD layouts; this is a complete versioned regression, not a blind test or an official hidden-distribution guarantee.
