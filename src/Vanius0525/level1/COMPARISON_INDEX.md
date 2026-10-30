# 方法与评测结果比较入口

维护分支：`source/Vanius0525`。2026-10-30用户要求后续每轮完整测试将协议、结果、代码版本同步到本分支；本入口随阶段完成更新。最新性能阶段为Round10，后续增加只读机制诊断；AI更新与测试暂停，后续默认每方法每题单遍。

## 当前可对齐的完整结果

| 阶段 | 数据范围 | 方法与次数 | 完整结果/协议 | 结论边界 |
|---|---|---|---|---|
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

最新工作交接见[后续阶段](round10/POST_R80_HANDOFF_V1.md)。旧性能结果和代码保持原字节，后续诊断没有产生新冠军或替换方法。
