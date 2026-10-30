# R87 wrapper interface

This directory owns only the evaluation wrapper, not the scheduler. Static preparation uses Linux Python to avoid Windows/Linux float-summation differences. Neither static command below runs a scheduler or reads complete input streams.

1. After producer READY: `python3 -B prepare_static.py --producer-sha256 <exact SHA>`.
2. After Root review and approval: `python3 -B freeze.py --root-approved`.
3. Root only, full prepare: `python3 -B regression.py prepare dyna`, then `python3 -B regression.py prepare final`.
4. Root only, separate quiet windows: `python3 -B regression.py run dyna --cpu-window-released`, then corresponding `run final`.
5. Both finalized gates PASS: `python3 -B regression.py combine`.

All outputs are write-once. Failure leaves partial evidence; do not delete or silently reprepare. Test-only scratch is retained. `test_r87.py` combines inherited R85 score/completeness/error tests with actual R87 parent score calculation, hard old-version checks and producer parent identities. `test_r87.py --parent-red` intentionally fails against unchanged R85 scoring because that matrix requires the now-excluded paired method.

The seven historical controls are copied by full dictionary from R85, including author source attribution and build hashes. Van's source is unchanged; captured evidence commit6ded7022215b80a8edf4170faefe1ca4da16814f is recorded separately without altering the original method dictionary.
