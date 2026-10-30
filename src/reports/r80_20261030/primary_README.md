# R80 Van受控迁移：完整实验归档

[完整报告](report_zh.md) · [354输出静态核验](publication_check.json) · [最终24例摘要](lazy/final/summary.json) · [独立复核](review/FINAL_REVIEW.md)。

最终24例固定新样本，final2.1.0@f25ade…，与R79旧24不重叠但不声明全项目历史盲测。含D、同批Naive、一次重复，R79/Van/paired_fast/hier_fast均分3.704079/3.846528/3.991113/4.090298。hier_fast对R79仍有最坏+21.12%、对Van+12.70%；仅样本领先，不晋升或替换默认R75。

初始156、缓存检查78、final120三个完整窗口分别保留；旧2xD淘汰记录未覆盖，用户在final前取消该硬门槛，新修订另存。训练无同轮Naive，不伪造训练比赛分；uncapped_sum为原逐例裁剪分之和未再总封顶，不是未裁剪成本改善。全部坏例、分组、原始日志和6候选均保留。按需版26例IO/hit/miss一致及短动作测试是已检查范围，不夸为全状态形式证明。

新10合法TRAIN在datasets的experiments/r80_train_100k_20261030，6谱系/4完整对/2缺hot；失败输入仅存参数/日志/指纹，不装partial input。旧16及final输入只引用固定Git版本。原件与公开SHA分列、路径和执行命令清理；不包含ELF或私有轨迹。冻结脚本需恢复source_record映射和环境，不承诺一键回放。
