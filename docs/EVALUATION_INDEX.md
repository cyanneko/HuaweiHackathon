# 统一评测与代码版本索引

**用户最终选定R81并停止优化。** 当前提交经允许的宏名映射归一化后token一致，官方预处理结果和ELF与已测R81一致，见[最终提交说明](FINAL_SUBMISSION_20261031.md)。下方R75默认状态属于各轮实验当时的记录，不覆盖最终选择；历史结果不改写。

用户已选择**以旧版为准**：主评测固定为 `dyna_dataset 1.0.0` 全12例与 `final_dataset 2.1.0` 全72个eval，固定数据提交 `c65c7b32b06a5764ce9ad4881133a3c6eb33ed17`（dyna tree `808ce8b11f57a1a96051f22aa572eceb82b1fba0`，final tree `41197783dd577dfccf5b007a6ece67cbfb241e4b`）。后续新方法按两套完整测试，输入/程序/评分身份与全部结果固定记录。移动 `datasets` 分支的3.0不等于主评测版本；R86的3.0结果仅作补充敏感性实验，不用于主榜、选优或晋升。保留新版数据和全部旧结果，不回滚数据分支，不改冻结输出，不因均分自动替换默认R75。

这是 source/cyanneko 的比较入口。机器清单 [EVALUATION_INDEX.json](EVALUATION_INDEX.json) 将每轮运行前的源码/TU/ELF、数据逐文件SHA和协议身份，映射到发布后的固定Git提交；不回写冻结selection或历史成绩。

