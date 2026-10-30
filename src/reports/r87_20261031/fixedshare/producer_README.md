# R87 fixed-share operator candidate

One candidate, R87_fixedshare_op, from immutable R85_fast_prior8. Two decayed operator forecasters retain half-lives256/2048 and priors8.009479828345365/64. A new accepted next-PROBE label is scored before insertion into either forecaster. The fast weight is updated by categorical log-loss likelihood multiplication, then shares alpha=1/256 to the other expert. Skipped time only decays counts; no share transition occurs without a new accepted label. Query-time operator marginal is the weighted mixture. Existing slow partition conditional pooling, proxy100, horizon64, proposal and pruning remain unchanged.

Two new persistent totals and their common clock are independent of temporary query totals. Selected fast/slow counts are advanced to that clock before prediction. Duplicate/old ordinals return before any new learning/count update. Query clock cannot rewind behind accepted lookahead. Dimension changes reset totals/clock/weight and cache. Weight/evidence guards protect nonfinite or invalid likelihoods; this does not claim bit identity to endpoint policies.

## Evidence order and current state

Tests were written first and their hashes saved. Candidate and test-only public-access scaffold were then generated while compilation was forbidden. **No behavioral RED or PASS is claimed before the Root-authorized window.** The window runs the parent behavior test first: it uses only parent-existing sampleNext/ensureProbabilities/ensureProbability and validates actual integrated partition probabilities. Parent compilation must succeed, then its pure-fast output must fail the mixture expectation with MIXTURE_BEHAVIOR_MISMATCH. A missing-field compile failure is never accepted as RED.

The candidate oracle independently sums all timestamped weighted observations in long double and evaluates log-domain expert likelihoods with a transition matrix. It checks marginal/conditional normalization, counts/global totals, pre-insertion likelihood, duplicate ordinals, irregular gaps, no query-only learning, lookahead/no rewind, K1, .5 invariance, nonuniform-weight contraction1-2alpha, long underflow gap, finite recovery, dimension reset and probability-cache epoch rollover. Separate deliberately wrong test-only score-after-insert and uniform-pool recurrences must fail. Legacy callback/refault and 400-callback legality tests are retained; their fixture streams are functional tests, not dataset benchmarks.

All private/public access and incorrect controls live only in test headers. Production class/TU contains none. Parent exact bytes, prefix/suffix and normalized official framework are checked; no C++17 or framework change.

## Root-authorized compile/test command

From Linux workspace root, only after the exclusive 90s window is released:

```bash
python3 -B tmp/r87_fixedshare/build.py
```

The controller is one-shot, serial, total90s including compiler metadata, compilation and tiny functional tests. Each child gets only remaining time and is killed as a process group on timeout. No automatic retry or source edit. All stdout/stderr, exit status, timeout and hashes survive failure. Producer is READY only after every intended PASS/behavioral RED and parent/artifact identity check; release/test_summary preserve any failure. Official flags are -std=c++14 -O2. No performance input or scheduler benchmark is read/run.

The predictive mixture learns on policy-dependent exposed callbacks, not all hidden hits or independent trajectories. Forecast comparison is not an IO/miss/D guarantee. The fixed primary regression is old dyna1.0 full12 + final2.1 eval72 per plan; final3 is supplementary and does not select this candidate. No parameter sweep, training, default promotion or Git change.
