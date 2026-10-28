# R57 完整公共集合结果（净化派生包）

2026-10-28。本包来自已封存报告，没有新增运行、重编译或训练。它测量原独立直接调度器；**single_fit_phase 的结果不是 ID103 适配版时延**，也不是训练后的融合器结果。

范围：cyanneko **0.3.0** 的24个已见开发/回归案例；member2/member3为空、跳过，不计分母。9次原main schema3 CLI各跑完整集合一次，固定轮序，3候选×24例×3重复=216次候选运行，另有216次新配对Naive，**432/432成功、0失败、0超时**。没有Naive自比评分。

数据与suite指纹见 [datasets.json](datasets.json)，精确代码/程序身份、9报告来源SHA与轮序见 [provenance.json](provenance.json)。协议为official-2026-10-26。Naive基线身份仍是来源声明，数字核验不自动认证算法动作；Naive仅按size排序，不能与按ID打破平局的largest_linear混称动作等价。

## 分数与尾部

| 方法（direct） | 集合分/全成员均分 | 逐例倍率均值 | P50 | P90 | worst | 胜/平/负 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best_fit_fast | 50.000000 | 1.495087 | 0.872244 | 4.118391 | 9.300542 | 18/0/6 |
| next_guard_fast | 38.555302 | 1.280362 | 0.995756 | 1.723324 | 8.293971 | 16/0/8 |
| single_fit_phase | 50.000000 | 1.245576 | 0.737620 | 4.118403 | 7.415080 | 18/0/6 |

倍率为每例三次候选均值成本/其自己的三次配对Naive均值成本，越小越好。P50为普通中位数；24例nearest-rank P90为第22项，不是逐回调分位。胜平负按未舍入倍率与1比较。

**BF/SF封顶50不代表没有退化。** BF/SF最差为r54_cross_operator_0_eval，NG最差为r54_cross_operator_3_eval；worst分别约9.30/7.42/8.29。NG不是通用稳定保底。相对Naive的累计成本比与逐例倍率均值不是同一统计量，均保存在summary。r54_control_0_eval的IO/miss为零，其得分含决策计时波动，不能称I/O收益。

每次配对先clip(10×(1−VAL/BASE),0,10)，VAL或BASE为0依runner规则记0；每集合每次重复求和封顶50，再重复均值，最后集合等权平均。本轮只有一集，因此集合分等于总体均分。逐例mean_score是**先逐次clip再平均**，不能由mean cost ratio反推；例如分次收益与退化并存时二者不同。

## 可复核文件

- [measurements.jsonl](measurements.jsonl)：432条成功测量，候选/配对Naive五指标、原stdout、wall、输入SHA、来源报告SHA与全局repeat。所有原CLI内部repeat均为1，重编号不伪造同一CLI三重复。
- [paired_cases.csv](paired_cases.csv)：216个配对，每次两套五指标与真实单分。
- [case_summary.csv](case_summary.csv)：72个方法×案例的三次均值、mean单分和成本倍率。
- [summary.json](summary.json)：逐集每重复封顶分、集合均值、全成员等权均值与P50/P90/worst、原始成本/决策时间。
- [case_info.json](case_info.json)、[datasets.json](datasets.json)：输入头可核对统计、版本与48个输入/meta指纹；真实输入在datasets分支。
- [artifact_manifest.json](artifact_manifest.json)：本包文件SHA，不包含自我哈希。原封存报告/完整程序源码仅引用SHA，未将本机路径、主机名、聊天ID或私有运行环境复制进来。

从源码分支仓库根运行纯数值核验（Python3.10+标准库，不启动solver）：

```sh
python -B src/reports/r57_public_suite_20261028/verify.py
python -B src/reports/r57_public_suite_20261028/test_verify.py
```

核验五字段/计数/成本公式、216个配对完整性、逐次单分/集合封顶/均分、分位及CSV与文件SHA。测试另检验篡改、缺失/重复测量，以及不能从mean ratio反推mean分。它不能独立证明原计时环境、官方基线身份或每条动作合法。

原执行保护为内部每case10秒、整CLI60秒，均未触发；不据此作官方超时或500万操作保证。数据是已见公共开发集合，不是隐藏集或独立泛化验证。没有将失败例删掉再评分；任何未来失败须单列失败而不能填0。

对应已发布或本分支源文件：[BF原类](../../methods/r53/best_fit_fast.cpp)、[NGfast原类](../../experts/next_guard_fast/reference.cpp)、[SF冻结原类](../../experts/single_fit_phase/reference.cpp)、[Naive类](../../methods/r49/official_naive.cpp)。新的SF适配另有独立动作验收，不能继承本表direct计时。
