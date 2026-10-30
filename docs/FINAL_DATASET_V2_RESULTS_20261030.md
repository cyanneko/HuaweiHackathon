# final_dataset v2 全部 50 例方法对比

固定数据提交 `33ab5af221069fe8b8832fd77e85563e9997633a`，VERSION=2.0.0；14 种方法 × 50 例 × 1 次重复，700/700 条指标完整有效。

按未封顶逐例分求和，VanBest 在本轮最高：总分 132.423069，逐例均分 2.648461/10，合计成本为 Naive 的 0.844173 倍。该结论只对应这组固定公开合成测试。

## 方法对比

本轮只选择 final_dataset 这一个集合，主分为 50 例原始贡献求和，理论上限 500；逐例均分为主分除以 50。本表不代表旧三成员等权总榜。原评测器封顶 50 分另保留。Total_Score 包含 IO、miss 惩罚和正式回调决策耗时 D。

`p_i = clip(10 * (1 - C_i / B_i), 0, 10)`，其中 C_i 为候选 Total_Score、B_i 为同例 Naive Total_Score；沿用原实现，任一成本不为正时贡献记 0。`主分 = sum_i(p_i)`，`逐例均分 = 主分 / 50`。

| 方法 | 未封顶总分 ↑ | 逐例均分 ↑ | 合计成本/Naive ↓ | 成本倍率 P90 ↓ | 最差倍率 ↓ | 每例累计 D 的均值（微秒）↓ | 胜/平/负 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| VanBest | 132.4231 | 2.6485 | 0.8442 | 0.9906 | 1.1757 | 9872.52 | 46/0/4 |
| VanRobust | 132.2179 | 2.6444 | 0.8441 | 0.9926 | 1.1777 | 9780.37 | 46/0/4 |
| VanAI2048 | 129.4354 | 2.5887 | 0.8479 | 0.9932 | 1.1629 | 17338.72 | 46/0/4 |
| FitTie | 126.6136 | 2.5323 | 0.8555 | 0.9980 | 1.2369 | 6775.30 | 45/0/5 |
| Clean | 126.1017 | 2.5220 | 0.8556 | 0.9980 | 1.2327 | 6923.73 | 45/0/5 |
| VanLegacy | 126.1007 | 2.5220 | 0.8556 | 0.9980 | 1.2327 | 7140.00 | 45/0/5 |
| LiuTree | 116.2849 | 2.3257 | 0.8675 | 0.9973 | 1.2257 | 16948.17 | 46/0/4 |
| LiuFinal | 109.0096 | 2.1802 | 0.8695 | 0.9888 | 1.0434 | 14012.53 | 48/0/2 |
| LiuNeural | 106.5940 | 2.1319 | 0.8705 | 0.9887 | 1.0516 | 22315.78 | 48/0/2 |
| R65 | 84.7778 | 1.6956 | 0.8976 | 0.9950 | 1.2326 | 10298.98 | 47/0/3 |
| R63 | 84.4410 | 1.6888 | 0.8932 | 1.0004 | 1.5076 | 9212.61 | 43/0/7 |
| BBP | 79.0107 | 1.5802 | 0.9208 | 0.9950 | 1.2219 | 15561.41 | 46/0/4 |
| SingleFit | 77.1026 | 1.5421 | 0.8922 | 1.0424 | 1.9509 | 8325.63 | 41/0/9 |
| Naive | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 11187.83 | 0/50/0 |

Clean、FitTie 为同源消融候选，BBP 为实验对照；R63/R65 保留实验状态。VanLegacy、LiuFinal 为旧版对照。单次 D 和相应胜负受计时波动影响。

## 本轮结论

优先保留 VanBest 和 VanRobust 这一领先组。两者未封顶总分只差 0.2051，VanRobust 的合计成本还略低；一次测量不足以把这点差异认定为稳定胜负。VanAI2048 分数稍低，每例累计 D 均值为 17.339 毫秒，对比 VanBest 的 9.873 毫秒，本轮没有显示出更好的整体取舍。

同伴更新确有收益：VanBest 相对 VanLegacy 的逐例均分提高 0.1264，合计成本降低约 1.34%；LiuTree 相对 LiuFinal 的均分提高 0.1455。不过 LiuFinal 的最差成本仅为 Naive 的 1.0434 倍，50 例中 48 例更低，尾部比本轮 Tree 和 Vanius 领先组更稳健。

