# R85 两项独立消融

[完整dyna12/final2.1 eval72报告](full_report_zh.md) · [独立新面板诊断](panel_report_zh.md) · [798格静态核验](publication_check.json) · [全量独立复核](full_review/result_review.json)。

新TRAIN84+DEV42、原始完整回归96+576共798格/1596日志全部通过，无策略重试。A fast prior8仅以+.003361等权分领先R81，final反退且42例成本更高；B clipped升但raw与尾部退，059相对父版1.451272。两项不合并、不晋升，默认R75不变。

严格固定final2.1/c65；后来移动分支3.0不是本结果。新18seed面板不与原84汇总混合，DEV已曝光，输入只在datasets研究目录。完整协议/源码/TU/ELF身份、编译定向测试/预期红测/工具失败、全部日志/分组/尾点和审核保留。类/TU原字节，不含ELF；公开元数据省略机器路径/命令，需恢复manifest source_record布局与依赖重建；无新native/编译/生成/训练。
