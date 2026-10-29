# GitHub 数据、源码与报告更新核对（2026-10-30）

本页比较矩阵冻结提交与本次读取的远端提交，记录文件、版本和作者报告的变化。核对依据为固定 Git 对象及文件字节；本次没有执行成员脚本、编译、训练、求解器计时或独立动作重放。后续分支可能继续前进，复核以下固定提交。

## 数据集合与旧矩阵边界

本次数据固定于 [e119c2326e198922243306eac062785420ed8156](https://github.com/cyanneko/HuaweiHackathon/tree/e119c2326e198922243306eac062785420ed8156/datasets)，共有 **840训练例、785评测例**。评测输入共137,224,870字节、8,086,312条操作，不含相邻meta的字节数。

| 成员 | eval/VERSION | train | eval | eval输入字节 | 相对旧矩阵 |
| --- | --- | ---: | ---: | ---: | --- |
| Vanius0525 | 0.1.0 | 192 | 209 | 49,738,657 | 新增非空成员集合 |
| cyanneko | 0.6.0 | 48 | 48 | 21,784,797 | eval树及原字节不变 |
| liunianwww | 0.1.0 | 600 | 528 | 65,701,416 | eval树及原字节不变 |

空member2/member3仍跳过。评测只要求至少一个有效非空集合，不要求三人都上传；成绩绑定本轮实际参与成员、版本与指纹。缺失/空集合可跳过，已有数据却非法或运行失败不能静默排除后给完整成绩。

**576例是冻结旧矩阵，785例是本次核对的新数据快照。** 旧矩阵固定于 [e4fd35e0bb2839c5b001020853fb367a73045d67](https://github.com/cyanneko/HuaweiHackathon/tree/e4fd35e0bb2839c5b001020853fb367a73045d67/datasets)，含cyanneko48例和liunianwww528例。新增209例不改变已启动矩阵的输入、分母或冻结源码。新的完整785例结果须另记实际源码、数据、重复、基线和评测器身份，不将两个快照的未封顶总分直接横比。

| 集合 | suite_id | 完整集合的成员权重 |
| --- | --- | --- |
| 旧576例 | `602191841f2205206b102f14aa5bca306f32b346953b1a33bb8c79b84c064c87` | 两成员各1/2 |
| 新785例 | `a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1` | 三成员各1/3 |

个人集合指纹按原评测器的member、VERSION、输入与相邻meta相对路径/SHA-256计算：

| 成员 | 集合SHA-256 |
| --- | --- |
| Vanius0525 | `ffb67eae2f23002bf3050a4b5b038c0bb5eadcc86c069f424ed1b26f4518458a` |
| cyanneko | `b22cd2f478cb798b84484ffe3432d54e1f25721314c65935c1a7d1fe5a0a3f50` |
| liunianwww | `ef37977db33edfa06d400cda486b2bf9098a3df6c1e754eb6b7908c7c89e4788` |

Vanius0525新增数据见[发布提交 b131982](https://github.com/cyanneko/HuaweiHackathon/commit/b13198234c4f70031afe884a5deef10de340cc78)与[作者说明](https://github.com/cyanneko/HuaweiHackathon/blob/e119c2326e198922243306eac062785420ed8156/datasets/Vanius0525/README.md)：train为64+96+32例；eval为holdout64、OOD64、round3 fresh32、round3 OOD32与17份边界案例，共209例。缺少所需SWITCH的旧end_insert诊断位于diagnostics，不计入eval。作者VALIDATION.json声称401份train/eval通过其记录的公开审核器；本次只读取该声明与文件身份，没有重跑审核，不能称为我们的独立合法性验证。这些数据已有开发或评测观察，名称中的holdout/fresh不表示对后续实验仍是未见数据。

## 各分支变化

| 分支 | 矩阵冻结提交 | 本次核对的提交 |
| --- | --- | --- |
| main | [b026a46](https://github.com/cyanneko/HuaweiHackathon/commit/b026a46364020d3bd06c88cf76bbd4dbe2550477) | [0a5d8cd](https://github.com/cyanneko/HuaweiHackathon/commit/0a5d8cd16a2aa875439f0de34658e1112c8812ec) |
| datasets | [e4fd35e](https://github.com/cyanneko/HuaweiHackathon/commit/e4fd35e0bb2839c5b001020853fb367a73045d67) | [e119c23](https://github.com/cyanneko/HuaweiHackathon/commit/e119c2326e198922243306eac062785420ed8156) |
| source/cyanneko | [b148d5a](https://github.com/cyanneko/HuaweiHackathon/commit/b148d5aaedb28dc3ac146a6a20d3f7dd8a87bd56) | [07f24f2](https://github.com/cyanneko/HuaweiHackathon/commit/07f24f20eebb7f8713d9f8f5c7287fa6652947d6) |
| source/Vanius0525 | [f962792](https://github.com/cyanneko/HuaweiHackathon/commit/f962792606d76b00daf326c5d4c3074464eca47d) | [9e39e51](https://github.com/cyanneko/HuaweiHackathon/commit/9e39e51eab04a41a9e46948771a9d43f811d4770) |
| source/liunianwww | [149a91a](https://github.com/cyanneko/HuaweiHackathon/commit/149a91a7dda8ad5c03c360af1d3658bd3cc1d93b) | [d25e10c](https://github.com/cyanneko/HuaweiHackathon/commit/d25e10ca99a163e122e60225907805c8db44b310) |

Vanius0525新增11个具名阶段/overflow/BUILD保护候选实现，以及46份按哈希归档的C++快照。46份归档中28份与冻结旧源逐字相同，9份匹配新具名候选，另9份不匹配前两组，是额外历史源码版本；文件数不能当成新算法数。原MySpillScheduler.cpp与MySpillSchedulerAI.cpp没有变化。作者记录phase候选在fresh/OOD上收益不稳定，未晋升为正式版本。[VERSION_LEDGER.json](https://github.com/cyanneko/HuaweiHackathon/blob/9e39e51eab04a41a9e46948771a9d43f811d4770/src/Vanius0525/level1/VERSION_LEDGER.json)还明确标注一个旧scan测量版本的精确源码未保留，不能拿后来源码沿用该次历史成绩。

liunianwww新增[旧合并数据评测报告](https://github.com/cyanneko/HuaweiHackathon/tree/d25e10ca99a163e122e60225907805c8db44b310/design/dataset_integration_20261029)、逐例/分组/动作审计材料及PDF；五个算法C++文件没有变化，默认推荐仍为MySpillScheduler_final.cpp。该作者报告固定旧数据0be5082，即cyanneko0.5.0/40例+liunianwww0.1.0/528例，共568例、3次重复，不能称785例或576例完整成绩；报告中的测量与动作审核是作者记录，本次没有独立复测。

main与source/cyanneko相对矩阵冻结提交新增成员等权摘要工具、评分说明、旧结果只读重算以及原证明文件换行字节保留；算法、SDK默认ID及原evaluation/evaluate.py没有变化。原评测器SHA-256仍为`9a1231d5dc6913b694927ab34fb34d8c59889584c1cfb596959d9eaf383e09f3`。

## 现成分数的口径不同

本仓主汇总为[逐成员未封顶sum，再对非空成员等权平均](../evaluation/MEMBER_SCORING.md)：`mean_member(mean_repeat(sum_case(original single_score)))`。原评测器含50总封顶的raw分另行保留。

Vanius0525在首次核对提交9e39e51的[SCORING_POLICY.md](https://github.com/cyanneko/HuaweiHackathon/blob/9e39e51eab04a41a9e46948771a9d43f811d4770/src/Vanius0525/level1/SCORING_POLICY.md)中，在分层内按相同操作流去重，成员内部按normal80%+corner20%均分，三成员等权后乘5；其结果还复用了不同重复设置的旧测量。这是作者当时的内部诊断分，不是上述dataset sum，也不是一次统一785例计时。liunianwww的现成报告使用旧568例。两份现成报告都不能直接与统一矩阵主分横排；须核对相同数据/源码/基线和测量设置，再按一致公式汇总。

## 首次发布后的源码分支补充

同日发布总览后再次读取远端，Vanius0525已通过[856549e](https://github.com/cyanneko/HuaweiHackathon/commit/856549e)前进到[9aa7cac85dbebdca018a89dde373005791b654e9](https://github.com/cyanneko/HuaweiHackathon/commit/9aa7cac85dbebdca018a89dde373005791b654e9)。相对9e39e51只增加或修改8个交接/评分说明、JSON摘要与Python工具文件，没有C++源码变化。上表保留首次核对的固定提交，不将本次补充冒充矩阵实测。

作者新的[评分说明](https://github.com/cyanneko/HuaweiHackathon/blob/9aa7cac85dbebdca018a89dde373005791b654e9/src/Vanius0525/level1/SCORING_POLICY.md)改为每成员内逐题均分，再对三成员等权平均；旧80/20、去重权重与50分换算仅作历史。[CURRENT_SCORES.json](https://github.com/cyanneko/HuaweiHackathon/blob/9aa7cac85dbebdca018a89dde373005791b654e9/src/Vanius0525/level1/CURRENT_SCORES.json)自报纯算法3.134088、AI3.211106，继续复用不同批次、不同重复设置的原测量。该成员内均分仍不同于本仓当前的成员dataset未封顶sum，本次没有执行其重算脚本，也不据成员文档改变统一矩阵口径。

作者[交接文档](https://github.com/cyanneko/HuaweiHackathon/blob/9aa7cac85dbebdca018a89dde373005791b654e9/src/Vanius0525/level1/SESSION_HANDOFF_20261030.md)声明其周期性研究已经停止且不自动恢复。这里只记录对方发布的状态，不独立认证其运行进程，也不将该文档作为启动或停止其他成员工作的指令。

本页及随后的总览修订只更新说明，不改变输入、版本号、评分器或矩阵冻结提交，不新增性能结论。
