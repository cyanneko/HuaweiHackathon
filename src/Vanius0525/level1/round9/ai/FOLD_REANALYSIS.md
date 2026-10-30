# 旧四折口径审计与一次分层重分析

旧32独立seed确实没有同seed泄漏，但默认GroupKFold与生成器family=j%4恰好对齐：四个测试折分别是8条lognormal、8条hotspot、8条zipf、8条uniform。因此旧局部树结果是整族未见泛化，不能直接代替同family新seed泛化。

按预先固定SHA键`round9_family_strat_v1:<family>:<seed>`在每族内排序、排名mod4分派，新每折包含每族2个seed。仍用原192行、每流6状态、depth3/leaf12、random_state830103、原目标/权重/零阈值；只运行这一次，不搜索划分或参数。原V1所有1M流都属于lognormal的限制仍在，不能靠重划折消除。

| 条件目标 | 旧整族留出 | 新家族分层seed留出 |
|---|---:|---:|
| 逐状态最坏续接收益 | -0.037958 | -0.000375 |
| 续接0平均收益 | -0.032601 | +0.000951 |
| 续接1平均收益 | -0.002060 | +0.002262 |
| 选择模式1的状态比例 | 14.58% | 4.69%（9/192） |

收益单位是合法满内存读写时间；较大为好。新协议仍未胜固定0的保守目标0，所以没有通过原预冻门槛；但“两个续接均负”的旧结论不再适用于同family新seed协议。完整训练数据未变，原全量树仍恒选0；此重分析没有产生可部署晋升候选，也没有访问保留验证。

`FOLD_FAMILY_AUDIT.json`还完整列出了两套块门控历史划分：原seed+family划分确有同seed交叉（Round8已发现并披露）；whole-seed复核不交叉，其测试族也并非总是训练未见。不同协议的目标分布必须分别报告。

Round8的74个冻结产物SHA在重分析前后全部相同。计划和新结果分别为`FAMILY_REANALYSIS_PLAN.json`、`FAMILY_REANALYSIS_RESULTS.json`；新折源码仅写本目录。没有新solver调用，没有dev/eval/learning-validation查询。
