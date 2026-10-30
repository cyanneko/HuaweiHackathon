# R79 自适应算子共享：实验归档

[完整报告](report_zh.md) · [静态发布核验](publication_check.json) · [24例最终摘要](final/recovery/summary.json) · [独立复核](review/REVIEW.md)。

final_dataset2.1.0固定24分层样本、含D/同轮Naive、1repeat/120格有效。R75/固定/自适应/Van均分约3.298530/3.417713/3.526573/3.698241；自适应相对R75有20胜4负，最坏退化8.85%，仍落后Van，均未晋升。旧默认R75不变。三家族、逐例、最坏及首次105+续15的恢复记录全部保留；单次D不支持稳定速度结论。

训练16例64格另记物理成本，不含正式D、无同轮Naive，不报告比赛分。新增8train/4谱系在datasets的experiments/r79_train_100k_20261030，另外8R78通过固定提交引用，不复制final输入。不提交ELF或私有trace/witness。冻结脚本需按manifest来源记录和固定数据映射恢复环境，并非一键重放承诺。
