# Corner stage0数据与切分独立轻量审查

结论：指定小JSON之间的参数、计数、容量、SHA引用及切分关系一致；16例全部记录为生成成功，无替换seed。**这是16×8000操作的接口pilot，不是大规模性能验证**。本次只读取config/source/data manifest、parity/handoff、16份meta及原R72配置，并查看native文件名；没有打开或hash输入/trace，没有编译、策略运行或训练，也没有参与Worker的teacher重计算。

## 参数、配对和身份

共8train＋8dev，每例N=8000，合计128000操作。固定K8/P64/M64MiB、B127、build_fraction=.4、write/read=100/80、penalty100、partition-speed=.0025、rare=none。4机制为fast_shared、fast_staggered、burst_staggered、slow_shared；每个机制×split均有pressure3/12一对。

8对配置展开后**只有pressure不同**，seed及其他参数完全相同。配对metadata中的每算子build/probe、每分区counts、switch阈值/位置、本地访问数、两层概率过程摘要完全相同；总build bytes及分区bytes随pressure改变。未读取输入正文，因此这里不能进一步宣称逐操作/key字节序列已经独立核验。

train base seed为202610309501–202610309504；dev为202610319501–202610319504，集合不交叉。与原R72/dyna全部12 seed无交叉，包括原holdout的202610307110/111/112。train/dev声明的input SHA互不重叠，16个声明SHA各异。每对是同seed压力干预，**不能当作16枚独立随机seed**：实际是4train＋4dev base seeds，每机制每split只有1枚。

config SHA在source/data manifest、parity、handoff中一致；handoff对source manifest/parity的文件SHA匹配。16份meta实际重hash均等于data manifest声明。冻结R75和生成器身份在config/source manifest中分别声明为cab5cae4…和0611bdec…，与既定版本一致；此次未重新hash代码/二进制或输入。源文件完整SHA见机器清单。

## 实际数量与容量

表中build/probe两压力版本相同，每例另含8次SWITCH，因此build＋probe＋8=8000。最大分区占比为该case内最大分区bytes/M。

| split/机制 | build | probe | 实际pressure p3 / p12 | 最大分区/M p3 / p12 |
|---|---:|---:|---:|---:|
| train fast_shared | 3199 | 4793 | 3.024375 / 12.097499 | 1.8812% / 7.5247% |
| train fast_staggered | 3151 | 4841 | 2.871510 / 11.486039 | 1.5315% / 6.1260% |
| train burst_staggered | 2713 | 5279 | 2.995974 / 11.983897 | 1.6219% / 6.4875% |
| train slow_shared | 3199 | 4793 | 2.990740 / 11.962959 | 1.7989% / 7.1955% |
| dev fast_shared | 3199 | 4793 | 3.021033 / 12.084134 | 2.4219% / 9.6875% |
| dev fast_staggered | 3617 | 4375 | 3.133977 / 12.535904 | 2.4739% / 9.8955% |
| dev burst_staggered | 3014 | 4978 | 3.015653 / 12.062612 | 1.3939% / 5.5756% |
| dev slow_shared | 3199 | 4793 | 3.001826 / 12.007307 | 1.4399% / 5.7597% |

逐meta复算：512个分区bytes之和等于total_build_bytes，最大值等于max_partition_bytes，全部≤M；bytes/M等于realized_pressure。每分区counts之和等于各算子实际build/probe，总操作闭合；8个switch位置合法且不早于阈值。普通分区process均为normal且满足原target带归一包络；无持久热/冷异常。期望tuple×1.5仍在生成器大小上界内。

这些是**生成metadata的独立算术一致性检查**，并非重新逐行解析输入得到的第二份stream审计。实际pressure不强制等于目标，保留2.871510–12.535904的自然差异，没有为对齐目标修正计数/bytes。

## Dev是否只生成

在本次stage0产物范围内，有相互一致的证据：config明确dev仅生成；parity的dev_evaluation_or_labels=false；teacher_handoff的dev_read_for_labels=false且8个case均为train；train_parity恰好覆盖8train，Hit＋Miss与metadata probe总量逐一一致。parity保存的dev相关命令恰好8条，均为成功的_generate；native目录dev文件名只有_generate.stdout/stderr，没有dev baseline/adapter策略trace或评分文件。

data目录仍有dev的operator_trace.csv/partition_trace.csv，它们是**生成器概率过程记录**，不是策略执行trace，不能据其存在判断dev已评分。本次未读取这些CSV。上述结论限定为指定stage0报告/日志/目录证据，不声称证明整个工作区任何其他任务绝不曾访问dev。

## 可支持的结论

当前数据可用于检查R75完整动作接口、状态恢复、候选覆盖以及有限train同状态teacher空间。8000步远短于已有5M输入；短轨迹的阶段混合、算子漂移成熟程度及分区字节尺度也可能不同，不能把当前合法性/parity或局部改善外推到大规模吞吐或泛化。config另设至少新≥100k机制/规模验证再讨论corner性能的门槛，当前尚未完成该门槛。

完整16例数据和来源身份：`corner_stage0_data_review.json`；可复现的小JSON审计脚本：`review_corner_stage0.py`。原生成器、数据、Worker产物均未修改。
