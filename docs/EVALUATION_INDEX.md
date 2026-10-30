# 统一评测与代码版本索引

这是 source/cyanneko 的比较入口。机器清单 [EVALUATION_INDEX.json](EVALUATION_INDEX.json) 将每轮运行前的源码/TU/ELF、数据逐文件SHA和协议身份，映射到发布后的固定Git提交；不回写冻结selection或历史成绩。

| 轮次 | 实际范围 | 已发布格数 | 状态与固定入口 |
| --- | --- | ---: | --- |
| R79 | TRAIN16×4；final24抽样×5 | 184 | [experimental_not_promoted](https://github.com/cyanneko/HuaweiHackathon/blob/890d8da1e862d8c4a508a6c3d2560fc9424ecc5b/docs/R79_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/7da7f9eac56c6dbce521086dbc73ae4650c4d6dd/src/reports/r79_20261030) |
| R80 | TRAIN26×6+26×3；final24抽样×5+dyna6抽样×5 | 384 | [experimental_not_promoted](https://github.com/cyanneko/HuaweiHackathon/blob/56aa71d45288e57d575f462a76ed5c5c9986bf31/docs/R80_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/388183be301a09157730d3a4b1e966e7d036bf9e/src/reports/r80_20261030) |
| R81 | TRAIN38×6+DEV6×5；dyna6抽样×6+final24抽样×6 | 438 | [regression_tail_guard_failed_not_promoted](https://github.com/cyanneko/HuaweiHackathon/blob/c38d71f18dde9d656c652ae5b8222c0be68f4081/docs/R81_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/a39d69342b7cd61f3c1489f0d9408ebe717414d6/src/reports/r81_20261030) |
| R82 | TRAIN38×6；DEV12未运行策略 | 228 | [FAILED_ON_TRAIN38 / experimental_not_promoted](R82_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/b1246ae64a006c679e57789766dc401da2a9ecb9/src/reports/r82_20261030) |
| R84 | **完整dyna12×7+final全部eval72×7** | 588 | [FULL_12_72_COMPLETE](R84_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/b7482004d5313c6654629324cb465ef36d6554b1/src/reports/r84_20261030) |

R79/R80/R81 的 final24、dyna6 都是历史抽样，保持原集合与字节；R82失败的是预先性能门槛，228格执行均有效。R79 TRAIN无同轮Naive且不含正式D主评分；R80训练只报同轮成本倍率。不能把这些诊断分与正式样本均分混榜。

## 如何比较

先核对机器清单中每个window的case/input SHA、数据commit/版本、selection原件与公开SHA、scorer依赖、同批Naive、方法source/TU/ELF、编译flags、环境、重复及并行数，再看对应逐例rows/summary/raw_logs。源码链接指向固定artifact commit，移动分支仅用于导航。缺少的CPU型号或编译器版本明确标为未记录，不用当前机器信息反填历史。R79训练线性分位与后续最近秩依冻结记录分别解释。

主要单例分沿原评测器定义，D计入Total_Score；两个dataset分别取case均分后各50%，不能把不同案例数的两个集合合并等权。IO/miss是模拟成本，D是每例累计决策实测；不能解释为真实磁盘速度。跨轮D及不同scope的均分不凭微小差异直接排名。R81官方裁剪分提升但raw诊断和最坏退化，均完整保留；raw诊断不是修改比赛计分。

## 新规则与待归档轮次

[R83起完整评测修订](EVALUATION_POLICY_20261030.md)保留原计划并要求新TRAIN12×8和DEV6×8完整测；TRAIN选择器只作诊断，不能因无候选跳过DEV。后续原dyna全12与final当前全部eval分窗口完整运行，数据在运行前核最新远端并冻结，所有失败/中断保留。

[R84加入Van的修订](EVALUATION_VAN_FULL_20261030.md)规定原数据全量为7方法、dyna12×7+final72×7共588格；Van须核最新作者推荐入口与原字节，不追溯加进R83已冻结八方法。R83报告待归档；R84正式v2的588格及独立复核已完成，完整报告待发布，v1仅metadata预检失败，尚不列为已发布完整成绩。

从R83起采用完整原数据，不追溯改写旧抽样或R82未评测DEV。每轮协议、数据/方法身份、环境、日志、逐例结果、状态/限制和external publication映射共同发布。DEV不转TRAIN，不注册为新比赛eval；已曝光动态原train也不允许据此拟合AI。默认R75不因局部均分自动替换。更早研究见 src/reports 历史目录，本结构化索引从R79起建立，不虚补未记录字段。
