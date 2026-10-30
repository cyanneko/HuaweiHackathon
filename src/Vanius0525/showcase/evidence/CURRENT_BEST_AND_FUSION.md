# 当前最高完整主测候选、正式默认及双方融合关系

2026-10-31。周期监测已停止；本次只做一次远端只读核验，`origin` 的 `refs/heads/source/cyanneko` 为 `4a259b7b1b4232f521decdb22b826e41d16baf48`。没有启动评测、训练或下载原始数据。已有冻结审核文件保持原字节。

## 展示主角：R85A fast_prior8

**在已发布的完整旧主面板同场八方法中，最高记录均分是 R85A：4.087790。** 它是合理的主文讲解对象；其意思是“该固定面板、该次运行的最高均分候选”，不是隐藏测试全局最优、统计显著优于所有方法或已经晋升。

上游正式默认仍为 R75；最新版 AGENTS 与 R85/R86 发布说明明确没有自动晋升。默认地位反映上游的保守晋升要求，不能替代“当前最高实测均分”的事实。老 README/release status 仍包含早期方法，不宜拿来作最新排行榜。[当前上游约定](https://github.com/cyanneko/HuaweiHackathon/blob/4a259b7b1b4232f521decdb22b826e41d16baf48/AGENTS.md)

R85A 源码原件：

- 原件提交：`b09ece11af152a705ef2df27162cade838399287`。
- 仓库路径：`src/experiments/r85_math_ablations_20261030/R85_fast_prior8.cpp`。
- SHA256：`a0ebc08399a8cd8c039dae59a779231df0c35306af3ea3269df3067c321779b5`，27197 字节。
- [固定上游源码](https://github.com/cyanneko/HuaweiHackathon/blob/b09ece11af152a705ef2df27162cade838399287/src/experiments/r85_math_ablations_20261030/R85_fast_prior8.cpp)；[本地原字节副本](R85_fast_prior8.cpp)；[完整公式与回调说明](ALGORITHM_EXPLANATION.md)。

## 完整主面板与同场八方法

固定数据 `datasets@c65c7b32b06a5764ce9ad4881133a3c6eb33ed17`：dyna 1.0.0 全 12，final 2.1.0 的全部 72 eval。dyna tree 为 `808ce8b11f57a1a96051f22aa572eceb82b1fba0`，final tree 为 `41197783dd577dfccf5b007a6ece67cbfb241e4b`。不是 final3.0，也不是 84 例直接等权混合。

逐例实际总成本 `C=IO+真实罚值*Miss+D`；D 为框架累计的决策时间。每例得分 `clamp(10*(1-C/C_Naive),0,10)`，先各数据集内取算术平均，再两集各占 50%。未裁剪分去掉 clamp，允许负分，能暴露被 0 分截断的严重退化。这里的 4.087790 是 **0–10 尺度的 case-mean-v1**，不是旧 `evaluation.py` “逐集求和封顶 50”的成绩。

以下来自 R85 同一次研究阶段的 finalized summaries：各方法每例单遍、CPU 串行，每个数据集都有同窗 Naive。主面板完整 84×8=672 格。没有把新 TRAIN/DEV 126 格混进主面板。

| 方法 | dyna12 均分 | final2.1/72 均分 | 两集 50/50 | 两集未裁剪分 |
| --- | ---: | ---: | ---: | ---: |
| **R85A fast_prior8** | **4.482767** | 3.692813 | **4.087790** | **4.007596** |
| R81 op256_cond2048 | 4.455848 | 3.713010 | 4.084429 | 4.003633 |
| R85B hier_anchor | 4.306789 | **3.734270** | 4.020529 | 3.923527 |
| R80 next_hier_fast100 | 4.306697 | 3.709196 | 4.007946 | 3.950102 |
| R80 paired_hier_fast100 | 4.380687 | 3.625506 | 4.003096 | 3.890665 |
| Van_latest：原 paired100 | 4.049627 | 3.483619 | 3.766623 | 3.602289 |
| R75 dense_switch | 4.247070 | 2.965827 | 3.606448 | 3.288803 |
| Naive | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

[R85 发布说明](https://github.com/cyanneko/HuaweiHackathon/blob/2dd9640a883a2d5d3b50a55f2f9e4919872446db/docs/R85_RESULTS_20261030.md)、[完整报告](https://github.com/cyanneko/HuaweiHackathon/blob/2dd9640a883a2d5d3b50a55f2f9e4919872446db/src/reports/r85_20261030/full_report_zh.md)。完整精度和成本分位数保存在 [BEST_VERSION_AND_SCORES.json](BEST_VERSION_AND_SCORES.json)。

这些分数是**发布者保存的结果**；本轮独立核对了实际源码字节、A/B 的精确源码差异、先验公式、completion 与 finalized 关联，没有独立重解析 R85 全部 798 个 stdout（包括训练/开发面板），也没有复跑。不能把先前对 R84 的完整 stdout 审计转移成对 R85 的同等证明。[既有 R85 核查](https://github.com/cyanneko/HuaweiHackathon/blob/2dd9640a883a2d5d3b50a55f2f9e4919872446db/docs/R85_RESULTS_20261030.md)

## 最高平均分与尾部稳健不是同一问题

R85A 对直接父版 R81 的两集均分只高 `0.003361`：dyna 提高 `0.026919`，final 降低 `0.020197`。final 中是 30 胜、42 负，最坏单例总成本为父版的 `1.213483` 倍。这个幅度与单遍设置不支持“稳定全面改善”的说法。

下表均为 final2.1 的逐例总成本 / 同窗 Naive 成本，越低越好。P90 表示 90% 案例的成本倍率不超过该分位数；worst 是最坏案例。

| 方法 | P90 | worst |
| --- | ---: | ---: |
| R81 | **0.953082** | 1.422137 |
| R80 hierarchy | 0.989347 | **1.403431** |
| R85A | 0.989598 | 1.403459 |
| R85B | 0.992126 | 1.624924 |
| R80 paired | 0.997549 | 1.709942 |
| 原 paired100 | 1.066102 | 1.928383 |
| R75 | 1.170297 | 2.853385 |

R81 的 P90 更好，R80 hierarchy 的 worst 略小；R80 与 A 的最坏倍率差极小，不应把这个单次差异讲成稳定优势。没有一个方法同时在所有均分、分位数、最坏例和所有数据集上占优。

R86 另做 final3.0 全 72×8 的敏感性实验，复用 R85 的 dyna 结果，没有新算法。它不能换名字冒充 R85 旧主面板，也不能把分数变化归因于算法改动。R86 身份已核，完整逐格结果未独立复算。[R86 核查](https://github.com/cyanneko/HuaweiHackathon/blob/4a259b7b1b4232f521decdb22b826e41d16baf48/docs/R86_SUPPLEMENT_20261030.md)

## 双方长处究竟结合在哪里

R80 发布者明确以我方提交 `28094bdec34ff7110d9f1614703d0b09d383d4a6` 的 `round9/candidates/paired_penalty100.cpp` 为参考，迁移三类思想：去重 next 的归一化概率；64 请求视野下的动作差分估值；100μs 在线 Miss 代理。它在自己的 R79 框架中实现，保留自身的动作确认、在盘暴露、算子共享、dense/scan/cycle 等条件分支。[固定 R80 报告](https://github.com/cyanneko/HuaweiHackathon/blob/388183be301a09157730d3a4b1e966e7d036bf9e/src/reports/r80_20261030/report_zh.md)

后续关系可表示为：

```text
我方原 paired100：next 归一化 + 64 视野 + 100μs + 动作差分
                            │ 思路迁移
同学 R79 框架 ──────────────┴── R80：分区概率 + 自适应算子共享
                                  │
                                  └── R81：快算子 256 × 慢条件 2048
                                         │
                                         └── R85A：快 prior 64 → 8.00948

我方原 paired100 ── 联合修正版：磁盘未知暴露 Z / 意外 Miss D 校正
                    （独立路线，没有被 R85A 完整合入）
```

这是有源码与报告支持的“吸收双方思路”，不能称为“两个最终最优源码已经整合”。R85A 的 `R80_MODE=2` 在一个 hierarchy proposal 后直接返回，未执行源码中保留的双方案差分比较器。

## 对我方“联合修正版”的精确区分

我方原 paired100 SHA 为 `3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15`；R85 面板的 `Van_latest.cpp` 正是该文件，**并不是联合版**。

联合版源为 `round9/pure/return_risk_pooling100_v1.cpp`，SHA `52ae25812a9863eae0774b2d45e837fd499506431650b8943ed6e4e979c76d2e`。它保持原两套 proposal，仅在原比较器的未来均值中，把原 p_i 换成：

\[
r_{o,-i}=\frac{1+\sum_{j\ne i,\,j\in o}D_j}{1+\sum_{j\ne i,\,j\in o}Z_j},
\qquad
h_i=\min\left(1,p_i\frac{r_{o,-i}+D_i}{1+Z_i}\right).
\]

D 是意外 Miss 的衰减事件量；Z 是按原概率累计的未知在盘暴露；已透露 next 的位置统一排除。h **不归一化**。只在全部算子 PROBE 后启用，混合阶段停用重置，没有未知暴露则回退。原风险余量保持，不能解释为 h 的校准置信区间。[部署合同](https://github.com/cyanneko/HuaweiHackathon/blob/a00677d59154156ac1da04b236c1bf8d0cff64b1/src/Vanius0525/level1/round9/pure/RETURN_RISK_DEPLOY_CONTRACT_V1.md)

R85A 没有这个 `RiskCore` 或 D/Z 校正。它保留的旧 refault fallback 是 `(exposure+64)/(events+1)` 等待时间代理，时钟、采样排除、适用分支都不同；其层次概率公式也不同。此前旧冻结简报把 joint 简写成“hierarchy 均值修正”不够准确；本稿明确以上公式，旧冻结文件不改写。

因此：R85 表可证明 A 在该次面板高于我方**原 paired100**，不能由此声称高于未入场的 joint。同输入跨归档的物理成本比较已有另一份 Round13 证据，它只比较 R80 hierarchy/paired 与 joint，不能被拼成 R85A 与 joint 的同窗含 D 成绩。

## 展示时可直接采用的结论

R85A 是当前已发布完整旧主面板的最高均分候选，以“快算子活跃度 × 慢分区偏好”估计驻留价值，并把读写代价和 100μs Miss 代理带入整分区选择。它继承了双方已验证的部分思路，但没有完整合并我方联合修正版。数据版本、单遍排名、尾部退化及上游默认未晋升应与分数同时呈现。
