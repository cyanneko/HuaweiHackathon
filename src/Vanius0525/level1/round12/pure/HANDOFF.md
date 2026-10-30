# Round12 pure：软热点驻留与周转空间

2026-10-30。用户主线继续，AI暂停。pure独占本目录，root拥有round12根与发布。参考固定R80，100μs在线代理；不读reserved dev、未发布R84或新eval，不修改旧冻结文件。

已完成一个候选 `R80_soft_tail100_v1.cpp`，SHA `0a68904cc689c70fabdb8364f58067c6b8df68d4f8b16338c1cf924b86a8755b`。`DESIGN_V1.md`给出精确公式/状态/复杂度/限制，`PLAN_PROPOSAL_V1.json`绑定原60顺序与4方法同窗口单遍240次、5旧协议仅新候选各1动作审核。这是源码提案冻结时的历史状态：当时尚待root审阅、没有solver或可执行二进制。后续正式执行已经完整完成，见下文及REPORT。

唯一新机制是冷侧自命中折扣，p/100/top4数量及主要规则不变；核心仅标签、可被合法释放。概率加权中位数预算是旧机制，成员滞后门槛是代理不是实际迁移费。固定核心IID单buffer式来源已核原研究与4个有理数小模型，不能据此声称本动态规划器长期公式已验证。

`python round12/pure/prepare_v1.py`生成候选与可逆diff；`python round12/pure/check_static_v1.py`在共享锁内 C++14/O2 `-fsyntax-only`成功 exit 0。原357个CRLF保留，全部原代码表达式可逐字节恢复。唯一编译warning为官方Naive未使用state参数。第一次静态准备在编译前因工作树缺statement文件停止；采用build.py相同git-show/SHA回退后通过，见`STATIC_PREPARATION_NOTE_V1.json`，候选未因此改变。

源码与提案冻结 `SOURCE_FREEZE_V1.json` SHA `50b1c146f5c13747e2b0fdb44fa7c7866fd26c9634dc65e67eb6c3bc8f17a259`。root构建准备授权已执行完毕，`python -u round12/pure/run_v1.py prepare` exit 0。prepare结束时累计1次C++语法检查、2个候选二进制构建、0 solver；原60输入与5协议SHA均核回、3参考二进制及源/TU/元数据均复用核验。

正式 `EXECUTION_FREEZE_V1.json` SHA `969504bf28a37122e5887d4147a36e160d02f7553d1586eca02a2d39de14ba46`。`PLAN_V1.json`的output_directory为`build/round12_soft_tail_v1`；Naive已使用公开round10/official_naive_reference.cpp同SHA，原源码/提案freeze未改。新runner完成RAW_OUTPUTS原文捆绑安排，执行metadata不会在落盘后被后置字段改变。

root最后审查已通过，唯一 `python -u round12/pure/run_v1.py run` 已确认terminal exit 0。5/5小协议合法、60/60题及240/240单遍全部完成；没有失败、重试或额外AI/dev/eval/dyna运行。普通与审计候选源码未改。root独立复核通过（`../ROOT_RESULTS_REVIEW_V1.json` SHA `27f5c5dc500b3428497d217b764ba8b8465943b34933ea95be3764fe2a856345`），核240原stdout、245发布bundle及180旧参考物理一致性，未重跑solver。

结果为负：候选分3.721593，对R80物理均比1.002140/总比0.998880/最坏1.126268，对paired均比0.994170/总比1.024217/最坏1.418230。双参考门槛失败，不进dev、不调参。最坏train519少833 Miss却IO多7,346,876.04μs，净物理+7,247,749.04μs；去D重计候选仍落后，不能把失败只归给新增决策耗时。详情`REPORT_V1.md`与root `COST_DIAGNOSIS_V1.md`。

已导出240行LF CSV、方法/数据manifest、约441KB原文bundle及完整report。最终冻结 `FINAL_FREEZE_V1.json` SHA `7b48a56080f27b71cc8114d1f6272010ee1d69f0ab13112234a3cb451c4f8a2d`，绑定27个pure文件，精确发布清单共29项。当前没有运行进程；所有本阶段文件停止修改，交root统一发布。后续新方向需另合同，本阶段所有源/提案/执行freeze保持原字节。

## Open Ideas / 值得深挖的问题

- 2026-10-30：本次最坏train519少833次Miss却多7.347百万μs IO，净物理成本+12.63%；同一p估计器下的集合/尾部折扣也未消除按字节周转风险。值得核对的是固定核心单buffer近似是否兑现实际驻留过程，而不是先增保护常数。最小后续诊断应只在已固定训练共同状态观察core/尾部驻留与实际动作，不把本轮整体结果归为某一γ因子的因果效应；尚未授权新实验，不宣称新颖性。
