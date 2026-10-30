# Level 1 新会话交接（2026-10-30 09:19 北京时间）

**当前入口更新**：用户最新要求停止旧评测并以综合dataset为标准，已执行停止。先读[round6/HANDOFF.md](round6/HANDOFF.md)和[round6/README.md](round6/README.md)，不能恢复旧三成员矩阵。固定综合集2.0.0@33ab5af，纯/AI初始测试和新隔离迭代由新控制器推进；旧结果保留。

## 后续授权覆盖：2026-10-30第五轮实施

用户已重新明确授权优化实施、持续迭代和每小时检查。历史取消指令不再是当前状态；旧STOP保留，新检查器使用独立build/round5-hourly。先读[round5/HANDOFF.md](round5/HANDOFF.md)及[round5/README.md](round5/README.md)，核查宿主进程和实验锁，不能仅凭沙箱PID列表推断旧任务停止。当前Best未晋升；新训练/基准由阶段控制器串行排队，避免重复启动。

## 最新指令与准确状态

用户将到新会话接管，要求更新个人交接并取消每小时周期检查。本会话不再启动额外实验。**小时检查及自动codex queue续接已取消，已有实验保留继续执行**，不能把取消定时器误报为所有实验都停止。

已创建 `build/hourly-resume/STOP`，`build/hourly-resume/status.json` 实测为 `stopped`、`next_check_utc=null`；旧 `build/hourly/STOP` 保留。停止标记不得自行移除。`HOURLY_RESUME_PROMPT.md` 已改为停止说明，历史排队消息不能覆盖最新停止指令。未声称清空服务端历史消息队列；本地没有新建云端Scheduled任务。恢复周期检查须用户明确授权。

## Git与发布入口

- 工作树：本仓库；分支 `source/Vanius0525`。只写 `src/Vanius0525/`，不切他人分支、不改公共框架或队友目录。
- 当前算法已推送：`d8369b04a74b2552aa3737f2f6213d808470eab1`，远端分支SHA已核对一致。
- 提交入口：`src/Vanius0525/level1/MySpillSchedulerBest.cpp`；只提交该文件内容，类名已为 `MySpillScheduler`，C++14标准库/CPU，无main、无需第三方运行时。
- 该文件逐字节等于 `round4/pure_set025_io_asymmetry_routecount.cpp`，SHA256=`2cd6440fb6e78a406a9abac1cab642a98ec94bd07f46f2e55f641d04a23ae1db`。成绩/审核证据及已知风险见 `CURRENT_CANDIDATE.json`。
- 原冻结 `MySpillScheduler.cpp`、`MySpillSchedulerAI.cpp` 未覆盖，分别SHA256=`5823016f30ba29bfa1264102d4888720aa34b490dd7c32a9c18ee9edded9ca0e`、`cb13de53288303110e6e0fb0d62198f11af15402a78d8822aac7e03ef6213621`。
- 本次只做交接/定时取消的文档提交；后台随后产生的新结果不属于已发布算法的完成证据。新会话先 `git status`、`git log -1` 检查，不能假定工作树或旧状态文件永远最新。

## 最新授权：可以参考合作者算法

用户于本次交接前明确授权：从现在起可只读参考另外两位合作者的仓库进展与算法、学习经验并在本人分支综合优化。该指令覆盖过去“不读队友算法”的限制；**过去测量的来源声明不追溯改写**。

已fetch来源：

| 分支 | 固定来源commit | 已知内容的证据级别 |
|---|---|---|
| `origin/source/cyanneko` | `5b51cf1dbe93c76b1bc9b7a0517e79a0a7ba09ae` | commit标题称发布候选状态及hot-stream机制证据；尚未阅读算法正文/核验结果 |
| `origin/source/liunianwww` | `0c6d963a1fcc364ecdf763c638571358928bab42` | commit标题称next-operation保护与write-cost credits；尚未阅读算法正文/核验结果 |

目前没有据此合并、复制或改写候选，也没有启动合作者对照实验。上一轮按猜测 `src/cyanneko/` / `src/liunianwww/` 筛选文件清单未命中方法目录，只看到了AGENTS；不要把它写成已经读过方法。下一会话先用 **未过滤的** `git ls-tree --name-only <commit>` / `git ls-tree -r --name-only <commit>` 找真实路径，再 `git show <commit>:<path>` 只读查看约定、说明、代码。不要切分支或整体merge两位合作者分支。新阶段断点见 `round5/HANDOFF.md`。

