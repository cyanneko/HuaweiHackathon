# Level 1 会话交接（2026-10-30）

## 当前状态与停止指令（优先于历史HANDOFF）

用户要求总结交接并结束当前周期性检查。本阶段已收尾，不再启动新实验。已创建本地`build/hourly/STOP`并在宿主WSL核实原hourly_check.py进程退出；核查时无本项目benchmark/stress/train进程运行。`build/hourly/status.json`及`build/LOCAL_RUNTIME.json`标记stopped、下一次时间为空；原始日志、锁文件、输入和模型不删除。停止标记不可自行移除。

`HOURLY_RESUME_PROMPT.md`已改成停止说明，后续即使收到旧小时消息，也不能据此重启。CLI queue仅暴露排队接口，没有核实/取消历史排队消息的入口，未声称清空队列；最新用户停止指令优先。恢复研究须等用户明确新指令。没有云端Scheduled任务。

## 原目标与硬约束

对Hash Join Spill调度优先提高Level 1成本表现，同时维护纯算法及AI路线。只提交继承SpillScheduler的MySpillScheduler类，Linux、g++ -std=c++14 -O2、CPU/标准库、AI权重内嵌。不修改框架，不注入完整未来/不可见Hit等隐藏信息。参考输入规模K<=8/P<=64/N<=5000000，单回调复杂度建议O(KP log(KP))。先读项目AGENTS、README、docs/AGENT_GUIDE；只操作本人目录。团队数据可补充，暂不参考其他成员算法。

## 当前可提交的两种方法

- `MySpillScheduler.cpp`：纯算法，合法部分观测历史去重、衰减热度、stride预测、等大小全对象循环确认后的快速受害者路径；普通场景只用空闲空间预取。单受害者线性选择、多受害者堆。历史不完整，不能称完整LRU/LFU或全局最优。
- `MySpillSchedulerAI.cpp`：在同类启发式候选中最多4个对象用内嵌12×16×1小网络重排，保持循环快路径与自适应预取。离线训练来自本人train96/val32，未用团队eval拟合。
- 两文件二选一，不一起编译；冻结指纹见`CANDIDATE_FREEZE.json`。纯SHA256=5823016f30ba29bfa1264102d4888720aa34b490dd7c32a9c18ee9edded9ca0e；AI=cb13de53288303110e6e0fb0d62198f11af15402a78d8822aac7e03ef6213621。第二/第三阶段未晋升替代版。

## 最新成绩与唯一汇报口径

只报三人各自测试的每题平均分，以及三个平均分等权平均；每题满分10分。每例相对Naive贡献=clamp(10×(1−VAL/BASE),0,10)，沿用题面对BASE/VAL零值、失败的边界。VAL包含I/O+Miss罚+决策时间。先平均重复运行，再在该成员合法测试间算术平均；不使用旧分层权重、去重权重、50分换算、封顶或全体混合均分。

| 成员数据 | 合法测试数 | 纯算法 | AI |
|---|---:|---:|---:|
| Vanius0525 v0.1.0 | 209 | 3.658058 | 3.722455 |
| cyanneko v0.6.0 | 48 | 3.429539 | 3.614183 |
| liunianwww v0.1.0 | 528 | 2.314665 | 2.296680 |
| 三人等权平均 | 三成员各1/3 | **3.134088** | **3.211106** |

`python mean_score.py`从原始报告只读重算，输出`CURRENT_SCORES.json`，核验候选指纹。不同批次沿用原始3/5/7次重复，不是同一时间全库重跑。团队快照固定datasets@923d21e；cyanneko40个不变SHA样例复用已有5次计时，新增8例补测5次；liunian528例3次。本人由holdout64/OOD64、fresh32/新OOD32、合法corner17组成。AI略高不能声称稳定/显著优势；liunian数据上反而略低。

旧`BALANCED_RESULTS.json`与`balanced_score.py`是历史80/20分层和50分尺度，保留但不再作当前成绩。corner继续适量构造、失败和最坏成本另报，不按候选表现好坏改标签。

## 已完成与主要负结果

