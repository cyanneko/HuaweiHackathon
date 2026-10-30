# R75 独立开发数据 1.0.0

8个新seed中型输入，各200008操作；其中04/06另生成同seed的500万操作版本，共10份实际输入、11600064次操作。大例仅N参数变化，但阶段阈值及元组大小随N重算，**不是原文本直接延长，也不是两个额外独立seed**。不重复旧R72/R73输入。

| gzip下载 | 组 | 操作数 | 配对中型case |
| --- | --- | ---: | --- |
| [r75_fresh_01_slow_shared](fresh/archives/r75_fresh_01_slow_shared.txt.gz) | fresh | 200008 | — |
| [r75_fresh_02_fast_staggered](fresh/archives/r75_fresh_02_fast_staggered.txt.gz) | fresh | 200008 | — |
| [r75_fresh_03_burst_shared](fresh/archives/r75_fresh_03_burst_shared.txt.gz) | fresh | 200008 | — |
| [r75_fresh_04_slow_staggered](fresh/archives/r75_fresh_04_slow_staggered.txt.gz) | fresh | 200008 | — |
| [r75_fresh_05_fast_shared](fresh/archives/r75_fresh_05_fast_shared.txt.gz) | fresh | 200008 | — |
| [r75_fresh_06_burst_staggered](fresh/archives/r75_fresh_06_burst_staggered.txt.gz) | fresh | 200008 | — |
| [r75_fresh_07_fast_shared](fresh/archives/r75_fresh_07_fast_shared.txt.gz) | fresh | 200008 | — |
| [r75_fresh_08_slow_staggered](fresh/archives/r75_fresh_08_slow_staggered.txt.gz) | fresh | 200008 | — |
| [r75_large_04_slow_staggered](paired_5m/archives/r75_large_04_slow_staggered.txt.gz) | paired_5m | 5000000 | r75_fresh_04_slow_staggered |
| [r75_large_06_burst_staggered](paired_5m/archives/r75_large_06_burst_staggered.txt.gz) | paired_5m | 5000000 | r75_fresh_06_burst_staggered |

inputs.json记录公开压缩路径与原输入/压缩SHA；发布者逐个无损压缩并完整解压校验，10/10原SHA匹配。metadata、配置、生成脚本和审核结果分别保存在fresh/paired_5m；旧R72生成和独立审核源码位于deps，未发布平台二进制。原manifest中的研究路径按发布manifest映射恢复，源码运行环境需重新绑定。

这些样本已用于本轮查看和针对性修订，是开发证据，不能称untouched holdout或官方测试。B1回归取fresh01，与主八大例分开；两个大例与各自中型例始终配对，不能跨训练/检查划分混用。目录位于experiments，不进入默认成员suite，不更改既有成员VERSION或dyna_dataset。
