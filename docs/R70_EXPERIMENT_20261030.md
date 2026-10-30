# R70：离线教师、小网络与独立保留集结果

日期：2026-10-30。**96/96 格正式评测完成；TinyNN 是失败实验，不推荐部署。** dev8 和 holdout8 分开报告，每例六种方案、每格一次；模型冻结后未按正式结果调权重、阈值或追加重复。

## 已发布材料

- [完整报告、算法、教师、标签和模型证据](https://github.com/cyanneko/HuaweiHackathon/tree/987b07c2cf5221280a9ed1f0b95651a696269054/src/reports/r70_experiment_20261030)：1930 个文件，包含 v1 失败、v2 修复、24 个教师、VanBest 真实轨迹及 96 条原始正式结果。
- [40 份实际实验输入](https://github.com/cyanneko/HuaweiHackathon/tree/4b0059e02c4c41a991bfcf8937a503ca62228428/experiments/r70_20261030)：实验版本 **1.0.0**，24 train / 8 dev / 8 holdout，共 441120 次操作，位于 datasets 分支的独立 experiments 目录。
- [逐例成绩 CSV](https://github.com/cyanneko/HuaweiHackathon/blob/987b07c2cf5221280a9ed1f0b95651a696269054/src/reports/r70_experiment_20261030/formal_v2/per_case96.csv)、[发布者独立复算](https://github.com/cyanneko/HuaweiHackathon/blob/987b07c2cf5221280a9ed1f0b95651a696269054/src/reports/r70_experiment_20261030/publication_check.json)与[机器发布记录](PUBLISHED_R70_20261030.json)。

数据均为合成输入，四类为 uniform、hotset、skewed、mixed。mixed 指算子 BUILD/PROBE 阶段交错。此实验不进入默认成员扫描，不改变旧成员 VERSION、785/576/30/dev24 或 final_dataset 的内容。holdout 已在模型冻结后使用一次，现已曝光，后续不能再称新盲测。

## 保留集成绩

按当前 **case-mean-v1** 计算八例逐例分的平均值，范围 0–10。每例分为 `clamp(10*(1-cost/Naive),0,10)`，成本包含模拟 IO、miss 惩罚和实测回调 D。原未封顶 SUM 保留为历史诊断，主分为 SUM/8；这不是官方隐藏八组的成绩预测。

| 方案 | 逐例平均分 ↑ | 每例累计 D 均值 ↓ |
| --- | ---: | ---: |
| VanBest | **4.9417** | 2.686 ms |
| LiuFinal | 4.8569 | 2.978 ms |
| Heuristic，同候选池/32维、无网络 | 4.2410 | 20.716 ms |
| R65 | 4.2377 | **2.015 ms** |
| TinyNN | 4.0389 | 24.156 ms |
| Naive | 0 | 2.228 ms |

TinyNN 对同候选池 Heuristic：dev 为 1 胜 7 负，holdout 为 2 胜 6 负；holdout 成本倍率均值 1.087842、中位数 1.067996、线性插值 P90 为 1.193195、最差为 1.207476。保留全部退化例，不晋升默认。每组只有八例，分位数描述本样本；单次 D 不构成稳定差异或总体尾部保证。

完整候选构造与32维特征本身耗时明显：holdout 同特征无网络对照约20.72 ms，网络再增加约3.44 ms。不能用“只有545参数”推断整体决策便宜，也不能把 Total_Score 当真实磁盘端到端速度。

## 离线教师与模型边界

新增静态保留区间规划，与既有 FIF、cost-aware、size-time 组合，并保留实际 Naive/R65 完整路径作为上界。24 train 的最终教师全部通过官方 compact 回放；对 Naive 的等案例平均物理成本下降为70.17%，对 VanBest 为44.16%。16/24达到相对Naive至少60%下降；难例和未改善规则均保留。这是训练样本的 IO+miss 目标，不含 D，不能替代此前百万 uniform 的46.21%结果。

模型为32→16→1、545参数，纯CPU/C++14/O2、权重内嵌。标签是固定后续策略的完整候选后缀成本，不是精确Q*。370个train状态参与拟合；16个dev诊断状态不参与梯度；holdout无拟合标签。训练循环v1约0.195秒、v2约0.152秒，不包含标签构造或验证；损失下降未转化为闭环收益。

v1因Python与C++浮点求和顺序差异导致密度严格排名不一致。v2统一显式顺序求和，特征版本为 `r70-causal32-v2-sequential-sums`，模型SHA为 `0e39bbd44d6086ce584957f3cefc8b0e8c3ff8621c0904247e9f3395a1872a9e`。全部dev8的双方法完整轨迹、128评分向量和48666个多候选回调摘要检查通过；正式使用无插桩程序。

## 发布核对与复现

发布者独立重解析96份stdout，核对输出公式、Probe总数、输入/程序/框架身份和唯一6×16覆盖，重新计算12个split×方法均分；40份输入逐字节匹配生产SHA。1930份证据与132份数据归档均核对了Git实际blob，未重跑求解器或训练，未新增发布者动作回放。

manifest区分原件SHA与公开SHA。少数本机路径已清理，WSL混合编码日志转为UTF-8；正式测量的六份policy和六份翻译单元保持原字节。归档是原研究布局的审阅快照，按manifest映射恢复相对布局并配置Python/C++运行环境后再复现，不是带二进制的一键运行包。默认推荐方案与其他成员源码分支没有改动。
