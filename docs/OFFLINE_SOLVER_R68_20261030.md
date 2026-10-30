# R68：无增益迭代与后补的单输入差距证书

日期：2026-10-30。本页只记录四个固定训练输入的离线物理目标，不与在线方法榜或 final_dataset 评测混合。[完整档案](https://github.com/cyanneko/HuaweiHackathon/tree/6067996cc685723a0449be3b7761bd7359c5f58e/src/reports/r68_offline_portfolio_20261030)包含源代码快照、输入、seed、逐构造/试探结果及原始与公开文件指纹。

## 搜索结果

四种新增完整构造各跑四例，共 16 条内部完整参考路径，均未超过 R67 保底。30 次局部试探中仅 12 次完成后缀，18 次因非负前缀成本已不可能严格改善而剪枝；实际访问锚点数为 1/2/2/2，不是 30 个不同动作或 30 条完整后缀。

| 固定输入 | R67 与 R68 相同的最终 A（IO+miss） | 新增改善 |
|---|---:|---:|
| beam06 | 269,416.673 | 0 |
| uniform，约 3M 工作集 | 72,739,702.995 | 0 |
| hotset，约 3M 工作集 | 8,537,653.736 | 0 |
| skewed，约 3M 工作集 | 872,157,740.986 | 0 |

没有新增官方回放。四个最终解沿用 R67 已官方验证的路径及原身份；不能称 16 个新构造已通过官方验证。未重跑旧三基线/六构造，未训练网络。批次约 10.123688 秒，不含另列的 0.116 秒 seed 测试，也不是正式 D。单独启发式的退化均保留在[完整报告](https://github.com/cyanneko/HuaweiHackathon/tree/6067996cc685723a0449be3b7761bd7359c5f58e/src/reports/r68_offline_portfolio_20261030/report_zh.md)。

## 后续独立证据及结论修正

搜索无增益之后，独立审读对固定 skewed 输入补充了容量下界。输入 SHA256 为 `20d9bb851209473353472bfe0a9a2067282f48059b494d93b678501d375ad59c`：全部 BUILD 先于 PROBE，四个大分区均超过 M/2。将请求投影至它们，有 2,715 次请求、2,020 次相邻不同 ID 切换。

每次服务完成、周期调整前目标必须完整驻留。相邻不同大分区不能共存，每个不重叠切换区间至少写出前者并读入后者，因此必要 IO 可相加。预取可改变 miss 及读入时刻，但不能免除这些完整读写；下界不加 demand-only 的额外 miss。

必要写出 79,048,255,738 字节、读入 79,048,509,305 字节，W=1000、R=100，得到物理目标的 **L=869,533,348.788 ≤ OPT ≤ U=872,157,740.986**。U 是已验证完整可行解。因此：

- `(U-OPT)/OPT ≤ (U-L)/L = 0.3018162%`。
- 从当前解最多还能降低 `(U-L)/U = 0.3009080%`。

这只适用于该固定输入的 IO+非负 miss penalty 目标，允许预取、不含 D；不是精确最优证明，也不外推其他输入。此前仅据相对旧基线改善 0.84% 将该例视作明显弱点，现由这项差距证书修正；证书不是新搜索找到更好解。

[独立审读](https://github.com/cyanneko/HuaweiHackathon/tree/6067996cc685723a0449be3b7761bd7359c5f58e/src/reports/r68_offline_portfolio_20261030/snapshot/review/search_coverage.md)、[整数证书](https://github.com/cyanneko/HuaweiHackathon/tree/6067996cc685723a0449be3b7761bd7359c5f58e/src/reports/r68_offline_portfolio_20261030/capacity_bound_verified.json)及[包内静态核对程序](https://github.com/cyanneko/HuaweiHackathon/tree/6067996cc685723a0449be3b7761bd7359c5f58e/src/reports/r68_offline_portfolio_20261030/verify_capacity_bound.py)保留推导与数值。归档程序仅调整包内路径，复算与原证书一致，没有运行调度器或求解器。源码原字节与清理后元数据的身份分别记录；归档不是参赛提交文件或已经移植验证的完整执行环境。

本次不修改旧 785/30/dev24 或 final_dataset 的集合、评分版本与结果。来源身份见[发布来源](OFFLINE_SOLVER_R68_PROVENANCE_20261030.json)。
