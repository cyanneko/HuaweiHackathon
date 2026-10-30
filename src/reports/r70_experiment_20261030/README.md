# R70 离线教师、小网络与96格正式证据

[完整报告](report_zh.md)与[独立发布核对](publication_check.json)；正式结果见[formal_v2/report_zh.md](formal_v2/report_zh.md)、[逐例CSV](formal_v2/per_case96.csv)。96/96有效，dev和holdout各8×6，逐格一次。发布者重新解析96份stdout、核对指标/公式/输入和程序身份，并复算12个split×方法总分；没有重跑程序或训练。

TinyNN为**失败实验，不推荐**：holdout对同候选池Heuristic为2胜6负，成本倍率均值约1.0878；VanBest/LiuFinal本轮领先。v1失败、v2顺序求和修复、三版标签、模型和全部正负轨迹均保留。小网络训练循环v1约0.195秒/v2约0.152秒，不包含标签生成或验证。

40份实际数据在datasets分支`experiments/r70_20261030`，版本1.0.0；本包不重复输入。`inputs/`保存配置、元数据、审核和配方，`teacher/`包含24条教师及基线完整witness，`expert/`保留VanBest真实周期动作。`nn/`保留标签、训练权重、部署源码、跨语言与完整dev验证；不含平台二进制。

`manifest.json`逐文件给出原研究路径、原SHA和公开SHA。仅清理本机路径，少数混合编码日志转为UTF-8；测量使用的12份policy/翻译单元逐字节保留。压短的归档目录是审阅布局；按manifest的source_record恢复原相对路径，并配置已清理的运行路径/原生C++及Python环境后才可重跑，不将本包描述为一键可执行环境。deps保留相关研究模块、生成审核器、官方兼容框架和正式进程/指标解析器。原件中的准备状态和失败记录保持历史顺序，最终完成由formal_v2/progress与96条原始结果证明。

该实验不改变成员VERSION、默认评测套件或既有榜单；训练教师70.17%的均值降幅不能替代旧百万uniform的46.21%。离线目标不含D；正式Total_Score含模拟IO、miss惩罚与实测回调D，不能当真实磁盘端到端收益。最终机器报告和Root摘要均采用(n-1)*p线性插值P90。

当前评分统一采用case-mean-v1逐例均分（0–10）。holdout8的VanBest为4.9417、LiuFinal为4.8569、TinyNN为4.0389；原SUM仅作冻结证据及兼容诊断，不作为新汇报主分。输入固定提交：[40份实际数据](https://github.com/cyanneko/HuaweiHackathon/tree/4b0059e02c4c41a991bfcf8937a503ca62228428/experiments/r70_20261030)。
