# corner_case 1.0.0

收集得到 **190** 份既有输入：`eval/` 有 **179** 份基础参数处于官方范围的输入，`diagnostics/` 有 **11** 份范围外微型诊断。输入原字节不改，50MiB以上使用可逆gzip。

## 筛选定义

每例每遍用同遍Naive完整成本计算 `clamp(10*(1-VAL/BASE),0,10)`，先平均三遍。完整成本包含I/O、实际Miss罚项与SDK实测回调耗时D。
按用户“目前最好算法低于1.5分”的要求，本包采用更保守、可复核的口径：**mix、clock、R75、R74、已发布小树、原Vanius六个冻结候选中，逐例最高均分仍严格小于1.5/10**。Naive只用于配对基线。不是数学意义的全局最优算法结论。

从声明范围内371份去重候选实测，7种方法各3遍，共7791条有效SDK记录；另排除16份普通均匀IID对照及其派生版本。非均匀IID Zipf/热点/长尾保留，结构化循环和资源边界也保留。
来源覆盖旧成员显式corners、cyanneko结构覆盖、Vanius合法edges、旧22个资源边界、当前主集已知低分、R70/R73/R74/R75开发输入；不是对仓库所有输入的穷举。

## 样本长什么样

| 类型 | 数量 |
|---|---:|
| 参数极值与混合阶段 | 80 |
| 倾斜访问与其他结构 | 43 |
| 容量临界与空分区 | 25 |
| 低改善空间与结构化控制 | 21 |
| 算子竞争与阶段交错 | 11 |
| 周期扫描与重用距离 | 6 |
| 热点迁移与大小热度反转 | 4 |

- 参数极值：冷热分区大小差异、读写带宽反转、罚值和周期极端组合，以及BUILD/PROBE交错。
- 容量临界：活跃分区组合恰好超过内存、空构建分区仍被探测，或必须淘汰的目标分区。
- 时间结构：周期扫描、长重用距离、热点迁移/反转、算子竞争和下一请求保护。
- 低改善空间控制：有些低分表示Naive已经接近该轨迹的成本下界，不能把所有低分都解释为算法错误。
本定义的1.5分阈值表示：按逐遍配对、截断后平均，相对Naive的得分不足15%；不是绝对延迟，也不是官方总分。

其中14例Naive的I/O和Miss本身均为零；30例在已测算法间I/O与Miss完全一致。已在manifest逐例标注，不能把这些全部解释为缓存策略失效。

## 文件和复核

- `manifest.json`：每例SHA、原GitHub提交/路径、参数、六法得分、最高分、参数范围与配对标记。
- `evidence/measurements.jsonl`：入选样本的完整三遍数值；`all_candidate_measurements.jsonl`保留全部实测候选，`candidate_decisions.json`保留未入选分数。
- `algorithms/`：本次实测源码原字节；mix/clock基于Vanius，R74/R75来源source/cyanneko，已发布小树仅作强对照。原作者和源码内说明保留。
- `tools/verify.py`：不运行算法，核对输入/源码SHA、三遍矩阵、计分与阈值。
- `tools/benchmark.py`：接同一官方兼容框架，用CPU/C++14/O2重测；默认只测eval，显式参数才包含diagnostics。

在仓库根目录执行：
```sh
python corner_case/tools/verify.py
python corner_case/tools/benchmark.py --repeats 3
```

## 边界

这是按已观察算法成绩筛选的困难回归集，不能称独立盲测或用其均分证明泛化。配对罚值/周期/规模版本不算额外独立seed。微型输入即使引擎可执行，也不冒充官方范围数据。范围标记先核header参数，并由本次动作/容量严格重放补充执行验证，不是对所有题面约束的形式证明。
动作容量严格重放2226次通过，物理指标匹配6678条SDK记录；重放CPU时间不替代实测D。所有算法同一逻辑CPU计时，未宣称硬件独占。
原数据、现有默认方法、其他成员文件及旧测量均不覆盖；本目录不自动加入默认成员suite。
数据固定提交：[0f3000f015d8ef96b9a1e45a75b0672fcbf97925](https://github.com/cyanneko/HuaweiHackathon/tree/0f3000f015d8ef96b9a1e45a75b0672fcbf97925)；R74/R75源码固定提交：[bacc6cdc0bc8b19a0ea9d545bc1e5e5cbb57162e](https://github.com/cyanneko/HuaweiHackathon/tree/bacc6cdc0bc8b19a0ea9d545bc1e5e5cbb57162e)。
