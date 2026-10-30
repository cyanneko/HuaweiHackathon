# R86 新final3补充敏感性实验

**旧版为主：dyna1.0全12＋final2.1全72。** [用户指定主评测版本](EVALUATION_DATA_VERSIONS_20261030.md) · [R85主要依据](R85_RESULTS_20261030.md)。本R86仅补充，排除主榜、选优与晋升，默认R75不变。

新测final3.0全72×8＝576格全部通过，1152份stdout/stderr日志。dyna12×8＝96格沿用R85同源、同原Naive与D的固定结果，没有重新运行或复制日志。[完整报告与逐例尾部](https://github.com/cyanneko/HuaweiHackathon/blob/ea9acc0d5fc74a4e2c3ae2189792c655a57ff380/src/reports/r86_20261030/report_zh.md) · [独立复核](https://github.com/cyanneko/HuaweiHackathon/blob/ea9acc0d5fc74a4e2c3ae2189792c655a57ff380/src/reports/r86_20261030/result_review/RESULT_REVIEW.md) · [全部逐例CSV](https://github.com/cyanneko/HuaweiHackathon/blob/ea9acc0d5fc74a4e2c3ae2189792c655a57ff380/src/reports/r86_20261030/result_review/per_case.csv)。

| 方法 | 历史dyna12 | 新final3/72 | 补充50/50均分 |
| --- | ---: | ---: | ---: |
| R75 | 4.247070 | 3.274672 | 3.760871 |
| R80 hierarchy | 4.306697 | 4.156039 | 4.231368 |
| R80 paired | 4.380687 | 4.064736 | 4.222711 |
| R81 | 4.455848 | 4.083487 | 4.269668 |
| Van paired100 | 4.049627 | 3.881477 | 3.965552 |
| A fast prior8 | 4.482767 | 4.087043 | 4.284905 |
| B hier anchor | 4.306789 | 4.168410 | 4.237599 |

A对父R81在新final成本34胜38负，最差1.296089倍；B对hierarchy为28胜44负，最差1.082973倍。仍无全面稳定改进或自动晋升。原2.1与新3.0的PROBE、Naive和D批次不同，分差不能当作算法改进量，原始成绩不改写。

新final固定datasets `e6613435d59690d6dd768813332387108f7e83c2` / tree `35d4f98b7464e62a9a89b606e41d192380788e76`，3.0.0全部72例、22,528,629操作、474,874,682B；全部PROBE流不同，BUILD继承已曝光旧例，不称盲测。[固定输入路径和SHA引用](https://github.com/cyanneko/HuaweiHackathon/tree/7446de9380876c0ac1b3e51091cde76d7eb372a2/experiments/r86_final3_supplement_20261030)，不重复上传输入。[历史dyna固定结果](https://github.com/cyanneko/HuaweiHackathon/tree/b09ece11af152a705ef2df27162cade838399287/src/reports/r85_20261030/full/dyna)，不把复用D计为本轮新测耗时。

同窗口Naive逐例评分含模拟IO+真实罚值×miss+累计D，case-mean-v1裁剪分与raw、P50/P90/worst完整保留。两套各case均分后50/50，仅作补充展示。CPU串行单次、C++14/O2复用R85同SHA源/TU/ELF，官方60秒/格、内部650秒，实际307.218658秒；模拟IO非实盘加速，微小D差异无显著性保证。Van仍为固定d92推荐paired100，不是实验风险池。

[全部576格协议、日志、源码身份、数据审计来源及Windows静态浮点预检失败记录](https://github.com/cyanneko/HuaweiHackathon/tree/ea9acc0d5fc74a4e2c3ae2189792c655a57ff380/src/reports/r86_20261030)。发布者重解析576 stdout、核1152日志SHA、全网格/分组/分位与历史50/50；没有新策略、编译、训练或重扫475MB输入。历史dyna只核固定已发布汇总，未复制日志或声称重测。源类/TU固定引用R85，ELF不提供；原件/公开SHA分列，脚本须恢复source_record及路径前缀映射。未实现的fixed-share提案未纳入本轮实测方法。[机器清单](PUBLISHED_R86_20261030.json)。
