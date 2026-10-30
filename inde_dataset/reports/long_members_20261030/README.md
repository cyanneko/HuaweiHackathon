# inde_dataset 1.1.0 长样例补充评测

新增20例，每例严格N=2,000,000（含INSERT、PROBE、SWITCH），10类场景各2例；训练500不变，测试50→70。
本轮每例每程序只运行一次：两位成员40次、Naive20次，共60次；旧50没有重跑。

| 研究版 | 旧50均分 /10 | 新长20均分 /10 | 合并70均分 /10 |
| --- | ---: | ---: | ---: |
| Vanius0525 | 5.115079 | 6.142982 | 5.408766 |
| cyanneko | 4.913007 | 6.287751 | 5.305791 |

逐例按同批Naive计算clamp(10*(1-C/B),0,10)，包含真实D，再对所有案例等权平均。
合并均分=(旧50均分×50+新20均分×20)/70，不按操作数或家族均分重新加权。
同一程序在不同规模子集上的分差不是算法改进证据；新增长例还有K/P/B等参数差异。

| 程序 | 新20平均累计D /ms | 新20最大实际wall /s | 新20完整成本胜出例数 |
| --- | ---: | ---: | ---: |
| Vanius0525 | 713.783 | 3.890 | 4 |
| cyanneko | 326.509 | 2.063 | 16 |

## 新长样例家族

| 家族 | 新例数 | Vanius0525 | cyanneko |
| --- | ---: | ---: | ---: |
| dynamic_irregular_jumps | 2 | 9.041824 | 9.080385 |
| dynamic_linear | 2 | 5.488121 | 5.594874 |
| dynamic_periodic_steps | 2 | 7.288207 | 7.359389 |
| dynamic_random_walk | 2 | 6.983177 | 6.950263 |
| dynamic_sigmoid_mix | 2 | 5.701189 | 5.956186 |
| dynamic_sinusoidal | 2 | 7.717002 | 7.766129 |
| static_hot_cold | 2 | 5.586091 | 5.624129 |
| static_lognormal | 2 | 4.659352 | 4.748378 |
| static_uniform | 2 | 4.503024 | 4.966468 |
| static_zipf | 2 | 4.461833 | 4.831309 |

## 身份与边界

两位程序沿用用户选择的Vanius联合版return_risk_pooling100_v1、cyanneko R80_next_hier_fast100。
源代码、SDK、编译器/参数与旧50相同，并直接复用相同SHA-256二进制，因此旧结果无需重新执行。
- Vanius0525: `598a8afba225dc7305132b091627ea7f6156448f`，`src/Vanius0525/level1/round9/pure/return_risk_pooling100_v1.cpp`，源码SHA `52ae25812a9863eae0774b2d45e837fd499506431650b8943ed6e4e979c76d2e`。
- cyanneko: `a39d69342b7cd61f3c1489f0d9408ebe717414d6`，`src/experiments/r80_van_transfer_20261030/R80_next_hier_fast100.cpp`，源码SHA `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`。
- 数据manifest SHA `c492268ca0fccd29ce50edbdde54a990ebe4b387a4cc79914922cda3a919a2b2`；完整570例suite `ecc93c2a4ddb9a8174aaf0ee83865c3102ad0a1d00e5f44c2470ec0051cc0803`。
- 成员源码按上述固定提交与SHA读取，SDK身份见`identity.json`；本目录保存旧50与新20的原始stdout/stderr、运行账本和身份。
- 两轮独立计时窗口，没有重新复测旧50，单次D不支持稳定显著性判断。
- 数据独立合法性审核通过；本轮只核验程序输出、计数及Score公式，不额外运行策略做动作重放。
- 所有本轮测试程序已完成，无重试、调参或源码修改。

原始记录分别位于`old50/`与`long20/`；二进制不上传。新旧结果使用完全相同的二进制SHA，两个计时窗口分列，不声明70例重新连续计时。
