# Level 1：纯算法与学习增强调度器

**当前发布入口（Round8，2026-10-30）**：两条路线继续独立探索。新纯算法在综合50例同批3重复中均分2.855474，旧Best为2.647765；通过冻结门槛后晋升。含AI路线没有新模型晋升，保留原最佳。完整证据、负结果与限制见 [round8/README.md](round8/README.md) 和 [round8/CURRENT_BEST.json](round8/CURRENT_BEST.json)。

| 路线 | 当前单文件提交入口 | 综合50例平均分 |
|---|---|---:|
| 纯算法 | [paired_confidence.cpp](round8/pure/paired_confidence.cpp) | 2.855474 |
| 包含AI | [ai_prefetch_budget2048.cpp](round4/ai_prefetch_budget2048.cpp) | 2.587030 |

一次只提交一个`MySpillScheduler`类，C++14标准库CPU。根目录`MySpillSchedulerBest.cpp`和`MySpillSchedulerAI.cpp`保留历史原件，不是最新入口。上述综合集已曝光，均分按全部50例等权计算，不使用旧三成员等权，也不代表隐藏正式评测成绩或全局最优。

**持续工作**：两个子agent分别推进纯算法与含AI路径；训练/求解器经公共锁串行。Round8已完成，新工作转入Round9；运行进度应读取最新交接并核查进程，不从历史“已停止/已恢复”文字推断。见 [round8/HANDOFF.md](round8/HANDOFF.md)。本阶段未恢复旧小时服务，未新建定时服务。

## 以下为早期方法、结果和复现记录

下方Round1–6的“当前”“最新”与运行状态只描述各自历史执行窗口；不覆盖上面的Round8发布选择。Round6综合集基准见 [round6/CURRENT_RESULTS.json](round6/CURRENT_RESULTS.json)，Round7提名见 [round7/RESULTS_RESUME.md](round7/RESULTS_RESUME.md)。

本轮只优化可测的Level 1成本，不讨论主观加分包装。调研、反例与适用边界见 [RESEARCH.md](RESEARCH.md)，实验结果见 [RESULTS.md](RESULTS.md)，机器可读证据见 [VALIDATION_SUMMARY.json](VALIDATION_SUMMARY.json)。

## Round4发布候选（历史记录）

直接提交 [MySpillSchedulerBest.cpp](MySpillSchedulerBest.cpp) 的内容，类名已经是 `MySpillScheduler`。该文件仅使用 C++14 标准库、无训练/推理运行时依赖；一次只提交一个候选文件，不要与其他cpp合并编译。

选型口径是**阶段2固定11候选完整同批评测中，三成员每题均分再等权平均最高**，不是官方隐藏集成绩或所有分布上的最优保证。代码与已测 `pure_set025_io_asymmetry_routecount.cpp` 逐字节相同，SHA及证据见 [CURRENT_CANDIDATE.json](CURRENT_CANDIDATE.json)。

| 当前发布文件 | 本人209例 | cyanneko48例 | liunianwww528例 | 三成员等权/10 |
|---|---:|---:|---:|---:|
| MySpillSchedulerBest.cpp | 3.814995 | 4.176432 | 2.625153 | **3.538860** |

每例5次重复，785次独立动作审核通过；20000组ASan/UBSan抽象状态、40000次回调检查通过。保留原启发式的合法观测和循环路径；在有Probe证据或读带宽不低于写带宽时，在4个候选的小子集中计入写出成本，并去掉冗余SPILL。完整环确认前的快捷拒绝只优化实现开销。

**已知风险**：该版在新种子fresh3上均分比原纯算法低0.126835；其中serial301030的I/O+Miss为99707.54us，原纯算法为15185.78us（候选在此例等于Naive）。三成员已测最坏I/O+Miss/Naive比为5.299，较稳健版本为3.393。没有因均分最高而隐藏反例，也不假定正式测试的corner比例。

| 取舍 | 单文件候选 | 同批三成员均分/10 |
|---|---|---:|
| 较稳健纯算法 | [pure_set025_all_probe_routecount.cpp](round4/pure_set025_all_probe_routecount.cpp) | 3.479223 |
| AI候选，权重内嵌 | [ai_prefetch_budget2048.cpp](round4/ai_prefetch_budget2048.cpp) | 3.508052 |