## 目标、协议与计分

沿用纯算法和AI两方向，允许训练，保留多个风险/均分/CPU取舍及完整失败轨迹；遇到问题先调研并落盘，不能因模型名头晋升。保存参考框架不改，调度器只读真实回调状态与一条next_op；普通Hit对象身份、完整未来、Miss罚值不在接口内，不能注入隐藏信息或重复计next_op。

当前口径：每案例每重复计算 `clamp(10*(1-VAL/BASE),0,10)`，VAL含I/O+Miss罚+决策时间，BASE/VAL零值按现有规则记0；再平均重复、成员内案例，最后三成员等权。不是旧50分cap、80:20混合或全部案例混合均分。corner/family/CPU-only/最坏I/O比另报，不推定正式分布。

## 已完成的可复核结论

阶段2固定11候选，同批三成员785合法eval（本人209/cyanneko48/liunianwww528），5重复；8635次独立动作审核通过。当前发布版是该面板等权均分最高者，而非所有分布上的赢家：

| 候选 | 本人 | cyanneko | liunianwww | 等权均分/10 |
|---|---:|---:|---:|---:|
| 当前Best/纯IOasym | 3.814995 | 4.176432 | 2.625153 | **3.538860** |
| 较稳健纯all-PROBE | 3.788724 | 4.093935 | 2.555011 | 3.479223 |
| AI预取2048 | 3.872611 | 4.108126 | 2.543420 | 3.508052 |

- Best在fresh3比原pure低0.126835；serial301030 I/O+Miss99707.54us，原pure15185.78us，候选等于Naive。三成员已测最坏I/O+Miss/Naive比5.299，稳健版3.393。反例不剔除，详见README、STAGE3_RESULTS、SERIAL_REVERSAL_CASE。
- 原始无phase子集版本更早出现29502倍/550倍退化，已否决；prune也曾退化20%，不称安全支配。
- 15候选各20000抽象状态/40000回调ASan/UBSan通过，总60万回调。新callback优化4候选各160完整轨迹动作字节一致且独立重放一致；其泛化/最终安全仍待下面队列。
- 零I/O36例的同一Naive二进制自比较能产生约0.79截断均分；两个规范化源码和机器代码区完全相同的模型，val正式分差约0.025。不能把微小计时差当方法改进，亦不能从正式分数机械扣除null均分。
- 固定成本/next操作相同、仅接口不可见罚值不同的N83精确配对流，最优首次驱逐相反。是信息边界，不是正式分布推断或新颖性保证。
- 廉价事件门控在challenge3 32例得2.003938，AI预取1.955736；但常规24例相对AI预取−.045038、预先标记corner8例+.327927，样例内corner权重约12.1%以下翻转。不能套此阈值到别的样例组。最新完整本人209复测：门控3.615211、原AI3.672292、AI预取3.845386，corner也没胜AI预取。另外两成员还没结束，不能先报新的等权均分。
- callback教师首输入的periodic边界修正，在72367事件标签变化0，已排除为负结果原因。真正改为精确Action过滤恢复9309组摘要相同但动作不同的样本；val纯collector反而变差，双collector小升但CPU高。贡献流也从合并198增至211（总输入仍288），不是固定贡献集消融。具体见round4训练/alias/负对照JSON。
- 最大N新矩阵首例（uniform/M64MiB/B1/W=R10000/对象1MiB/500万操作）7程序×3重复完成。纯预算256三次Miss均1 vs Naive4374336，逐例分8.249143、墙时17.060s vs19.793s；AI预算2048为8.234871、25.113s。强收益仅限该条件，不能替代全套件选型。

## 仍在执行的原有实验：不要重复启动

私有实际PID/日志映射只在 **`build/round4/HOST_RESUMED.json`**；旧矩阵的PID/状态在 `build/round4/stress_campaign/`，其他工具会话在 `build/round4/RUNTIME.json`。这些文件不能提交或在公开文档复制聊天ID/绝对路径。PID可能已退出，需对照命令行和状态，不只信旧JSON。

