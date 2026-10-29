# 第二轮：BUILD竞争与AI推理门控

2026-10-29。授权沿用当前任务；只写个人源码目录。初始分支source/Vanius0525、工作区干净。小时检查器等待下一次15:39 UTC，不重复启动。

目标：修复首轮AI在serial_293046的I/O约4.16倍退化，检验BUILD期间Probe序号冻结与学习模型外推的影响。首轮两份提交文件和CANDIDATE_FREEZE保持原字节。

已验证事实：该例K2/P4/M64MiB，op0先132 INSERT+12000 Probe，随后op1的42 INSERT+12000 Probe。Naive与纯算法I/O=23311.50/Miss0，AI I/O=97131.25/Miss1。机制尚需通过实际动作差异确认，不能直接归因。

计划：比较overflow不使用网络、overflow按Naive规模排序、连续无Probe进展2/4次overflow再退回规模排序。先在已曝光开发集筛选，再用新的295000起种子验证；不把既有holdout重称盲测。保持框架不变、C++14、合法信息与单回调复杂度约束。

运行：准备实验；原小时进程不变。

## Open Ideas / 值得深挖的问题
暂无新增独立问题；上轮信息价值问题保持在上级HANDOFF。

## 本轮补充文献
- Resource-Adaptive Query Execution with Paged Memory Management，CIDR2025，https://www.vldb.org/cidrdb/papers/2025/p2-otaki.pdf ：动态资源重分配避免静态配额与按需分配的局限；本题只能借鉴阶段竞争思想，不能改buffer pool或执行框架。本次已核对摘要与正文开头。
- REMOP: REmote-Memory-aware OPerator Optimization，arXiv:2606.19576（2026，under review），https://arxiv.org/abs/2606.19576 ：转移次数的固定往返代价会改变只最小化字节数的最优选择；本题Miss罚相关，但LOAD次数与Miss次数在预取下不同，不能直接沿用其网络模型。本次核对原始arXiv摘要，不把预印本当已发表结论。

## 进行中
- 已生成纯算法overflow冷启动与AI禁用overflow网络/连续停滞门控的独立候选，未覆盖首轮提交。
- 正在对已曝光val32串行比较7个候选、重复5次并独立动作审核；计时锁与小时脚本共享。

## 15:21 UTC检查点
- 用户新指令：同学新测试纳入主线；已固定datasets@0be508208700edae7a7b4443b122c633cc87b0e0，仅数据/manifest。cyanneko0.5.0有40 eval，7683466字节；liunianwww0.1.0有528 eval，65701416字节；共568例73384882字节，全部SHA及输入规则校验通过。528例有524个manifest声明的operation group，后续统计不假装全部独立。快照在build/team_snapshot_0be5082。
- 确证动作差异：serial_293046的第189个回调为overflow(op1,pid0,tuple65536)，纯算法SPILL旧op0/p0，AI SPILL新BUILD op1/p2。禁用overflow网络恢复I/O23311.50/Miss0；保留网络但BUILD候选后排，I/O11655.75/Miss0。不能据单例晋升。
- val32：直接禁用overflow网络的I/O+Miss诊断均分从4.3872降至4.2839，主要损失另一个serial例3.333分，网络在BUILD并非总是无用。阶段过滤的诊断均分约4.3775，仍略低原版。
- cyanneko0.5.0已完成：原纯/原AI/next-build阶段候选，平均逐例分3.3177/3.5343/3.5581；候选总I/O和Miss略增加，符合截断逐例分与总成本不同这一边界。所有动作审核通过。
- 正在串行评测liunianwww528例、3次重复、3候选+Naive，session记录仅在本地工具/运行状态，不创建重复任务。另有纯算法阶段best-fit候选val32等待同一实验锁；不与主评测并发计时。
- 首轮根目录两份提交及冻结指纹未变。本轮只保留实验候选，尚无晋升决定。

## 第二轮补充评测与版本档案（2026-10-29）
- 新数据固定datasets@0be508208700edae7a7b4443b122c633cc87b0e0；只读manifest/输入，不读同学算法。40+528=568 eval、73384882字节全SHA及格式校验，1704次独立动作重放通过。cyanneko重复5次、liunian重复3次。
- 新团队平均逐例分：cyanneko纯3.317664/AI3.534258/next-build3.558065；liunian纯2.314665/AI2.296680/next-build2.294218。全部合成套件封顶50不等于隐藏成绩。AI在更大集合不领先，不晋升阶段保护候选。
- 纯phase-best-fit在曝光val32诊断均分4.162282→4.289854，但平均成本比变差、shift最坏2.16倍。尚未做新种子外推，保留实验版本，不替换正式提交。
- 用户要求保存全部优化过程：OPTIMIZATION_HISTORY.md记录路线、现象、失败和下一步；VERSION_LEDGER.json索引44个测量版本，43个精确源码归档。缺失早期scan源码3f2f9c1003bc32fc…明确记录，不冒充完整恢复。根目录/round2同时保留未测量候选。
- build.py新增编译前内容寻址快照，防止后续别名覆盖丢失版本；C++14编译复核通过、框架检查仍执行，两冻结提交SHA不变。原始结果/输入仍本地保留，提交摘要与源码不含私人会话信息。
- 小时进程保留，状态waiting、下一次15:39 UTC；未启动重复实验。下一步先读本记录和round2/RESULTS.json，考虑新seed295000起验证纯phase及scan/corner退化，禁止把曝光val当盲测。
