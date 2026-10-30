# corner_case 2.0.0：针对最新Vanius的低分回归集

共 **207** 份既有输入：`eval/` **192** 份基础参数范围内样本，`diagnostics/` **15** 份范围外微型诊断。输入原字节保留，大文件无损gzip。

## 唯一筛选算法

**只按最新Vanius纯算法的分数筛选，不取其他算法最高分。**
- 分支：`source/Vanius0525`；固定提交：`28094bdec34ff7110d9f1614703d0b09d383d4a6`。
- 当前推荐入口：[src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/28094bdec34ff7110d9f1614703d0b09d383d4a6/src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp)。
- 实测源码SHA256：`3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15`，保存原Git blob字节。
- 发布前复查分支头`27b8faf0fa27deaa43e2f2b8b0f3e26e2ca24e05`：当前推荐pure入口与本次实测源码完全相同，详见`evidence/latest_source_confirmation.json`。
- 此为Round9的paired_penalty100，固定100us Miss代理保持原样；引擎计分仍使用输入真实罚项。旧MySpillSchedulerBest.cpp是历史原件，本版未使用。

每例每遍以同遍Naive完整成本计算 `clamp(10*(1-VAL/BASE),0,10)`，先平均三遍；零VAL/BASE按规则计零。**Vanius均分严格<1.5/10才入选。** 完整成本包含I/O、真实Miss罚项及SDK实测回调D。
419份候选×2方法×3遍=2514条全新测量，Naive只作配对基线。排除16份普通均匀IID对照及派生版本，保留非均匀IID的Zipf/热点/长尾、结构化循环和资源边界。
候选覆盖旧成员显式corners、cyanneko结构覆盖、Vanius合法edges、22个资源边界、完整72例主测试，以及R70/R73/R74/R75开发样本。取消了上一版按mix低分只取主集24例的预筛；不是对全仓库所有输入的穷举。

## 类型

| 类型 | 数量 |
|---|---:|
| 参数极值与混合阶段 | 83 |
| 倾斜访问与其他结构 | 46 |
| 容量临界与空分区 | 26 |
| 低改善空间与结构化控制 | 25 |
| 算子竞争与阶段交错 | 16 |
| 周期扫描与重用距离 | 7 |
| 热点迁移与大小热度反转 | 4 |

这些样本分别考查参数极值、BUILD/PROBE阶段交错、容量临界、空分区、周期扫描、热点迁移及大小热度取舍。低分不自动证明算法错误：Naive本身可能已经接近该轨迹的可达成本。
其中14例Naive的I/O和Miss均为零，已逐例标注。

## 优先排查的样本

入选样本中，有**60例**最新Vanius的I/O加真实Miss罚项高于已实测Naive。按该物理成本比排序，挑三个不同类型的代表：

| 样本 | Vanius三遍均分 | 物理成本/Naive | Miss：Vanius / Naive |
|---|---:|---:|---:|
| [cc_0005_burst_mixture](eval/cc_0005_burst_mixture.txt) | 0.0000 | 200.35倍 | 1185 / 0 |
| [cc_0049_operator_competition](eval/cc_0049_operator_competition.txt) | 0.0000 | 103.09倍 | 610 / 0 |
| [cc_0001_build_probe_overlap](eval/cc_0001_build_probe_overlap.txt) | 0.0000 | 30.00倍 | 177 / 0 |

这些仅表明相对Naive存在已测回归，不代表离线最优差距或新方法收益。表中物理成本比单独排除D以辨别I/O与Miss问题；入选分数仍包含实测D。完整60例统计见`evidence/improvement_priorities.json`。

## 证据与复现

- `manifest.json`：唯一Vanius版本、来源、参数、SHA、三遍平均分与筛选分。
- `evidence/measurements.jsonl`：入选样本的三遍完整指标；`all_candidate_measurements.jsonl`保留全部419候选，两者均只有Naive和最新Vanius。
- `candidate_decisions.json`保留未入选分数；`changes_from_v1.json`记录口径纠正前后的移入移出。
- `algorithms/vanius_latest.cpp`：本次实际测试的最新Vanius原字节。
- `tools/verify.py`：不执行算法，校验输入/源码SHA、单法三遍计分与阈值，拒绝旧多算法schema。
- `tools/benchmark.py`：CPU/C++14/O2独立复测；默认仅eval，显式选项才含微型diagnostics。

```sh
python corner_case/tools/verify.py
python corner_case/tools/benchmark.py --repeats 3
```

419次Vanius动作/容量严格重放通过，匹配1257条Vanius SDK物理记录；1257条Naive另核完整矩阵。重放CPU时间不替换真实D。统一逻辑CPU计时、60s/次上限，不保证硬件独占。

## 与旧版的区别

旧1.0.0是六算法最高分筛选190例，不符合“针对最新Vanius”的目标。本2.0.0纠正为最新Vanius单法，新增20例、移出3例。旧版保留在原Git提交历史中。
这是一套按已观察Vanius成绩选择的困难回归集，不是独立盲测，也不能据换集后的均分推断算法提升。配对费用/周期/规模版本不是额外独立seed。范围标签只说明基础参数，动作与容量另经执行核查；微型诊断不冒充官方范围数据。
