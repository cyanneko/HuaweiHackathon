# 最终提交：R81 宏含义命名版

使用 [MySpillScheduler.cpp](MySpillScheduler.cpp)。用户最终选定R81；此版本在排版和模块注释整理上，仅将五个实验编号宏改为含义名称，数值和算法不变。

| 名称 | 固定值 |
| --- | ---: |
| HASHJOIN_OPERATOR_HALF_LIFE | 256 |
| HASHJOIN_REUSE_ESTIMATOR | 2 |
| HASHJOIN_ADAPTIVE_RISK_SHARING | 1 |
| HASHJOIN_REFAULT_MODEL | 3 |
| HASHJOIN_SIZE_BIAS | 0 |

按允许的五个宏名映射归一化后，6659词法token一致；官方翻译单元296115预处理token、ELF/.text均与已测原版一致。没有新benchmark、调参或训练。[验证](verification.json) · [身份](manifest.json) · [提交说明](../docs/FINAL_SUBMISSION_20261031.md)。

文件只包含调度器类及必要助手/标准库，无main或引擎；按原赛题框架只替换MySpillScheduler，保持官方声明和框架，纯CPU/C++14/O2。原始7f版、上次易读ef1版和历史测量保持不变。
