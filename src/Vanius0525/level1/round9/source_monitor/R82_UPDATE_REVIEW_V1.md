# R82 已发布负结果与本项目 write1 的区别

2026-10-30。14:11:32 UTC实际监测到 `source/cyanneko` 更新为 `b1246ae64a006c679e57789766dc401da2a9ecb9`。本阶段读取并核对七个小源码/文档/选择记录，共65,544字节，没有下载输入、编译、运行求解器或重新计时。R80源码未变，Round11固定来源不因本更新改变。

## 具体改动和源码身份

两候选父版均为R80_next_hier_fast100，SHA `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`，没有混入R81的快速算子边际。

| 候选 | 原字节SHA-256 | 已核字节数 |
|---|---|---:|
| R82_write1 | d23b0fa17bbec229fae40343b502b31160fda6a155ce4357afec40b0d977c44e | 25,721 |
| R82_singlefit025 | f51a53c07ef19bedcadfce06b6f2d2ed985095ed54cd198d03b960325af4249e | 26,991 |

两份源码均与发布manifest逐字节SHA及大小一致。

**R82_write1与我们的Round10 write1不完全相同。** 两者都只改top4子集的当前写费权重，不改变排序或原回退流程。但R82新增 `ordinary=全部算子PROBE && !scan && !uniform_cycle`，该条件成立才用1，其余仍用0.25。我们已测试的 `round10/R80_write1.cpp`（SHA `bc2be976f444854c746f1d568a8fabab0e7302d627a5211aa718d5a94ecf2207`）对所有实际进入top4枚举的路径用1，包括BUILD/混合等非ordinary路径。

已做全文规范化换行后的精确变换检查：R82恰好是父版增加ordinary检查并替换写项为三元条件；我们的版本恰好是无gate地替换0.25→1.0。原字节SHA另外保留，未改原文件换行。差异见 `R82_WRITE1_SOURCE_DIFF_V1.patch`。不能把两个结果叫完全相同策略的重复实验，也不能把其38例结果与我们的60例均分直接混算。

**R82_singlefit025改变候选池，系数仍为0.25。** 仅在ordinary路径中，在原受害者收集扫描里保存每对象 `priority*s+.25*s/W`，寻找能单独覆盖缺口、非空驻留、非当前目标且非已知next的最低损失对象。原proposal只生成一次，先执行原有多余SPILL裁剪，再把其全部剩余动作损失与最佳singleton比较。严格更低才替换，平局保留原方案；原proposal即使来自top4不足后的贪心回退，也参与同一比较。它不是“找到大对象就优先驱逐”，也不是只跟未裁剪top4子集比。新增动作只有最后实际选中者被记录。

这里的“全部single-fit”仍受原目标/next保护和ordinary gate约束，不等于遍历题面允许的所有动作集合。新增工作为常数次线性扫描，没有全分区组合枚举；本阶段仅静态核对，不替代动作或性能验证。

## TRAIN38、门槛和结果

TRAIN38完全复用R81开发面板：R80已有26输入，加R81新增12输入。所谓新增12是六条seed谱系各none/hot成对，已经用于R81开发，本轮不是12个新独立seed。六方法含同轮Naive、R79、R80共享概率、R80双方案及两候选，38×6=228格、每格单遍。以下为已发布报告及选择JSON中的数字，本监测没有独立解析228份原始输出或重测。

| 方法 | 旧26均分 | 新12均分 | 全38均分 | 新12物理/父版均值 | 全38最坏含决策成本/父版 |
|---|---:|---:|---:|---:|---:|
| R80共享概率父版 | 4.513727 | 5.910890 | 4.954936 | 1.000000 | 1.000000 |
| R82_singlefit025 | 4.376177 | 5.715462 | 4.799109 | 1.045213 | 1.139643 |
| R82_write1 | 4.500141 | 5.903565 | 4.943327 | 1.002661 | 1.011478 |

两个候选在新12均为1胜11负，全38均为7胜31负。相对父版，新12含决策均分分别下降0.195428与0.007325；去掉决策后物理成本仍增加约4.52%和0.27%，因此本批负结果不能只归于运行时间。

其事前规则是新12同轮Naive均分严格提高、旧26下降不超过0.05分、全38最坏成本/父版不超过1.25，且完整且分母有效；没有额外D倍率硬淘汰。singlefit同时未过新12提高和旧26回归条件；write1只未过新12提高，两者均通过该1.25尾部门槛。`advance.json`和`failure_report.json`均selected空。失败的是预设性能条件，228格执行本身全部有效、无失败/超时；默认没有改变。

这些门槛与本项目Round10的门槛不同，不能把上游门槛通过当成本项目晋升证据，也不能由两个固定开发面板推断所有分布下无效。表中物理成本为模拟I/O加实际Miss罚值，不含决策D；成本比例先逐例取比再平均。

## reserved DEV 是否运行

R82另生成12个150k操作DEV，六个新seed各none/hot成对，共1.8M操作、36,559,012字节。源码包报告声明没有策略运行。已直接核到以下归档证据：

- `src/reports/r82_20261030/evaluation/train/advance.json`：selected=[]，reserved_dev_results_consulted=false，SHA `16ceefff3879fc4686d9a13695d31ba08562ad0ef4c52e924d560a4c0172d044`。
- `src/reports/r82_20261030/review/failure_report.json`：dev12_policy_runs=0，SHA `b6b5bb42ba750f0cf78a5c162ed74997955e397d27d155daad13a87c7008a291`。
- Git中 `evaluation/` 只有执行器、协议检查器与train子树，没有DEV评测目录或DEV策略输出。

因此发布归档支持“DEV未运行策略/未查看性能”的声明；这不是对仓库外所有历史进程的证明。数据侧agent另外核metadata中的policy_evaluated/reserved/training_allowed字段，此报告不代替其完整输入/来源核查。本监测没有访问DEV实际请求或成绩，也不会自动把它转作训练。

## 对当前工作的影响

本项目此前已记录singleton扩池及写权重改动的负结果，上游R82为另一个开发面板提供了类似方向的负证据，但带不同gate、数据和门槛，不能简单合并成一次实验。先复用代码和统计差异解释当前失败，不追加重复网格，也不中途改变Round11的固定observer。若未来提出新机制，须明确相对这些已失败改动增加了什么可证伪信息。

来源：[固定报告](https://github.com/cyanneko/HuaweiHackathon/blob/b1246ae64a006c679e57789766dc401da2a9ecb9/src/reports/r82_20261030/report_zh.md)、[两份冻结源码](https://github.com/cyanneko/HuaweiHackathon/tree/b1246ae64a006c679e57789766dc401da2a9ecb9/src/experiments/r82_victim_search_20261030)、[本地源码与归档核查](R82_SOURCE_EVIDENCE_V1.json)。
