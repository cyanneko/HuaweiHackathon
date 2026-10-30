# 方法与评测结果比较入口

维护分支：`source/Vanius0525`。2026-10-30用户要求后续每轮完整测试将协议、结果、代码版本同步到本分支；本入口随阶段完成更新。最新本地性能阶段为Round12，软核心/冷侧折扣候选未晋升；Round13增加R84全量归档审核和联合版物理成本对齐，没有新solver。AI更新与测试暂停，后续默认每方法每题单遍。第三方重测的当前入口、联合版和R80强对照见[固定版本清单](round13/THIRD_PARTY_RETEST_V1.md)。

## 当前可对齐的完整结果

| 阶段 | 数据范围 | 方法与次数 | 完整结果/协议 | 结论边界 |
|---|---|---|---|---|
| [Round12](round12/pure/REPORT_V1.md) | 与Round10相同的固定60 train | Naive、原paired、R80、soft_tail100同场各单遍，240次；另5次候选小协议审核 | [计划](round12/pure/PLAN_V1.json)、[全部结果](round12/pure/RESULTS_V1.json)、[原始输出](round12/pure/RAW_OUTPUTS_V1.json)、[root复核](round12/ROOT_RESULTS_REVIEW_V1.json) | 新候选均分3.721593，低于R80的3.742500与paired的3.744194；未进dev/eval/dyna。 |
| [Round10](round10/REPORT_V1.md) | final2.1固定60 train，24热点/24Zipf/12对数正态 | Naive、原paired、joint、R80、write1、value_rank，同场各单遍；另16次小协议审核 | [计划](round10/PLAN_V1.json)、[全部结果](round10/RESULTS_V1.json)、[逐例CSV](round10/COMPARISON_ROWS_V1.csv)、[代码/数据映射](round10/COMPARISON_MANIFEST_V1.json) | 已曝光训练诊断；三个新主候选均未晋升，未进入dev/eval。 |
| [完整原72](round9/eval72/REPORT_V1.md) | final2.1全部72 eval | Naive/paired/joint各单遍；随机20原记录复用后补52 | [计划](round9/eval72/PLAN_V1.json)、[结果](round9/eval72/RESULTS_V1.json) | 两阶段同日，不声称整72同一个独占窗口；无新增完整动作重放。 |
| [dyna12](round9/DYNA_FULL_REVIEW_V1.md) | dyna1.0完整12，每例500万操作 | 6方法，历史每例3遍，另完整动作审核 | [计划](round9/DYNA_FULL_EVALUATION_PLAN_V1.json)、[结果](round9/DYNA_FULL_RESULTS_V1.json) | 历史已完成，不因改为单遍而重跑或修改旧结果。 |
| [原主60风险校准](round9/RETURN_RISK_MAIN60_COST_DIAGNOSIS_V1.md) | 同60 train | 5方法，历史3遍及候选动作审核 | [计划](round9/pure/RETURN_RISK_MAIN60_PLAN_V1.json)、[结果](round9/pure/RETURN_RISK_MAIN60_RESULTS_V1.json) | 三风险校准候选均未过门槛；跨轮计时不能混入Round10同场成绩。 |

## Round10代码身份

| 方法标识 | 被测提交类源码 | 身份/用途 |
|---|---|---|
| paired100 | [原算法](round9/candidates/paired_penalty100.cpp) | 原纯算法100μs参考，SHA前缀3f8dfaee8b。 |
| risk_pool100 | [联合修正版](round9/pure/return_risk_pooling100_v1.cpp) | 分区/算子驱逐重访风险联合校准，SHA前缀52ae25812a。 |
| r80 | [上游原件](round10/R80_next_hier_fast100_reference.cpp) | cyanneko固定388183b提交，SHA0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d。 |
| write1 | [局部当前写费对照](round10/R80_write1.cpp) | 仅top4子集即时写系数.25→1，负结果保留。 |
| value_rank | [对象总价值排序对照](round10/R80_value_rank.cpp) | 只改候选排序，子集不重复乘size；严重尾部退化，未晋升。 |
| mixed_build0 | [混合阶段小对照](round10/R80_mixed_build0.cpp) | 只测试一个既有mixed协议，未进入主60；所测TRACE相同，无收益证据。 |

完整源SHA、输入SHA和已测二进制/TU SHA在[执行冻结](round10/EXECUTION_FREEZE_V1.json)及[比较清单](round10/COMPARISON_MANIFEST_V1.json)。这些是实验方法，不等于已经替换正式默认入口。只有MySpillScheduler类可提交，框架/输入不能换成方法的一部分。

## 评分与复现方式

