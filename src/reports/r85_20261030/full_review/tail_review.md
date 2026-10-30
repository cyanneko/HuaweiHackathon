# R85 full-regression independent tail review

PASS:96 dyna +576 final cells;1344 current stdout/stderr SHA verified and independently reparsed. Six identical controls×84 inputs=504 pairs have exactly identical IO/Hit/Miss to R84; their1008 historical stdout/stderr SHA were also checked. D is measured and was not required to repeat.

Source classes, TUs, original ELFs and both executed ELF caches were actually rehashed in Linux, and normalized official skeleton checked. Full input bodies were not read or rehashed by this reviewer: their identities are tied to frozen inventories, prepared input gates and per-row identities. All84 metadata SHAs were read/checked.

主分含D；physical sensitivity同时从候选与同轮Naive分母去除D，只作敏感性分析。两个dataset各50%，不池化84例。12例P90为第11秩，72例为第65秩；不沿用6例P90=max规则。

|Candidate / parent|Equal clipped delta|Equal raw delta|Physical-only clipped delta|Physical-only raw delta|
|---|---:|---:|---:|---:|
|R85_fast_prior8 / R81_op256_cond2048|+0.003361007|+0.003963400|+0.003349085|+0.003961641|
|R85_hier_anchor / R80_next_hier_fast100|+0.012583229|-0.026575033|+0.013552786|-0.024998666|

A的均分增益很小，并非两dataset一致改善。B的裁剪均分上升不能覆盖raw退化：零分下的负改善会被裁剪隐藏。物理敏感性不是主榜，也不是去除所有实验噪声后的官方分。

|Dataset|Candidate/reference|Mean ratio|P50|P90|Worst|W/T/L|Worst case|
|---|---|---:|---:|---:|---:|---|---|
|dyna|R85_fast_prior8/R80_next_hier_fast100|0.965576214|0.975591923|1.000499625|1.000735715|10/0/2|train_burst_staggered_06|
|dyna|R85_fast_prior8/R81_op256_cond2048|0.987535977|0.998697471|1.000030171|1.000288096|10/0/2|dev_burst_staggered_09|
|dyna|R85_fast_prior8/Van_latest|0.904017086|0.910614728|0.978658196|0.996685070|12/0/0|dev_burst_staggered_09|
|dyna|R85_hier_anchor/R80_next_hier_fast100|0.999974334|0.999850046|1.000366126|1.002598921|8/0/4|train_burst_shared_05|
|dyna|R85_hier_anchor/R81_op256_cond2048|1.024442028|1.008941320|1.074620507|1.136171032|5/0/7|holdout_fast_staggered_11|
|dyna|R85_hier_anchor/Van_latest|0.935926228|0.933257192|0.995807649|0.996063052|12/0/0|dev_burst_staggered_09|
|final|R85_fast_prior8/R80_next_hier_fast100|1.008774445|1.000401616|1.041352262|1.214907635|20/0/52|eval_059_random_zipf|
|final|R85_fast_prior8/R81_op256_cond2048|1.005646423|1.000006461|1.041468475|1.213482993|30/0/42|eval_050_random_zipf|
|final|R85_fast_prior8/Van_latest|0.956159216|0.989954018|1.025936534|1.213219335|47/0/25|eval_044_random_zipf|
|final|R85_hier_anchor/R80_next_hier_fast100|1.004607582|1.000001709|1.028115286|1.451271565|32/0/40|eval_059_random_zipf|
|final|R85_hier_anchor/R81_op256_cond2048|1.001041978|0.999288556|1.044112392|1.142593123|39/0/33|eval_059_random_zipf|
|final|R85_hier_anchor/Van_latest|0.950330328|0.991836099|1.020811768|1.058628063|47/0/25|eval_055_random_zipf|

## 双方同为零分且候选更差的点

|Dataset/case|Candidate|Cost/parent|Physical/parent|Raw delta|
|---|---|---:|---:|---:|
|final/eval_063_random_zipf|R85_fast_prior8|1.010198161|1.010179960|-0.105282319|
|final/eval_065_random_hotspot|R85_fast_prior8|1.033504714|1.033639641|-0.403076079|
|final/eval_075_random_hotspot|R85_fast_prior8|1.000026631|1.000000000|-0.000373743|
|final/eval_006_random_hotspot|R85_hier_anchor|1.007328392|1.006932353|-0.080788519|
|final/eval_059_random_zipf|R85_hier_anchor|1.451271565|1.446515273|-5.052684845|
|final/eval_063_random_zipf|R85_hier_anchor|1.005632892|1.005371867|-0.056412311|
|final/eval_065_random_hotspot|R85_hier_anchor|1.037061555|1.035322035|-0.446958936|
|final/eval_075_random_hotspot|R85_hier_anchor|1.000138595|1.000000000|-0.001945089|

## 损失机制族（对各自直接父版）

|Candidate|Dataset/family|N|Clipped delta|Raw delta|
|---|---|---:|---:|---:|
|R85_fast_prior8|dyna/burst_staggered|2|-0.001178209|-0.001178209|
|R85_fast_prior8|final/random_hotspot|28|-0.026494564|-0.040895719|
|R85_fast_prior8|final/random_lognormal|16|-0.005777926|-0.005777926|
|R85_fast_prior8|final/random_zipf|28|-0.022138340|-0.004639161|
|R85_hier_anchor|dyna/burst_shared|2|-0.008938439|-0.008938439|
|R85_hier_anchor|dyna/fast_shared|2|-0.001175709|-0.001175709|
|R85_hier_anchor|final/random_hotspot|28|-0.005343944|-0.024261535|
|R85_hier_anchor|final/random_lognormal|16|-0.048285437|-0.048285437|

范围：这里仅原dyna12/final72完整回归。新18例TRAIN/DEV结果未导入、未改标签、未合并计时或均分。这些原数据已曝光，单次repeat不能证明泛化或无噪声优越。审查PASS只表示结果/身份/数学可复核，不自动授权替换冻结R75默认或修改候选。
