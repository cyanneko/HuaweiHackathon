# R73/R74：罚值先验、回访热度与LUT提速

[完整可移植报告](report_zh.md) · [发布者静态复核](publication_check.json) · [可提交调度器类](../../experiments/r74_refault_20261030/MySpillScheduler.cpp)。当前优先实验候选为fast operator，不替换任何正式默认。

formal30保留5方法×6完整5M用例的30格；fast18保留同轮slow/fast operator及fast coverage共18格。发布者重新解析48份原stdout、核对唯一覆盖/输入/程序/框架/输出SHA与公式、复算operator总成本改善及同轮D，并核对两份原zip共292成员与原件逐字节一致。原zip含本机命令路径，不直接发布；公开包中的raw单独导出，manifest分别记录原件与公开SHA，执行命令字段省略。没有重跑程序或新增动作审核。

slow operator相对本轮VanBest平均总成本降9.787%，6/6改善；fast operator同轮累计D均值降8.9965%，6/6更快，物理指标保持一致。这是六个自建开发输入的一次本机测量，不是未知官方泛化保证。覆盖率跨轮burst05 D增加16.8157%、size诊断最坏1.994013倍、罚值先验六大例无净收益均保留。原1us罚值代理与热度改进单独归因；历史Naive仅作辅助均分，不冒充同轮重测。

诊断132、周期配对48、R73先验132/因果16/AI66及82项一致性材料独立保留。report_test_fixtures是汇总器测试夹具，不算正式运行。source目录保留策略、生成和测试脚本；依manifest的source_record可恢复研究相对布局并绑定已省略的机器环境，归档不是一键可运行环境。实际诊断输入仅在datasets分支experiments/r73_r74_diagnostics_20261030，不混入源码或默认suite。旧源码和旧数据不改，R75后续工作不在本发布中。

[诊断输入固定提交](https://github.com/cyanneko/HuaweiHackathon/tree/cbca7d31323425c89573bd781941b300cc326c05/experiments/r73_r74_diagnostics_20261030)。完整5M输入固定于dyna_dataset提交28db22e，不随后续final_dataset版本变化。
