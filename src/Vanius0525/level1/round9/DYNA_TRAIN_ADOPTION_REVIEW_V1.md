# 500万操作补充训练集：本地接入审核

2026-10-30。六条dyna_dataset 1.0.0训练输入已从本地已有Git压缩对象生成自有快照，并通过独立流式逐行审核，共30,000,000操作。没有下载输入、没有读取其dev/holdout内容，也没有运行调度器。主final_dataset 2.1的432/108/72划分和排名标准保持不变。

原始输入合计586,123,350字节，六个gzip对象合计193,130,930字节；原始与压缩SHA、Git blob身份和尺寸均与冻结清单一致。执行前计划为[DYNA_TRAIN_ADOPTION_PLAN_V1.json](DYNA_TRAIN_ADOPTION_PLAN_V1.json)，独立完整结果为[DYNA_TRAIN_ADOPTION_RESULTS_V1.json](DYNA_TRAIN_ADOPTION_RESULTS_V1.json)，补充核查为[DYNA_TRAIN_ADOPTION_REVIEW_V1.json](DYNA_TRAIN_ADOPTION_REVIEW_V1.json)。脚本[adopt_dyna_train.py](adopt_dyna_train.py)关闭所有Git传输及lazy fetch，保留已有文件和不完整尝试；本轮没有失败重跑。

| train | PROBE数 | 实际BUILD/PROBE交叠 | 最终数据量/内存 |
| --- | ---: | --- | ---: |
| slow_shared_01 | 3,999,997 | 无 | 1.5000 |
| slow_staggered_02 | 3,248,899 | 有 | 5.9883 |
| fast_shared_03 | 3,499,999 | 无 | 3.0000 |
| fast_staggered_04 | 2,967,454 | 有 | 11.9199 |
| burst_shared_05 | 3,249,993 | 无 | 6.0008 |
| burst_staggered_06 | 3,941,989 | 有 | 3.0549 |

审核逐行检查题面范围、阶段、声明计数、每分区完整大小不超过内存、原始与规范请求流指纹，并核对发布者的各算子BUILD/PROBE计数。六条原始和规范请求流指纹各自唯一；算子头顺序另行检查通过。最大规模合法性通过不是调度器运行时间、动作合法性或性能证据。

这批数据主要补充动态算子访问份额、最大N和交叠阶段。仅train01有持久分区热点，其余算子内分区接近均匀；不能把六条都称作分区倾斜，也不替代主倾斜集。算子概率随时间改变来自发布者生成规则与元数据证据，本轮流式审核没有独立验证其可预测性或声称已获得学习收益。

另一个值得检验的训练现象是train05算子7的BUILD份额约30.5%，PROBE份额约9.4%；最终增长份额不能直接当未来访问热度。这里只是离线分项观察，线上策略不能读取完整后续份额。

六个seed与主train/dev/eval、dyna dev/holdout的清单seed和原始SHA交集均为0；它们与历史R71及部分R73开发派生有亲缘，不作为额外独立样本重复计数。缺失的细sidecar未继续获取，不把publisher审计当作本轮独立时间窗口核查。

下一步单独冻结六条train的100-only基线与资源检查，才运行调度器；不直接混入主60分数，不自动查询任何保留集。当前快照位于忽略的`level1/build/round9/dyna_train_snapshots/808ce8b11f57a1a96051f22aa572eceb82b1fba0`，成功过程session23630已exit0。
