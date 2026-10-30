# Level1 持续优化：2026-10-30

保留纯算法与AI两方向、多种风险取舍及全部负结果。两个根目录冻结候选保持原字节；本目录是独立实验候选，每次只提交一个定义`MySpillScheduler`的C++14文件。训练教师、数据生成器及脚本不是提交物。

## 当前同批完整结果

固定三成员785条合法eval、11候选、每例5重复，8635次候选独立动作重放通过。每次重复先计算相对Naive的截断分，再平均重复和成员内案例，最后三成员等权平均，满分10；I/O、Miss罚与CPU均进入总分。保留所有案例，不采用旧50分cap或80:20混合权重。

| 候选 | 本人209 | cyanneko48 | liunianwww528 | 三成员等权 | 最坏I/O+Miss/Naive |
|---|---:|---:|---:|---:|---:|
| [pure](../MySpillScheduler.cpp) | 3.636017 | 3.415706 | 2.313863 | 3.121862 | 3.478 |
| [ai](../MySpillSchedulerAI.cpp) | 3.712301 | 3.601342 | 2.299625 | 3.204423 | 4.167 |
| [pure_prune_routecount](pure_prune_routecount.cpp) | 3.693468 | 3.477826 | 2.367756 | 3.179683 | 3.478 |
| [pure_set025_all_probe_routecount](pure_set025_all_probe_routecount.cpp) | 3.788724 | 4.093935 | 2.555011 | 3.479223 | 3.393 |
| [pure_set025_io_asymmetry_routecount](pure_set025_io_asymmetry_routecount.cpp) | 3.814995 | 4.176432 | 2.625153 | 3.538860 | 5.299 |
| [ai_set025_routecount](ai_set025_routecount.cpp) | 3.850440 | 4.107758 | 2.515257 | 3.491152 | 4.000 |
| [pure_prefetch_budget256](pure_prefetch_budget256.cpp) | 3.644861 | 3.414165 | 2.330741 | 3.129922 | 3.478 |
| [pure_prefetch_budget2048](pure_prefetch_budget2048.cpp) | 3.656296 | 3.428127 | 2.335796 | 3.140073 | 2.615 |
| [ai_prefetch_budget2048](ai_prefetch_budget2048.cpp) | 3.872611 | 4.108126 | 2.543420 | 3.508052 | 4.000 |
| [ai_context_exact_pure_d6_m005_support_fast](ai_context_exact_pure_d6_m005_support_fast.cpp) | 3.758411 | 3.690448 | 2.401568 | 3.283476 | 4.000 |
| [ai_context_exact_agg_d6_m005_support_fast](ai_context_exact_agg_d6_m005_support_fast.cpp) | 3.738516 | 3.579745 | 2.406659 | 3.241640 | 4.000 |

这张表不能当作最终冠军排序：另一批新种子fresh3中，偏均分纯算法相对原pure下降0.126835分，AI集合相对原AI下降0.198553分。新serial例中两候选I/O+Miss为99707.54us，等于Naive；原冻结版15185.78us，单例损失约8.47分。均分优胜会随生成分布反转，不能只保留最好的一批。见[STAGE3_RESULTS.json](STAGE3_RESULTS.json)。

最坏列只比较Naive I/O+Miss为正的例，避免微秒CPU比例噪声；零I/O正成本例另记机器报告。该列不是总成本保证，也不包含未测场景。按候选结果筛掉的案例数为0。

- `all_probe`偏保守：只有所有算子都在PROBE阶段才启用集合优化；`io_asymmetry`也在读带宽不低于写带宽时启用，均分较高但尾部更差。
- `ai_set025_routecount`使用内嵌网络重排小候选，再枚举固定小集合；AI预取2048放宽一次真实next_op的传输预算，是显式风险先验，不读不可见罚值，不保证长期regret。
- context树每次比较多组假想动作，CPU明显更多。已对首步周期回调干预边界做完整对照：72367事件标签变化0，排除该疑点对当前结果的影响。精确动作身份过滤恢复9309组摘要相同但动作不同的候选，独立训练消融继续验证；不能把旧模型的不佳表现直接归因模型容量。
- 同一Naive二进制独立重复，在36个零I/O用例上也可产生约0.79的正向截断均分。没有从正式成绩机械扣除该值，完整保留所有微秒例及重复；小分差不等于稳健收益。

