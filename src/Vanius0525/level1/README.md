# Level 1：纯算法与小神经网络调度器

本轮只优化可测的Level 1成本，不讨论主观加分包装。调研、反例与适用边界见 [RESEARCH.md](RESEARCH.md)，实验结果见 [RESULTS.md](RESULTS.md)，机器可读证据见 [VALIDATION_SUMMARY.json](VALIDATION_SUMMARY.json)。

## 两个提交候选

| 文件 | 方法 | 部署 |
|---|---|---|
| [MySpillScheduler.cpp](MySpillScheduler.cpp) | 无模型训练；部分观测历史、代价密度、扫描/循环检测、快速受害者选择、保留信息的预取 | C++14标准库 |
| [MySpillSchedulerAI.cpp](MySpillSchedulerAI.cpp) | 同一合法接口，最多4个候选经过12×16×1 ReLU（负值置零的激活函数）网络重排；模型权重已内嵌 | 同上，无第三方推理依赖 |

**一次只提交其中一个文件。** 两个文件都只定义 `MySpillScheduler : public SpillScheduler`，没有main或执行引擎。其他cpp是保留的实验/失败对照或独立测试工具，不能一起编译为提交物。历史v1快照保留原字节与已知空行缩进；非冻结实验的空行空白清理记录在FORMAT_NOTES.json。按当前实测平均逐例分数，AI略高，可作为分数优先候选；纯算法保留为较低开销的对照与备选。AI尚未稳定胜过纯算法，具体范围见结果。

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

## 小时检查与继续研究

`hourly_check.py`运行于本地WSL，首轮22:39已完成，之后每小时运行新seed回归和一组参数试验；不自动晋升候选。结束后通过官方 `codex queue` 把 [HOURLY_RESUME_PROMPT.md](HOURLY_RESUME_PROMPT.md) 排入原会话，继续研究。已实测queue成功，不创建新代理或新会话。

这依赖WSL/app-server继续运行，不是云端Scheduled任务。会话绑定与进程状态只保存在忽略的 `build/hourly/`；不提交聊天ID、私人状态或凭据。查看 `build/hourly/status.json`、`last_queue.json` 和每轮summary；创建 `build/hourly/STOP` 可在当前案例完成后停止。实验锁只串行化本项目工具，不能保证整个操作系统没有其他负载。

版本与优化过程见[OPTIMIZATION_HISTORY.md](OPTIMIZATION_HISTORY.md)、[VERSION_LEDGER.json](VERSION_LEDGER.json)。第二轮新增568个团队样例的结果见[round2/RESULTS.json](round2/RESULTS.json)；较大团队集上纯算法均分略高于AI，尚无新的候选晋升。

后续候选按[三人等权内部指标](SCORING_POLICY.md)选型，结果见[BALANCED_RESULTS.json](BALANCED_RESULTS.json)。该指标不是官方分数。第三阶段外推反例与CPU结果见[round3/RESULTS.json](round3/RESULTS.json)。
