# R87 Fixed-share 旧版完整评测

[完整报告](report_zh.md) · [672行指标](sol_review/per_case_metrics.csv) · [独立Sol复核](sol_review/review.json) · [发布身份核验](publication_check.json)。

旧dyna12+final2.1 eval72，8方法672格全新实测，无旧D/3.0混入。R87裁剪4.083811低于A约.004021，raw4.022360高于A约.014705，不认定优于父版或自动晋升；默认R75不变。七控制588物理记录与R85一致，计时为本轮新测。

源码/TU、真实父RED/候选GREEN/错式RED测试和编译日志、全部正式日志、协议/分组/尾部/报告生成器与五文件Sol清单保留。没有新native/编译/训练，发布者不重复已完成的stdout算术审计；旧依赖固定引用，输入只在datasets原提交。公开路径/命令净化，脚本恢复source_record后使用，不含ELF或未实现提案。