R65 的逐例均分为 1.6956，低于本轮前列方法；BBP 未超过 R65，SingleFit 和 R63 的最坏成本分别达到 Naive 的约 1.95 倍和 1.51 倍。本轮结果不支持把这些实验方法提升为唯一主推。Clean 和 VanLegacy 的分数几乎相同，不能把极小差异解释成已确认的算法收益。

## 为什么均分看起来偏低

全部 50 例严格输入检查通过，本轮没有复现数据损坏。按家族观察，VanBest 在均匀随机场景相对 Naive 的收益较小；热点和对数正态场景收益明显。分数取决于输入分布及相对基线的成本改善，不能直接与旧三成员测试或旧场景抽样的均分横比。

| 新常规家族 | 例数 | VanBest 逐例均分 /10 | 合计成本/Naive |
| --- | ---: | ---: | ---: |
| 均匀随机 | 12 | 0.3036 | 0.9227 |
| Zipf 倾斜 | 14 | 1.7790 | 0.9091 |
| 随机热点 | 14 | 4.7584 | 0.4762 |
| 对数正态 | 8 | 4.4834 | 0.7558 |

这仍不能定位队友那次自测的具体低分原因；要复现该次结果，仍需它使用的程序版本、基线、命令和原始输出。

## 同伴版本更新

Vanius 源码固定 `9c755a71b26f5a0937dbbfc7edf68272b3510e72`：新增当前主推 MySpillSchedulerBest.cpp，同时纳入明确推荐的稳健备选和 ai_prefetch_budget2048；原纯算法保留为 VanLegacy 对照。

liunian 源码固定 `0c6d963a1fcc364ecdf763c638571358928bab42`：新增并推荐 MySpillScheduler_tree.cpp，同时比较保留的 final 规则版和 neural 备选。源码变化及逐文件身份见 [teammate_updates.json](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030/teammate_updates.json) 和 [selection.r1.json](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030/selection.r1.json)。


结束时再次核对 GitHub：Vanius 分支已前进到 `5d466610958fba796681020575c2ac5cf6b6064e`，上述已测原纯算法、Best、Robust、AI2048 四份文件仍与本轮冻结源逐字节相同，当前主推与备选入口也相同，因此本轮测量仍对应这些方法的最新源码字节。数据分支仍为 `33ab5af`，liunian 分支仍为 `0c6d963`。见 [末次源码核对](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030/latest_source_recheck.json)。

## 首位方法的退化案例

| 输入 | 成本/Naive | 方法 IO 微秒 | 方法 miss | 方法 D 微秒 | Naive D 微秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| eval_031_random_zipf.txt | 1.175723 | 7620529.61 | 4959 | 1955.04 | 842.66 |
| eval_006_random_hotspot.txt | 1.128068 | 3781768.33 | 3252 | 1435.50 | 600.72 |
| eval_037_random_uniform.txt | 1.020507 | 63649968.99 | 65298 | 33998.39 | 16135.19 |

## 复核和范围

统一编译器：`g++ (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`，参数 `-std=c++14 -O2`；原官方框架只替换调度器类及其实例化。程序在 Linux 持久工作目录串行执行，逐格上限 60 秒。suite_id 为 `55d000e9bac9d17acdb40ad1eb8ed4803014b29ced43c1df8623231732517b6c`。

全部 50 例已做严格输入审核。每条性能记录重新核对程序/输入身份、五项输出、Probe 总数和代价公式；本轮没有逐动作独立重放，不据自报指标声称完整动作审核通过。后续重复须另行安排，不能将本轮单次 D 当作稳定优势。

全部逐例分数和原始成本见 [per_case.csv](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030/per_case.csv)，家族分组见 [by_family.csv](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030/by_family.csv)，完整机器、源码和程序身份及坏例见 [report.json](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030/report.json)。

固定发布档案：[886c89f · 700 原始输出、程序与数据身份](https://github.com/cyanneko/HuaweiHackathon/tree/886c89f71cf78ab1e2e4b284e5c8f055ea73cc1a/src/reports/final_dataset_v2_14methods_20261030)。只在本次 v2 的 50 例中比较，不与离线 A 或旧测试集混榜。