| 角色 | 主脚本/结果 | 本次核查状态 |
|---|---|---|
| 原8候选最大N矩阵 | `round4/stress_campaign.py` → `results/round4-stress-campaign.json` | 27/30输入、729/810次测量，仍未全完成 |
| 新6候选最大N | `round4/run_stage2_maximum.py` → `results/round4-stage2-maximum.json` | 2/6输入、42/126次测量，仍未全完成 |
| joint-LOAD稀疏回调最大N | `round4/run_joint_maximum.py` → `results/round4-jointlookahead-maximum.json` | 等待锁，0/42次；已曝光输入定向诊断，不是盲测 |
| 精确过滤模型新分布 | 宿主 `round4/resume_validation.py callback` | val/fresh已完成，challenge尚未完成；fresh待归约 |
| 软BUILD读回先验 | `round4/run_build_read_prior.py` | val32及4个已曝光机制例完成，待逐例分析；不是新泛化证据 |
| 廉价门控完整三成员 | `round4/run_eventgate_members.py` | 本人209完成，cyanneko48进行中，liu528未完成 |
| 最终输入与安全审核 | `round4/final_safety_and_inputs.py` | 等callback challenge完成后自动执行，不要额外启动重复fuzz |

上述都使用 `experiment.lock` 串行CPU实验。`state=running`可能只是上次字段停留；结合测量数、PID的wchan和子进程判断持锁者。完整状态以新会话再核查为准。

原普通控制器曾SIGTERM退出（143），原因未确认；已保留旧日志，只恢复缺失suite为宿主后台控制器，未重跑已完成fresh3。现在benchmark按完成案例追加`.cases.jsonl`，新恢复challenge3的journal与最终报告逐项一致。完整或部分原始报告均拒绝覆盖；若再次中断，先保存/核验checkpoint及原始输出再设计续跑，**不要直接重启旧矩阵脚本或清空目录**。

## 新会话立即执行的顺序

1. 读项目AGENTS、README/指南、本文件、`HANDOFF.md`、`round4/HANDOFF.md`、`round5/HANDOFF.md`；确认分支与本地修改。最新“取消小时检查”优先于旧恢复提示；不要自动恢复daemon。
2. 核对HOST_RESUMED/旧矩阵进程和最新报告；保留已运行任务，不重复启动，优先收已有队列。只有三成员都完整才算新等权均分；保留失败/超时/未完成项。
3. 分析callback fresh/challenge、soft BUILD4例及门控三成员。soft先验只是假设BUILD将读回，可能伤害活跃PROBE；开发集变化很小，不能据单例恢复就晋升/扩全部弱模型。
4. 用 `python round4/summarize_maximum.py` 归约**完整案例**（脚本目前只汇总旧/阶段2新矩阵，joint需另外加入归约）；需要两个主矩阵state=complete才报完整压力结果。不要混同60秒与90秒本地timeout设置。
5. 只读查看两位合作者的真实文件路径及算法，固定commit/SHA并注明来源；区分作者自报与同框架动作审核/同批性能，必要时再做独立验证。不用他人的测试分数替代自己的计分口径，不读输入隐藏信息。
6. 后续研究继续保持纯算法/AI、多候选、corner与总体取舍。源代码、文献、失败、当前进程与下一动作及时写交接；明确完成的阶段按用户约定提交个人分支，不force、不替他人提交。

## 关键证据位置

- `README.md` / `CURRENT_CANDIDATE.json`：当前发布入口和完整同批分数、反例。
- `round4/README.md` / `round4/HANDOFF.md` / `round4/VERSION_LEDGER.json`：完整探索轨迹、源码/报告指纹。增量报告的SHA只是当次快照，会继续改变。
- `round4/RESEARCH_UPDATE.md`：实际核验论文与适用边界，含GUARD/LRB/Merlin/3L-Cache、DAgger、集合表示/DeepMDP、删失反馈、Saving Private Hash Join及Landlord；未核验正文的来源有明确标记。
- `round4/STAGE2_RESULTS.json`、`EVENTGATE_CORNER_SENSITIVITY.json`、`SCORE_GAP_DECOMPOSITION.json`、`POLICY_ALIAS_CHECK.json`、`SERIAL_REVERSAL_CASE.json`：总体/尾部/噪声/机制分析。
- 大输入、原始重复计时、教师行/模型缓存、二进制、私有会话绑定只在忽略的`build/`、`results/`；不删除，不随源码push。

## Open Ideas / 值得深挖的问题

沿用主HANDOFF里的固定Open Ideas：动作改变未来观测、aggregate-hit删失、截断分数噪声、动作摘要别名与接口不可辨识的区别。当前没有经新颖性核验足以宣称独立顶会立项的新结果，不能把已有经典理论或本项目反例包装为新贡献。