新最大规模测试也显示条件差异：高带宽、B=1的500万请求随机例，有限预取版明显强于当前均分优先版；不能把某个特例的优胜替代完整套件选型。最新完整探索、模型负结果和corner敏感性见 [round4/README.md](round4/README.md) 与 [round4/HANDOFF.md](round4/HANDOFF.md)。原冻结提交文件继续保留原字节，后台未完成实验不视作已验证结果。

复现构建：`python build.py MySpillSchedulerBest.cpp --name current_best`。该命令只插入候选类，保存的参考框架不改。

## 首轮冻结提交候选（历史记录）

| 文件 | 方法 | 部署 |
|---|---|---|
| [MySpillScheduler.cpp](MySpillScheduler.cpp) | 无模型训练；部分观测历史、代价密度、扫描/循环检测、快速受害者选择、保留信息的预取 | C++14标准库 |
| [MySpillSchedulerAI.cpp](MySpillSchedulerAI.cpp) | 同一合法接口，最多4个候选经过12×16×1 ReLU（负值置零的激活函数）网络重排；模型权重已内嵌 | 同上，无第三方推理依赖 |

**一次只提交其中一个文件。** 两个文件都只定义 `MySpillScheduler : public SpillScheduler`，没有main或执行引擎。其他cpp是保留的实验/失败对照或独立测试工具，不能一起编译为提交物。历史v1快照保留原字节与已知空行缩进；非冻结实验的空行空白清理记录在FORMAT_NOTES.json。这两个文件是上一阶段冻结对照，其历史AI略高不代表本轮候选排序；当前发布入口及取舍见上表。

保存的官方参考框架未经逻辑修改。`build.py`从冻结题面提取框架并核对SHA，只插入选手类、选择其实例；额外audit仅包装调度器、输出动作，不改变engine。实际计分使用不带audit的程序。当前协议依据仓库保存版本，不认证隐藏评测实现。

## 纯算法怎样工作

- BUILD初始没有Probe证据时保持最大的分区优先，排除当前INSERT目标，不让学习式热度估计凭空改变冷启动。
- 用累计Probe序号去重当前Miss和next_op观测。只记真实可见对象，普通Hit没有对象信息；记录的是采样频数，不是假装拥有完整LFU。
- 一般情况下用衰减观测频数、访问间隔及扫描距离估计保留价值，乘读写成本和已知最小miss罚的单位字节代价。下一次准确可见Probe优先保留，容量不足仍有合法fallback。
- 常见单受害者路径线性扫描；多受害者使用heap，冷启动保留排序。只选驻留且非空的合法候选，释放量只计算真实缺口。
- 对全部分区等大小、全部已切Probe、完整循环的每条可见相邻边至少匹配3次的情况，启用MRU快速查找。模式是假设，不保证未来；观测到转移变化即重新分析。MRU近期列表也只有部分观测，不宣称精确Belady最优。它解决了跨算子循环下的稀疏回调抖动，并减少CPU开销。
- 通常只在空闲空间足够时预取。若为了预取提前驱逐，就可能丢掉之后Miss回调能看到的再下一条操作；已识别等大小完整循环时才允许腾空间预取。没有异步I/O重叠模型。

设n=K·P、v为实际驱逐数。最坏单回调O(n log n)，一般驱逐O(n+v log n)，周期无压力快路径O(1)，辅助内存O(n)。循环转移图分析最多O(n)/次，候选网络规模固定，因此AI最坏复杂度也不超O(n log n)。框架自身状态复制仍计入原计时，不能由调度器消除。

## 复现自造数据与评测

在本目录运行：

```sh
python build.py MySpillScheduler.cpp
python build.py MySpillSchedulerAI.cpp
python generate.py --out build/data/dev --count 64 --start-seed 290000 --probes 12000
python benchmark.py --data build/data/dev --scheduler pure=MySpillScheduler.cpp --scheduler ai=MySpillSchedulerAI.cpp --repeats 7 --out results/dev-reproduce.json
```

构建器输出完整可测程序路径；例如 `build/MySpillScheduler 输入文件.txt`。编译参数为Linux的 `g++ -std=c++14 -O2`，附带编译警告参数。没有修改框架源码。

数据划分：

