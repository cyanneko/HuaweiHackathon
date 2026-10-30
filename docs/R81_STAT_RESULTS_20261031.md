# R81独立stat评测与数据身份

R81在stat_dataset 1.0.0的10个eval用例上，按每例、每重复与同轮Naive评分，最终均分为 **3.439814873/10**。两方法各3次重复，共60/60格有效；30组配对均低于Naive成本。该结果独立于旧dyna12/final2.1 eval72主口径，不重新选择算法。

|项|固定身份或范围|
|---|---|
|数据|stat_dataset 1.0.0；40例、168M操作，train30/eval10|
|本次正式评测|仅eval10，合计42M操作；2方法×10例×3重复|
|manifest SHA256|`d6a3584ab2385e45c7aeeb30a1c2c4d5fdda013dd0606ff994dc264463558149`|
|质量摘要SHA256|`bd015c35e1725fadca8405425278f6ae3a487d002c2151c5fb0b8946b67ae58e`|
|数据发布白名单SHA256|`c9a194e0529c1abc7b0e067d2b00848bc8e833e69f36df180213365713914cdd`|
|最终源/ELF|源`2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`；ELF`bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1`|

逐例成本比均值约0.656018513；均分是逐例逐重复评分的均值，不是总成本之比。正式执行约201.320秒，包含两次准备约227.692秒，额度900秒；这些时间沿用原协议记录，发布者没有重新运行。

eval10经授权正式评测和后续BUILD/消融后已经曝光，不能继续称为盲测或用于拟合。原数据README中“尚未评测”的表述是数据生成审核时状态；当前曝光状态由公开发布说明补充，冻结生产原件不改。

数据归档采用压缩文件，不上传约3.299GB raw正文。40个gzip逐一核SHA，压缩发布约1.265GB，最大单文件41,021,138字节。压缩数据与本页同次发布，见[固定生产归档](https://github.com/cyanneko/HuaweiHackathon/tree/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset)；当前曝光说明见[PUBLICATION](../stat_dataset/PUBLICATION.md)，原生产README保留生成时状态。

[完整报告](https://github.com/cyanneko/HuaweiHackathon/blob/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_stat_eval_20261031/report_zh.md) · [逐例结果](https://github.com/cyanneko/HuaweiHackathon/blob/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_stat_eval_20261031/per_case.csv) · [独立复核](https://github.com/cyanneko/HuaweiHackathon/blob/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_stat_eval_20261031/independent_check.json) · [公开完成投影](https://github.com/cyanneko/HuaweiHackathon/blob/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_stat_eval_20261031/completion_projection.json) · [全部证据](https://github.com/cyanneko/HuaweiHackathon/tree/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_stat_eval_20261031)。

公开证据按260项精确白名单发布，原stdout/stderr与测量C++保留字节，manifest区分原件与公开SHA。原GO、控制器私有进程/ownership及部分旧准备记录未公开；原verification的引用不是全部公开的保证。原脚本依赖研究布局，需要恢复路径和依赖。IO/miss是模拟成本、D是实测决策时间，不是实际磁盘加速；不保证官方隐藏集分数。