## 新验证与机制证据

阶段2先冻结源码SHA，再生成fresh2的64条新种子和challenge的64条新生成规律；每套11候选、5重复、逐例审核。challenge含循环破坏、渐变热点、大小/热度翻转、扫描切换、混合phase、bridge、强读写不对称和空分区等轴，不声称代表正式分布。设计受已曝光问题启发，不能称完全不受反馈的confirmatory test。

新challenge均分：纯IOasym1.873141、AI预取1.834631、AI集合1.812337，原pure1.594315/AI1.711069；两context约1.72–1.73。训练策略没有稳定领先。所有入围者都报告，不只保留冠军。

10万请求机制面板：B1的scan_hot，纯有限预取256使Miss77091→0、总成本93.605M→16.441M us；uniform86819→1、105.396M→18.525M。B31收益显著缩小，低罚可能不划算。新联合LOAD版本利用Miss回调的一条真实next_op，把两对象同时纳入分配，仍可能丢失下一次Miss的额外lookahead；开发及新分布对照单列。

精确小例只改变接口不可见的Miss罚值，操作流、首次状态和next_op完全相同，最优首次驱逐相反；证明存在实例级信息边界，不代表benchmark有错，也不声称策略达到界或研究新颖。见[PENALTY_INFORMATION_BOUNDARY.json](PENALTY_INFORMATION_BOUNDARY.json)。

## 证据与复现入口

- [HANDOFF.md](HANDOFF.md)：完整阶段日志、失败尝试、当前队列及下一动作；[RESEARCH_UPDATE.md](RESEARCH_UPDATE.md)：原论文来源、结论和本题适用边界。
- [STAGE2_EXTERNAL_FREEZE.json](STAGE2_EXTERNAL_FREEZE.json)：先于新输入的源码清单；[PHASE_RESULTS.json](PHASE_RESULTS.json)：阶段限制完整三成员及corner敏感性；`STAGE2_RESULTS.json`是本批完整分析（若尚未生成，脚本正排队，不冒称已完成）。
- [VERSION_LEDGER.json](VERSION_LEDGER.json)：每份源码/已测SHA、原始报告SHA和状态；原始输入、完整动作及重复结果保留在本地忽略的`build/`与`results/`，不上传大日志或私有会话信息。
- `run_stage2_external.py`、`run_stage2_members.py`复现本批，但重跑会改变测量；已有进程运行时不要重复启动。`summarize_stage2.py`和`plot_stage2.py`只基于已有报告分析；corner重加权仅作敏感性诊断，不替换当前计分。
- `fuzz_stage2.py`、`fuzz_miss_lookahead.py`做ASan/UBSan抽象回调安全测试。`stress_campaign.py`及`run_stage2_maximum.py`保存最大N增量结果，只有state=complete才算整矩阵完成；未完成数据不能冒充最终压力结论。

小时续接已恢复为`../hourly_resume.py`，当前要求至少持续到北京时间07:00；不是云端Scheduled，依赖本地宿主与Codex服务。最近状态以[../HANDOFF.md](../HANDOFF.md)及本目录交接为准。


## 分数差的来源

[SCORE_GAP_DECOMPOSITION.json](SCORE_GAP_DECOMPOSITION.json)保留全部785例，精确分解差值。纯balanced相对AI集合约−0.01193分，其中−0.01002来自纯CPU例，重复归约存在方向翻转；不能称AI稳定领先。纯IOasym相对AI预取约+0.03081，零I/O组反而贡献−0.00685，有I/O组贡献+0.03766，故不能把此优势全部归为纯CPU噪声；有I/O组的正式成本仍包含CPU。两者也都不解决新分布反转。


## 廉价训练候选的当前边界

阶段3独立challenge中，事件门控d4总分2.003938高于AI预取1.955736，且决策耗时较少；但预先标记corner分组后，常规24例反而落后0.045038分，corner8例领先0.327927分。样例内corner权重低于约12.1%即翻转，不能用当前25%比例代替正式分布。该候选作为corner较强的一种取舍保留，完整三成员同批复测继续；证据见[EVENTGATE_CORNER_SENSITIVITY.json](EVENTGATE_CORNER_SENSITIVITY.json)。