| 用途 | 生成器/参数 | 数量 | 使用方式 |
|---|---|---:|---|
| 开发 | generate.py，seed290000起，12000 Probe | 64 | 已用于算法选择 |
| 训练 | seed291000起，8000 Probe | 96 | 仅此批拟合模型 |
| 验证 | seed292000起，12000 Probe | 32 | 选择候选/预取/推理范围 |
| 冻结后新种子 | seed293000起，24000 Probe | 64 | 首轮留出；后续迭代需视为已曝光 |
| OOD诊断 | generate_ood.py，seed294000起，16000 Probe | 64 | 新K/P拓扑与Probe规律；并非真实生产分布 |
| 团队补充 | datasets@0310af59，cyanneko 0.4.0 | 32 | 未用于拟合；不是官方隐藏集 |

所有完整生成数据、原始重复运行和二进制保存在忽略的 `build/`、`results/`，不把大日志放Git。一个可直接读取的合法自造反例已随代码保存于 [test_cases/opaque_hit_prefetch.txt](test_cases/opaque_hit_prefetch.txt)。生成器v1的burst长度逐次随机，不是固定长度的严格burst；OOD另有固定96次的burst，两者明确区分。

```sh
python generate.py --out build/data/train --count 96 --start-seed 291000 --probes 8000
python generate.py --out build/data/val --count 32 --start-seed 292000 --probes 12000
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python train.py --train build/data/train --val build/data/val --recollect
python make_hybrid.py
python finalize_candidates.py
python check_edges.py --scheduler pure=MySpillScheduler.cpp --scheduler ai=MySpillSchedulerAI.cpp --sanitize
python fuzz.py --cases 20000
python counterexample.py
python stress.py --n 5000000 --b 1 10000 --scheduler pure=MySpillScheduler.cpp --scheduler ai=MySpillSchedulerAI.cpp --out results/stress-reproduce.json
```

训练需要Python/numpy/scikit-learn；提交推理不需要它们。`train.py`使用冻结collector_v1.cpp输出基础MLP（多层感知机神经网络），`make_hybrid.py`结合纯算法快路径，`finalize_candidates.py`打包自适应预取并检查提交指纹；同版本numpy/scikit-learn下完整重跑已复现。最终adaptive预取版本的来源见 `CANDIDATE_FREEZE.json` 及实验源码。回调特征从collector真实可见的历史提取，未来仅作离线标签；collector与部署策略改变后，观测分布仍会变化，这个问题没有被消除。

独立Python重放会检查每一步动作是否合法、容量、目标保护、Miss末项LOAD，以及I/O/Hit/Miss是否和未改引擎一致；小状态oracle仅在不超过8个分区时穷举所有合法回调动作，包括预取。它是测试专用离线最优，不在提交推理中运行。

## 新会话接管与周期检查

每小时检查和自动续接已按用户最新指令取消。`hourly_resume.py`已停止，`build/hourly-resume/STOP`及旧`build/hourly/STOP`保留，不自行移除或因历史排队消息重启。已启动实验继续执行，具体PID/日志仅在本地忽略目录；新会话应先核查，不重复启动。

最新完整入口：[SESSION_HANDOFF_20261030.md](SESSION_HANDOFF_20261030.md)。用户已授权只读参考两位合作者的进展和算法，所有修改仍仅在本人分支；当前只完成来源fetch，未读算法正文/未融合方法，见[round5/HANDOFF.md](round5/HANDOFF.md)。

版本与优化过程见[OPTIMIZATION_HISTORY.md](OPTIMIZATION_HISTORY.md)、[VERSION_LEDGER.json](VERSION_LEDGER.json)。第二轮新增568个团队样例的结果见[round2/RESULTS.json](round2/RESULTS.json)；较大团队集上纯算法均分略高于AI，尚无新的候选晋升。

历史分层内部指标见[SCORING_POLICY.md](SCORING_POLICY.md)及[BALANCED_RESULTS.json](BALANCED_RESULTS.json)，已被当前逐成员每题均分口径取代，不再用于本轮选型。第三阶段外推反例与CPU结果见[round3/RESULTS.json](round3/RESULTS.json)。

当前检查已再次取消，新会话交接入口：[SESSION_HANDOFF_20261030.md](SESSION_HANDOFF_20261030.md)；当前发布候选与同批三成员成绩：[CURRENT_CANDIDATE.json](CURRENT_CANDIDATE.json)；原冻结两版的历史汇总保留于[CURRENT_SCORES.json](CURRENT_SCORES.json)。