| 轮次 | 实际范围 | 已发布格数 | 状态与固定入口 |
| --- | --- | ---: | --- |
| R79 | TRAIN16×4；final24抽样×5 | 184 | [experimental_not_promoted](https://github.com/cyanneko/HuaweiHackathon/blob/890d8da1e862d8c4a508a6c3d2560fc9424ecc5b/docs/R79_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/7da7f9eac56c6dbce521086dbc73ae4650c4d6dd/src/reports/r79_20261030) |
| R80 | TRAIN26×6+26×3；final24抽样×5+dyna6抽样×5 | 384 | [experimental_not_promoted](https://github.com/cyanneko/HuaweiHackathon/blob/56aa71d45288e57d575f462a76ed5c5c9986bf31/docs/R80_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/388183be301a09157730d3a4b1e966e7d036bf9e/src/reports/r80_20261030) |
| R81 | TRAIN38×6+DEV6×5；dyna6抽样×6+final24抽样×6 | 438 | [regression_tail_guard_failed_not_promoted](https://github.com/cyanneko/HuaweiHackathon/blob/c38d71f18dde9d656c652ae5b8222c0be68f4081/docs/R81_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/a39d69342b7cd61f3c1489f0d9408ebe717414d6/src/reports/r81_20261030) |
| R82 | TRAIN38×6；DEV12未运行策略 | 228 | [FAILED_ON_TRAIN38 / experimental_not_promoted](R82_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/b1246ae64a006c679e57789766dc401da2a9ecb9/src/reports/r82_20261030) |
| R83 | 完整新增TRAIN12×8+DEV6×8；未混原始回归 | 144 | [FULL_NEW_PANEL_12_6_COMPLETE](R83_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/6bfb4861b664c366e0bc38624e1b6e7e980780f8/src/reports/r83_20261030) |
| R84 | **完整dyna12×7+final全部eval72×7** | 588 | [FULL_12_72_COMPLETE](R84_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/b7482004d5313c6654629324cb465ef36d6554b1/src/reports/r84_20261030) |
| R85 | 新TRAIN12×7+DEV6×7；完整dyna12×8+final **2.1 eval72×8** | 798 | [完整归档，未晋升](R85_RESULTS_20261030.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/b09ece11af152a705ef2df27162cade838399287/src/reports/r85_20261030) |
| R86 | **仅补充**final3.0全72×8；dyna96格历史复用R85 | 576新格 | [补充敏感性，排除主榜/选优](R86_SUPPLEMENT_20261030.md) · [日志](https://github.com/cyanneko/HuaweiHackathon/tree/ea9acc0d5fc74a4e2c3ae2189792c655a57ff380/src/reports/r86_20261030) |
| R87 | 旧版完整dyna12×8+final2.1 eval72×8；全部新测 | 672 | [裁剪略低/raw略高，未晋升](R87_RESULTS_20261031.md) · [源码/日志](https://github.com/cyanneko/HuaweiHackathon/tree/1857b65b106c3c3e8ac1b079af43f26abf950351/src/reports/r87_20261031) |

R79/R80/R81 的 final24、dyna6 都是历史抽样，保持原集合与字节；R82失败的是预先性能门槛，228格执行均有效。R79 TRAIN无同轮Naive且不含正式D主评分；R80训练只报同轮成本倍率。不能把这些诊断分与正式样本均分混榜。

## 如何比较

先核对机器清单中每个window的case/input SHA、数据commit/版本、selection原件与公开SHA、scorer依赖、同批Naive、方法source/TU/ELF、编译flags、环境、重复及并行数，再看对应逐例rows/summary/raw_logs。源码链接指向固定artifact commit，移动分支仅用于导航。缺少的CPU型号或编译器版本明确标为未记录，不用当前机器信息反填历史。R79训练线性分位与后续最近秩依冻结记录分别解释。

主要单例分沿原评测器定义，D计入Total_Score；两个dataset分别取case均分后各50%，不能把不同案例数的两个集合合并等权。IO/miss是模拟成本，D是每例累计决策实测；不能解释为真实磁盘速度。跨轮D及不同scope的均分不凭微小差异直接排名。R81官方裁剪分提升但raw诊断和最坏退化，均完整保留；raw诊断不是修改比赛计分。

## 新规则与待归档轮次

[R83起完整评测修订](EVALUATION_POLICY_20261030.md)保留原计划并要求新TRAIN12×8和DEV6×8完整测；TRAIN选择器只作诊断，不能因无候选跳过DEV。后续原dyna全12与final当前全部eval分窗口完整运行，数据在运行前核最新远端并冻结，所有失败/中断保留。

[R84加入Van的修订](EVALUATION_VAN_FULL_20261030.md)规定原数据全量为7方法、dyna12×7+final72×7共588格；Van须核最新作者推荐入口与原字节，不追溯加进R83已冻结八方法。R83报告待归档；R84正式v2的588格及独立复核已完成，完整报告待发布，v1仅metadata预检失败，尚不列为已发布完整成绩。

从R83起采用完整原数据，不追溯改写旧抽样或R82未评测DEV。每轮协议、数据/方法身份、环境、日志、逐例结果、状态/限制和external publication映射共同发布。DEV不转TRAIN，不注册为新比赛eval；已曝光动态原train也不允许据此拟合AI。默认R75不因局部均分自动替换。更早研究见 src/reports 历史目录，本结构化索引从R79起建立，不虚补未记录字段。

独立附录：[与Van保存记录的交叉核对](https://github.com/cyanneko/HuaweiHackathon/blob/28fcd850291dbb3914f7ea0ddfa02494be2d74f1/src/reports/r84_20261030/van_cross_audit/cross-audit.md)。84份input身份与216条物理指标记录一致，两侧D置换可解释分差；仅保存记录复算，无新策略运行，不改冻结R84成绩。发布期间移动datasets分支已出现final_dataset 3.0（e6613435），本轮仍只代表固定2.1.0全部72 eval，不将旧分数标为3.0成绩。

R85全量与新面板分开发布，A/B独立不合并。A仅+.003361等权分领先R81却在final退步；B裁剪分升但raw和尾部退，默认R75不变。四窗口以finalized_summary/completion_gate为完成依据；新面板raw summary仍complete=false。所有原final结果固定2.1/c65，后来移动分支3.0另行评测。

当前主评测数据版本的完整约定见[评测版本约定](EVALUATION_DATA_VERSIONS_20261030.md)。

R86仅保留新final3完整576格，dyna96格通过固定R85档案引用，不重跑、不重复计作新格或上传日志。其跨数据集50/50只用于补充敏感性展示，不改变顶部旧版主评测约定；新旧final分差不是算法改进量。
