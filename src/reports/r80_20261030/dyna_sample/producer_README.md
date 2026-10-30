# R80 dyna existing_eval6 regression sample

Frozen selection: `selection.json`, SHA256 `3bad1352e30a5a74ab1ac5b5bbcd5887859677d15a1cb5a9dc245435acd508e2`.

The six case IDs and order are copied unchanged from the earlier R77 `existing_eval6_case_ids`: slow/shared, slow/staggered, fast/shared, fast/staggered, burst/shared, burst/staggered. Original splits are four train and two dev. They are previously exposed regression inputs, not blind tests; this preparation authorizes no training. No original holdout case is included. Each input has 5,000,000 operations.

Fixed dyna1.0.0 identity:

- manifest SHA256: `2ddcec4fd7ce5b7f37e92bb850a24abf66a5769de55cb543854ae412f035d038`
- dataset SHA256: `4ff12f2e8f6441c2a4040535c4782ede6cd7b7adde6340a7a1702701091206cf`
- VERSION SHA256: `59854984853104df5c353e2f681a15fc7924742f9a2e468c29af248dce45ce03`

Input locations come from the R77 contract and declared input SHA values match both fixed published contracts. The preparer verified all six file sizes, six headers and twelve small metadata hashes (original and published copies), counts, parameters and partition capacity. No complete input was hashed or scanned; the runner must verify actual input SHA before execution. `audit.json` counts the preparation script's 44 header lines and zero operation lines. Preliminary format inspection also displayed the first three INSERT lines of one case; it did not scan the input body.

The five method records are copied exactly from frozen R80 final24 selection: Naive, R79 adaptive, Van paired penalty100, R80 paired hierarchy fast100, R80 next hierarchy fast100. No method or threshold changes are included.

Planned evaluation is serial, one repeat, 30 cells, with a separate 360-second controller budget and the unchanged official 60-second limit per cell. First compute six equally weighted per-case scores against same-run Naive, including D. Report this dyna6 mean separately, then compute `(dyna6_mean + final24_mean) / 2`. Do not pool the 30 cases into one equal-case mean, or combine their decision timing as one execution round. This folder contains no policy results.
