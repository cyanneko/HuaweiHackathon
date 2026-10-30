# R78：single-fit对照与离线标签证据

[完整报告](report_zh.md) · [48次输出静态重解析](publication_check.json) · [两个未推广提交类](../../experiments/r78_singlefit_controls_20261030/README.md)。

8k组A/B平均物理倍率0.962628/0.985820，但中位数均退化。新100k组A仅0.997435、B为1.000294，分别4胜4负/3胜5负，均标experimental_not_promoted；原R75父源码cab5…未改。模拟IO+真实罚值×miss是主指标，不含D；D仅单次诊断记录，无同轮Naive，不报告比赛分或正式耗时胜负。规模与seed同时改变，不单独归因规模。

stage0和scale各24次真实R75/A/B输出全部保留、未筛掉坏例。发布者独立解析48个stdout、核96个日志SHA、网格/源与输入身份/五指标公式，复算均值、线性中位/P90、最坏与胜负。scale独立最终审计PASS和原报告SHA一并保留，runner6.482秒与native循环至release6.137秒是不同计时范围。

8个100k实际TRAIN及必要配方仅在datasets分支experiments/r78_train_100k_20261030，版本1.0.0、4条seed谱系、train8/dev0/eval0，不属于测试集注册；不创建eval、不更改发现器或过滤名单，原全部非空eval发现/分组/计分和冻结suite保持原样。具体机制已按实际evaluation/evaluate.py核对，见数据README。

offline_notes仅保存旧89分支的标签、账本审核、快速账验证和收益分解摘要；12/16局部headroom不是网络胜出，完整teacher链/大trace/private witness/ELF和旧8k输入未包含。原件SHA与公开件SHA分别记录，命令省略、路径清理。归档为审阅布局，复现需恢复source_record映射及运行环境，不将其描述为一键执行包。未重跑测量或训练，不改默认/其他成员源码。

[8个100k TRAIN固定数据提交](https://github.com/cyanneko/HuaweiHackathon/tree/5e6a5ab6cd3e7a63b8dde10776192fe5359cfe3a/experiments/r78_train_100k_20261030)。原研究data_manifest SHA与公开路径清理版SHA分别保留。