- 首轮自造新种子/OOD/团队动作审核、36次边界sanitizer、40000抽象状态/80000回调属性检查；5百万操作循环压力最终约10–11秒。边界“动作运行通过”不能等同输入全部合法，见下条纠错。
- 发布公共输入校验发现旧end_insert缺必须SWITCH。原引擎容忍不代表符合规范；移到diagnostics，不计评测，不删除原字节。其余train192/eval209共401例通过公共校验，输入和元数据指纹、算子头升序已核验，训练/评测操作流重复0。历史含该诊断的原始报告保留并明确排除，不能照搬其全部套件分。
- AI cold BUILD与跨算子serial存在严重退化。serial_293046中纯I/O23311.50/Miss0，AI97131.25/Miss1；确证AI驱逐新BUILD而纯驱逐旧PROBE。阶段保护可修复单例，但不能泛化。
- `round2/pure_phase_bestfit.cpp`与`ai_protect_build_next.cpp`在新fresh32均分改变量+0.0155/+0.1500，在新OOD32为−0.1663/−0.0167，均不晋升。纯阶段版在一个alternating_sets的I/O+Miss达到旧版2.598倍；保护新BUILD会牺牲仍有价值的PROBE。四版256次独立动作审核通过；阶段版5百万压力约9.6–10.6秒。
- 早期即时最少写出的cover最差约189倍Naive；反事实门控teacher验证约3.07低于纯4.27；尾部网络在早期压力仍造成14%退化，后由循环快速路径修复。都保留为负结果。
- 全面复现训练采集、特征与拟合打包得到相同两份提交SHA；见TRAINING_REPRO.json。没有以预测误差替代策略收益。

## 文件、数据与版本追溯

- 总入口README.md；研究RESEARCH.md（22项来源）；首轮RESULTS.md/VALIDATION_SUMMARY.json；第二轮round2/RESULTS.json；第三轮round3/RESULTS.json。
- OPTIMIZATION_HISTORY.md记录优化路径、现象、技巧、长短板；VERSION_LEDGER.json索引44个测量版本，其中43个精确源码已恢复，缺早期dev-v2 scan SHA3f2f9c1003bc32fc…，不以新版冒充。version_archive保存精确字节；后续build.py编译前自动存build/source_snapshots/<SHA>.cpp。
- 原始重复计时/动作日志保存在本地忽略目录results/；输入、权重与运行记录在build/，不随源码分支上传大产物。不删除。新seed295000/296000已曝光，后续外推不能再叫盲测。
- 自造数据已在datasets分支发布：个人提交b131982，合并并发公共更新后远端e119c23；目录datasets/Vanius0525，v0.1.0，train192/eval209/diagnostics1，输入总77498140字节。逐例meta/manifest/生成器/VALIDATION齐全，见该分支README。
- 本人源码工作树分支source/Vanius0525；上一完整阶段提交9e39e51。独立数据发布工作树为同级HuaweiHackathon-data-Vanius0525（detached，已推送），不要切换/覆盖其他主线和共享datasets工作树。本交接另有收尾提交，以git log为准。

## 待用户恢复后的下一步（当前不执行）

1. 先看AGENTS、本文、git status及宿主进程。停止标记保持，除非用户明确重新启用自动检查；不要重启已完成实验。
2. 根据用户目标决定是否继续。当前优先研究scan/corner/hot-smallcold以及跨算子BUILD竞争；现有phase保护已被外推否决，不能只看fresh正收益晋升。
3. 新候选固定后，三个成员完整集合分别审核/计时，同时用新seed297000起及独立新分布验证；不要为排名在已曝光样例上硬编码。三人分开报告+等权平均，CPU与最差退化另报。
4. 新想法先核验论文；保持框架不改、C++14。已记录预取改变未来callback信息机会的独立研究问题，见HANDOFF的Open Ideas，新颖性/真实系统适用性未证实。
5. 完成一个阶段才commit/push本人文件到source/Vanius0525；数据变更另升级eval/VERSION到datasets，不force、不改队友算法。

## 验证命令

本次收尾仅验证停机、指纹、成绩重算和文档，不重跑算法实验：

```sh
python mean_score.py
python -m py_compile mean_score.py
sha256sum MySpillScheduler.cpp MySpillSchedulerAI.cpp
git diff --check
```