每例成本 `IO_time + actual_miss_penalty*Miss + Decision_time` 越低越好；均分先按同轮Naive算 `clamp(10*(1-cost/naive),0,10)` 再逐例等权。单例0成本或Naive0按保存规则记0。物理成本排除Decision，在线100代理不替换隐藏实际罚值。逐例比值的均值和总成本之比分别报告，不能互换。

Round10为CPU单线程、C++14/O2、g++11.4；每例60秒wall限制。任务锁只协调本任务，不保证整宿主独占。性能输入单遍，5条小协议另做动作/字节审核，不能声称主60也完整逐动作重放。

可审阅并复现[运行脚本](round10/run_v1.py)：在仓库根执行 `python src/Vanius0525/level1/round10/run_v1.py prepare`，随后执行同一路径的 `run` 子命令。**需要先恢复清单绑定的本地输入缓存及原参考二进制/框架**；build目录被Git忽略，脚本严格校验其SHA，不能把缺少依赖时的命令当一键可运行承诺。数据来源为datasets分支固定snapshot `42fbd682f6fadc54e23c4ee7cc0bef6563a4513d` 的final_dataset，原参考来源为Round9执行冻结。新平台二进制SHA会变化，应另建执行版本并记录新环境，不能覆盖旧执行冻结。现有已完成目录不得直接重跑。

