# 第三方重测：固定方法版本

2026-10-30。用户询问当前最佳版本用于同一第三方环境重测。必须区分当前保留的提交入口、实验联合版，以及上游强对照；没有一个版本被证明在全部范围和全部指标上占优。

本分支固定提交：`a00677d59154156ac1da04b236c1bf8d0cff64b1`。下列三个文件均已逐字节核对该提交和工作树。

| 用途 | 方法 | 固定源码 | SHA256 |
|---|---|---|---|
| 我方当前正式保留入口 | paired100，纯算法100μs | [paired_penalty100.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/a00677d59154156ac1da04b236c1bf8d0cff64b1/src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp) | `3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15` |
| 我方联合修正版，未晋升 | risk_pool100 | [return_risk_pooling100_v1.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/a00677d59154156ac1da04b236c1bf8d0cff64b1/src/Vanius0525/level1/round9/pure/return_risk_pooling100_v1.cpp) | `52ae25812a9863eae0774b2d45e837fd499506431650b8943ed6e4e979c76d2e` |
| 上游R80共享版强对照 | R80_next_hier_fast100 | [R80_next_hier_fast100_reference.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/a00677d59154156ac1da04b236c1bf8d0cff64b1/src/Vanius0525/level1/round10/R80_next_hier_fast100_reference.cpp) | `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d` |

若只需复现“我方当前提交算法”，用第一行；若要客观选这三个方法中当前环境的优胜者，三行加同批官方Naive一起测。R80共享版在已核旧72+12的平均指标上更强，尚未通过本项目严格的跨范围尾部门槛，故没有改写当前入口。联合版在dyna明显优于原paired，但原60训练晋升门槛失败。R12软核心/尾部折扣是后来的负结果，不应只因轮次更晚就作为最佳版。

三个文件均为`MySpillScheduler`提交类，使用官方C++14框架编译（本项目已测g++11.4、`-std=c++14 -O2 -Wall -Wextra -pedantic`）；不是独立带main的完整程序。R80文件有混合换行，校验完整原字节时不要让下载工具或编辑器转换换行。100μs是算法内部代理，计分仍用输入真实罚值，不能把测试输入的罚值统一改成100。

同一环境使用固定输入SHA、同一官方框架/编译参数，每方法每题一遍，Naive同批重测；同时保存IO、Miss、D、总成本、wall和失败。主结果用实际含D分数，物理成本单列。旧完整比较是final2.1全72与dyna1.0全12，分别求均值后各占50%；若采用新final3.0，必须单列版本与输入SHA，不能和旧版成绩合并。此文件只固定重测身份和口径，没有启动第三方任务或恢复AI测试。
