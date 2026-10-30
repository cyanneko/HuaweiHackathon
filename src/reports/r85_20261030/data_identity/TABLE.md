# R85 frozen18-case preparation

Not generated. Root generation/full-audit window required. All18 seeds independent; no pairing. W/R=100/80 at scale1,6400/5120 at scale64. AllN150000. Dynamic expected build fraction.4 with naturally sampled actual counts; IID exact build60000 and probe90000−K. Both sources unchanged.

|#|Split|Mechanism|Seed|K|P|M MiB|Pressure|BW scale|Penalty|Period|Rare|
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
|1|train|slow_shared|202610310601|2|16|64|1.25|1|1|17|hot|
|2|train|slow_staggered|202610310602|4|64|256|3|64|100|1000|none|
|3|train|fast_shared|202610310603|8|32|1024|1.25|64|1000|127|none|
|4|train|fast_staggered|202610310604|2|64|256|3|1|100|17|none|
|5|train|burst_shared|202610310605|4|32|1024|1.25|1|1000|1000|none|
|6|train|burst_staggered|202610310606|8|16|64|3|64|1|127|hot|
|7|train|random_zipf|202610310607|4|32|1024|3|1|100|1000|IID shape|
|8|train|random_hotspot|202610310608|8|16|64|1.25|64|1000|17|IID shape|
|9|train|random_lognormal|202610310609|2|64|256|3|64|1|127|IID shape|
|10|train|random_zipf|202610310610|8|16|64|1.25|1|1000|17|IID shape|
|11|train|random_hotspot|202610310611|2|64|256|3|1|1|127|IID shape|
|12|train|random_lognormal|202610310612|4|32|1024|1.25|64|100|1000|IID shape|
|13|dev|slow_staggered|202610310613|8|32|1024|1.25|64|1000|127|none|
|14|dev|fast_shared|202610310614|4|16|64|3|1|1|1000|hot|
|15|dev|burst_staggered|202610310615|2|64|256|1.25|1|100|17|none|
|16|dev|random_zipf|202610310616|2|64|256|3|64|1|127|IID shape|
|17|dev|random_hotspot|202610310617|4|32|1024|1.25|64|100|1000|IID shape|
|18|dev|random_lognormal|202610310618|8|16|64|3|1|1000|17|IID shape|

TRAIN pressure×BW cells each3; DEV counts1/2/2/1 (p1.25 low/high,p3 low/high). Each split has equal K/P/M/penalty margins, equal pressures and bandwidths. Each of six mechanism families spans all K/M/penalty levels across its three independent seeds. This is coverage, not a full factorial or matched causal experiment.

Three dynamic rare-hot cases: TRAIN01/06 and DEV14. Preserve any illegal capacity realization or timeout; never substitute a seed. IID hotspot is a static family distribution, distinct from persistent rare-hot anomaly.

Root must review config/commands/source identity before granting90s. Audit will stream every input once: headerN/K/P/M/W/R/penalty/period; operation count/phases/K SWITCH; key and tuple bounds; build/probe perop and partition counts; final partition bytes/max<=M; realized pressure; metadata/config agreement; fullinput/meta/body/operation/partition streamSHA; seed/split/SHA separation. Actual dynamic pressure can differ from requested; no resampling.

DEV is reserved until candidate identity freeze; subsequent plan calls for complete TRAIN and DEV diagnostics, not blind official testing.