上游R80此前的“两数据集”是final24+dyna6，不是本表完整72/12，且Van对照为原paired，未包含joint。[上游冻结说明](https://github.com/cyanneko/HuaweiHackathon/blob/2932ce972289b8744f5355c9692fe9cb2c93b5f4/docs/R80_RESULTS_20261030.md)与本分支结果应先对齐输入范围再比较。

## 后续诊断与数据更新，不是新增成绩

- [全24 Zipf训练描述性诊断](round10/diagnostic/REPORT_V2.md)：固定取Round10全部24条Zipf，顺序解析已有输入一次；0新增solver、编译或计时。R80/paired的逐例物理比均值0.996451，而总物理成本比1.029403；12好/1平/11坏，6条退化例Miss更少但IO更多。[完整统计](round10/diagnostic/RESULTS_V1.json)、[摘要](round10/diagnostic/SUMMARY_V1.json)、[root独立算术复核](round10/ZIPF_DIAGNOSTIC_REVIEW_V1.json)。完整请求计数仅供离线诊断，不能输入在线算法；未观测R80内部share/p，不作估计误差因果归因。V2仅澄清复核范围，统计沿用V1。
- [大小与成本感知缓存调研](round10/SIZE_COST_RESEARCH_V1.md)：包含近期预印本、NSDI论文和Google数据库实践，分别注明目标与可见性差异；未据文献收益替代本题测量。
- [inde1.1.0更新审核](round9/dataset_monitor/INDE_V11_REVIEW_d144cdd1c3b7.md)：datasets固定d144cdd新增20条每条200万总操作的eval，原train500/eval50保留；final/dyna/balanced未变。仅小元数据/Git身份核验，没有下载新输入、读取方法成绩或纳入比较。发布者已测过新20，不称未曝光盲测；其中2条均匀对照不自动恢复为主测。

## Round11：同状态观察与上游R82

- [两条固定训练流的观察报告](round11/observer/REPORT_V1.md)：548/593各一个仪器化运行、各3快照，原R80 IO/Hit/Miss精确保持；不是新增性能评分。只有548的q4100改变flat/hier驱逐集合，且各自估计偏好自己的集合，不能推断完整轨迹优劣。
- [观察源码](round11/observer/r80_observer_v1.cpp)、[原码恢复证明](round11/observer/SOURCE_RECOVERY_V1.json)、[合同](round11/observer/CONTRACT_V1.md)、[全部快照/审核](round11/observer/RESULTS_V1.json)、[执行冻结](round11/observer/EXECUTION_FREEZE_V1.json)、[root独立重建12套局部规划](round11/OBSERVER_ROOT_REVIEW_V1.json)。logger和反事实仅作用于副本；源码用于诊断，没有替换正式方法。
- [运行前代数分析](round11/MECHANISM_NOTES_V1.md)：单算子概率排序在共享下保持，但大小和离散集合仍可改变动作。观察结果和此推导的适用范围分开记录。
- [R82负结果与write1源码差异](round9/source_monitor/R82_UPDATE_REVIEW_V1.md)、[R82 reserved DEV来源审核](round9/dataset_monitor/R82_RESERVED_DEV_REVIEW_f4a7fcf6e957.md)：上游TRAIN38与本分支主60不同；其DEV12未下载/接入。资料来自发布归档，未独立重跑上游228格。

最新工作交接见[Round13](round13/HANDOFF.md)。旧性能结果和代码保持原字节，后续诊断与R12候选没有产生新冠军或替换方法。上游R84现已正式归档到caafb937，并完成本分支独立静态审核，具体范围见下节；当前paired100正式入口未因新平均分改变。

与上游R84对齐时，其冻结口径为dyna全12、final eval全72各自逐例均分，再对两个数据集各赋50%权重；不是将84例混合等权，且保留dyna原train/dev/holdout标记，不称新盲测。Van已核为原paired100、源码3f8dfaee8b3e…，不含joint。本文原60训练诊断仍单独报告，不按新口径重写旧结果。政策来源记录见[source文档更新](round9/source_monitor/UPDATE_8e380ad4c664.json)和[datasets文档更新](round9/dataset_monitor/UPDATE_c65c7b32b06a.json)；该口径是上游比较合同，不冒称官方隐藏评测规则。

## Round12：软核心/冷侧折扣负结果与复现

候选[源码](round12/pure/R80_soft_tail100_v1.cpp) SHA为`0a68904cc689c70fabdb8364f58067c6b8df68d4f8b16338c1cf924b86a8755b`；[设计与适用限制](round12/pure/DESIGN_V1.md)、[可逆差异](round12/pure/SOURCE_DIFF_V1.patch)、[执行冻结](round12/pure/EXECUTION_FREEZE_V1.json)将它绑定到具体被测二进制与输入。代码保留R80估计器和动作池规则；固定核心/IID单buffer推导不是动态方法的长期成本证明。

对R80，候选逐例物理比均值1.002140、总物理成本比0.998880、最坏1.126268，33好/3平/24坏。二者去掉D后重新归一化，候选仍少0.015977分；最坏train519少833次Miss但IO增加7,346,876.04μs。[分项诊断](round12/COST_DIAGNOSIS_V1.md)保留这一反例，没有把它只归因于计算慢。5小协议均合法，主60只校验输出；最大wall2.925秒不能外推全规模极限。

[执行器](round12/pure/run_v1.py)的prepare/run分离，正式运行受固定执行清单约束。复现需恢复与Round10相同的冻结输入缓存、参考二进制及官方框架；缺少build依赖时不是一键可运行承诺。已完成输出不能覆盖或自动重跑；新环境应另建执行版本并记录编译/TU/二进制指纹。发布的245项[原始stdout/小协议TRACE/执行元数据](round12/pure/RAW_OUTPUTS_V1.json)可直接核读，root的[独立复核脚本](round12/review_results_v1.py)不调用solver。

15:05 UTC监测到datasets提交`e6613435d59690d6dd768813332387108f7e83c2`，题名标记final_dataset3.0，具体新规模与划分仍在做元数据审核。此更新没有进入上述任何本分支性能成绩；R12保持旧final2.1快照`42fbd682f6fadc54e23c4ee7cc0bef6563a4513d`。后续比较须另绑定新版输入指纹，不能把旧72或旧60自动视为新版覆盖。

## Round13：R84全量审核与联合版归档比较

[R84独立审核](round9/source_monitor/R84_REVIEW_V1.md)、[588条重算CSV](round9/source_monitor/R84_RECOMPUTED_PER_CASE_V1.csv)、[证据](round9/source_monitor/R84_SOURCE_EVIDENCE_V1.json)固定上游caafb937。七方法、588 stdout和1176日志SHA、3067报告文件及七份实际TU经过核查；本分支0新增solver。数据固定d144cdd1下的dyna1.0全12＋final2.1全72。上游同窗含D两集等权分：R80共享4.008007、R80双方案4.003133、Van原paired3.766640；R81为4.084522，但其final尾部退化仍在，未据此替换默认方案。

[联合版额外物理比较](round13/ARCHIVE_JOINT_COMPARISON_V1.md)独立核84输入/罚值、216历史原paired/Naive物理记录与框架非空代码一致，再用既有joint结果对照。R80共享/joint的逐例物理比均值：dyna0.953902、final0.951179；final总成本比却为1.001610，最坏1.157591。平均收益不能解释为每例都改善。该项排除跨次D，只是归档物理比较，不是R84新增joint同窗得分，更不含final3.0。

正式保留入口仍是paired100；联合risk_pool100和R80共享版作为不同身份的重测候选，固定提交/文件/SHA见[第三方重测清单](round13/THIRD_PARTY_RETEST_V1.md)。R12负结果不推荐作为最新最佳版。新纯算法设计和3.0元数据核查仍在独立推进，不与这一已完成审核混作新增性能成绩。
