# 双时间尺度分层复用调度器：实际算法、可见信息与完整回调复杂度审计

审计日期：2026-10-31。仅静态只读审计；未编译、未运行调度器、未读取大输入、未修改最终 R81、未进行网络或共享 Git 操作。

## 1. 审计对象与结论边界

- 最终语义命名源：[最终语义命名源](https://github.com/cyanneko/HuaweiHackathon/blob/3064e270fde0473810cd8c0e57b738ee48356254/submission/MySpillScheduler.cpp)，SHA256 `2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`。本算法内部版本为R81，下文以机制名称说明。Root提供的已发布代码commit为`3064e270fde0473810cd8c0e57b738ee48356254`，固定代码路径`submission/MySpillScheduler.cpp`；本审计未联网重查远端。
- 逐行审计基准源：[逐行审计基准源](https://github.com/cyanneko/HuaweiHackathon/blob/a1ee48aee1af3b561efa2eacc5c68769a9a0dc83/submission/MySpillScheduler.cpp)，SHA256 `ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65`；本文行号沿用此基准。最终源只增加五条宏注释并重命名五个宏，算法不变。
- 已读取命名工程的已有命名验证记录（公开摘要见[verification.json](https://github.com/cyanneko/HuaweiHackathon/blob/3064e270fde0473810cd8c0e57b738ee48356254/submission/verification.json)，原本地validation原件未单独发布）：其记录原始/可读/语义命名版本预处理tokens相等，C++14 -O2构建ELF相同（`bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1`）。这是已有命名验证证据，本审计未重新编译。
- 框架语义参照：R81已测官方兼容TU（[固定原始归档](https://github.com/cyanneko/HuaweiHackathon/blob/b09ece11af152a705ef2df27162cade838399287/src/reports/r85_20261030/measured_sources/R81_op256_cond2048.tu.cpp)） 的接口与引擎部分；并未据此声称两个类文件逐字相同。
- 源中启用宏：`HASHJOIN_OPERATOR_HALF_LIFE=256, HASHJOIN_REUSE_ESTIMATOR=2, HASHJOIN_ADAPTIVE_RISK_SHARING=1, HASHJOIN_REFAULT_MODEL=3, HASHJOIN_SIZE_BIAS=0`（逐行审计基准第1—5行）。
- 记 K 为算子数，P 为每算子的分区数，N=KP。本文 N 不是框架输入文件中的操作行数 N；以下另用 T 表示回调次数。
- 在固定有效 K、P，合法索引、正带宽、可满足容量请求及通常 RAM/浮点单位成本模型下，完整调度器回调的上界是 `O(N log(N+1) + P + A_prev + C_init)`；由于 P≤N 且本实现单次待确认动作数 A_prev≤N，可以写成 `O(N log(N+1) + C_init)`。额外内存 `O(N + C_table)`。这里明确计入了更新、确认、概率缓存、结构识别、动作整理，不是只看排序得出的结论。
- `C_init` 是固定查表的首次惰性初始化工作，总共 18,436 个 double 表项；它不随 K/P 增长，但会进入触发初始化的真实回调耗时。已有源中的“common one-victim linear”只能描述常见分支；不能据此把完整所有回调一概称为 O(N) 或 O(1)。

宏名对应关系（仅机械重命名）：

| 旧宏 | 最终语义宏 |
|---|---|
| `R81_FAST_HALF` | `HASHJOIN_OPERATOR_HALF_LIFE` |
| `R80_MODE` | `HASHJOIN_REUSE_ESTIMATOR` |
| `R79_ADAPTIVE` | `HASHJOIN_ADAPTIVE_RISK_SHARING` |
| `R74_MODE` | `HASHJOIN_REFAULT_MODEL` |
| `R74_SIZE` | `HASHJOIN_SIZE_BIAS` |

## 2. 真实活动路径

`release` 每次使概率缓存失效，然后仅调用一次 `propose(..., frequency_mode=2)`；随后因 `HASHJOIN_REUSE_ESTIMATOR!=3` 直接返回（762—779行）。因此：

1. 当前路径使用层级频率分支，不运行方案对照分支。
2. `comparePlans`、`chooseAlternative` 的均值、方差、置信边界与 paired 选择逻辑没有被调用，不能写成 R81 实际贡献。
3. `HASHJOIN_SIZE_BIAS=0`，候选密度的额外 `sqrt(1+size/typical)` 修正没有启用；但字节大小仍决定容量约束、密度和 I/O 成本。
4. `HASHJOIN_ADAPTIVE_RISK_SHARING` 只控制 `refaultReuse` 的风险共享系数；主层级概率的 `g.share` 不受这个宏控制。把该宏改成0不能称为“去掉自适应层级共享”。

回调顺序：

- overflow：`update → release → pruneSpills → record`。
- miss：`update(当前缺失分区) → release(该分区字节数) → pruneSpills → LOAD → record`。
- periodic：激活后先 `update`；若下一条是合法 PROBE、目标在 PROBE 阶段且位于磁盘、大小不超过容量，则检查 cycle。仅在空闲空间已足够，或等大小完整循环假设成立时，才 `release → pruneSpills → LOAD → record`。普通需逐出情形会等待随后 miss，以保留那时能看到的再下一条操作（823—847行）。

## 3. 可观察信息：没有完整访问轨迹

官方 `SystemState` 提供内存量、K×P 分区大小/驻留状态/阶段、读写带宽、累计 hit/miss、I/O 字节、以及仅下一条 `next_op`（框架39—49行）。真实计分 `miss_penalty` 在引擎内部，未进入 SystemState；源中100微秒是固定代理，不能说“读取了真实惩罚”或“适配任意真实惩罚”。

框架只在 INSERT 溢出、PROBE 缺失、每 B 个 INSERT/PROBE 的周期处调用调度器；SWITCH 不触发周期；单个普通命中不回调。缺失先增加 miss_count 再回调。`getSystemState` 在计时闭包内部复制全体 operators，因此记录的 D 包含 O(N) 状态构造，以及回调本身，但不含随后 executeActions 的整段执行（框架640—688、718—785行）。

R81 的时钟 `q=hit_count+miss_count` 是累计 PROBE 序号，不是墙钟时间，也不是 INSERT/SWITCH 总行序号。`sampleNext` 只采样回调暴露的下一条 PROBE；当前缺失分区只进入 `observe` 和 refault 事件，不自动作为 `sampleNext` 热度样本。相同 `q+1` 用 `next_sample_q_` 去重，miss/periodic 重复暴露同一条下一请求不会重复计数；真正连续重复 key 在不同序号上仍保留。`observe` 同样按序号去重，只在连续可见序号之间更新后继与步长。周期回调在第一次 overflow/miss 激活前直接返回。

因此“热度”是可见下一 PROBE 样本的指数加权估计，并非完整 hit 序列的精确频率；hit_count 只提供累计量，无法补出未暴露命中的 key。风险区间也只从本调度器记录且后续状态确认的动作推导，不能宣称完整系统访问风险或精确未来概率。

## 4. 双时间尺度与异质性共享的准确公式

下式各量均按相同 PROBE 序号 q 惰性衰减到当前评估时刻。令 c_op,p 为慢分区质量，M_op=Σp c_op,p，F_op 为快算子质量；每个新可见下一 PROBE 给对应 c、M、F 加1。

快算子衰减 `F ← F·2^(-Δq/256)`；慢分区及算子统计衰减 `c,M ← c,M·2^(-Δq/2048)`。这两个数是半衰期。风险的512/128与coverage的256使用 `exp(-Δq/τ)`，是另一些统计量的时间常数，不能混为这两个半衰期。

慢统计同时维护 `S_op=Σp c_op,p²` 与样本权重平方和 `W2_op`；衰减时二者乘慢衰减因子的平方。有效样本量 `n_eff=M_op²/W2_op`。满足 P>1、M_op>8、n_eff>8、有限数等保护后：

```
v = max(0, [P*S_op/M_op² - 1 - (P-1)/n_eff] / [1-1/n_eff])
strength = v*(M_op-8)/(M_op+P)
heterogeneity = strength/(1+strength)
alpha_op = share = 0.75/(1+strength)
```

不足证据时 share=0.75。集中到少数分区、且证据充分时，strength 增大，share 减小，以减少向算子内均匀分布的收缩。这是代码中的启发式异质性估计与经验收缩，本文不主张其为无偏估计、理论最优收缩或首次原创。

设 b=64/N，b_op=64/K，Z_f=Σop F_op+64，则层级分区概率为：

```
operator_marginal(op) = (F_op+b_op)/Z_f
conditional(op,p) = [(1-alpha_op)*c_op,p + alpha_op*M_op/P + b]
                    / (M_op+b_op)
p_hier(op,p) = operator_marginal(op)*conditional(op,p)
```

有限有效状态下分区条件概率按算子归一，整体概率和为1。快速算子边际响应算子间负载变化，慢条件分布保留算子内部证据；share 用慢统计调节分区特异性与共享信息。`flat_probability=(c+b)/(ΣM+64)` 也被算出并缓存，但本模式的实际候选复用值使用 `64*p_hier`，不使用 flat 概率进行方案选择。`64*p_hier`可超过1，是固定尺度的优先级代理，不应解释为0到1的真实回访概率，也没有代码证据证明真实未来64步满足该统计假设。

此频率分支仅对 PROBE 阶段、且当前未判为 scan/cycle 的候选启用（675—681行）。其余候选走可见历史/风险回退，不能把全算法都描述成上述概率模型。

## 5. 回访风险、可见历史与结构回退

`record` 只记录 PROBE 阶段、非空且预计会改变驻留状态的动作意图。下次回调 `confirm` 检查大小未变化与真实驻留状态，才确认风险区间 begin/end。区间被后续缺失触发时记一次回访 event；主动 LOAD 结束区间不记event（383—413、564—569行）。这避免将未执行或状态不吻合的意图直接当作成功逐出。

分区风险 τ=512，算子聚合风险 τ=128。对曝光量 E、事件数 R、开始数 S 和活动区间数 a，间隔 Δ 的更新是：

```
f=exp(-Δ/τ)
E ← E*f + a*τ*(1-f); R ← R*f; S ← S*f
mean_time=(E+64)/(R+1)
risk_reuse=64/(64+mean_time)
```

若分区尚无有效 start，使用可见历史值；若算子聚合有有效 start，则以 alpha=share 混合分区与算子风险。之后再以 observed_weight 混合风险与可见历史。`demandWeight` 根据周期可见下一 PROBE 的衰减覆盖代理选择0.25或1；达到0.75阈值时直接返回可见历史，风险分支被跳过。这是覆盖代理，不能解释成完整轨迹观测率的测量值。

可见历史复用值为 `min(1,h.count/16)/(1+(age+1)/64)`；h.count 每次可见访问之前乘 `256/(256+序号间隔)` 再加1，并非指数热度。连续同算子、非零相同步长达到条件时使用 `1-step_distance[delta]/P`，步长距离表按模P前进最多P次构建。

scan 判据为 `streak>=6 && stride>0 && observed_count*2>now`；它只改变符合特定当前算子条件的历史值，并使所有候选跳过频率分支。等大小 cycle 识别要求所有 N 个节点的后继至少连续置信3、所有算子处于PROBE、所有分区大小相等且正，以及从当前节点恰好N步回到起点。通过后优先沿最近记录反向寻找一个足够大的驻留 victim，排除当前目标与 next PROBE；找不到仍回到一般候选处理。这是已观察序列下的循环假设，不能写成知道未来的 oracle。

## 6. 成本密度、下一条保护、有限子集搜索

每个一般候选的密度：

```
density_i = reuse_i * (1/R + 1/W + 100/bytes_i)
```

其中R/W单位为字节/微秒；对应 `reuse_i*(bytes_i/R+bytes_i/W+100)` 的每字节代理代价。它兼顾未来读回、重写与固定缺失惩罚；不是官方完整计分的精确条件期望。当前要加载/写入的目标被排除；下一条 PROBE 目标在一般候选中加 `1e12`，这是强软保护，极端情况下仍可能被逐出，不能称绝对禁止。cycle 快路则直接跳过该目标。

一般候选按密度升序、同密度大分区优先。满足代码门槛时，只保留最前4个候选并枚举它们最多15个非空子集；对能满足释放容量的集合比较：

```
loss(S)=Σi∈S [density_i*bytes_i + 0.25*bytes_i/W]
```

命中可行子集立即返回。不是枚举所有N个候选的2^N子集，也不是全局最优的背包解。没有可行top4集合时，无probe证据走全排序贪心；有证据先测试单victim，再建堆逐个贪心释放。最后 `pruneSpills` 按既有顺序移除仍可满足容量的冗余spill，不重新全局优化。

## 7. 完整复杂度逐项审计

设 V≤N-1 为本次一般候选数，A 为本次返回动作数，A_prev 为上一回调待确认意图数。所有空间查询和向量索引按 O(1) 计；vector 连续push的总扩容成本按标准摊还保证计入。

| 部件 | 单次上界 | 不能省略的成本/条件 |
|---|---|---|
| update 维度初始化 | O(N+K)，固定尺寸以后无此项 | history/risk/next_mass/successor/confidence/recent 等assign；recent大小N+2；允许维度变化时每次变化均可能重置，不声称所有变化摊还O(1) |
| confirm | O(A_prev) | 遍历全部意图，advance/begin/end每项O(1)，末尾clear也是线性上界 |
| refreshSharing / advanceFast / sampleNext | 各O(1)+可能C_init | 不扫描P；square/mass/weight2使用增量统计；sampleNext只处理单个样本 |
| observe | O(1)通常，O(P)重建时 | successor/recent/history更新O(1)；新合格stride的assign(P)+P次循环；一次update最多两次observe，因此O(P)仍成立 |
| update 合计（初始化后） | O(A_prev+P+C_init)，常见O(A_prev+1) | 最多处理一个当前miss和一个next PROBE；无按隐藏gap逐点迭代的循环 |
| analyzeCycle | O(N)，版本没变或早退时O(1) | 可能扫描K×P状态再遍历N条后继；版本变化不能保证很稀少，不得宣称摊还O(1) |
| ensureProbabilities | cache有效时O(1)；首次构建O(K)+可能O(N)分配/清零 | 外层候选中虽然调用多次，每次release已失效且仅首次有效调用重建；循环K次refreshSharing，不是每个victim都重新O(K)；resize或tags/sign assign是O(N)；epoch溢出fill(N)；operator_scale resize O(K) |
| ensureProbability(id) | O(1)+可能C_init | 每epoch每id只计算一次，懒衰减用一个exp或查表，未遍历时间gap |
| propose cycle快路 | O(N)+analyzeCycle | recent_count≤N+2，可能逐项找不到；不能保证常数时间 |
| propose 一般候选构造 | O(N+K+C_init) | N个状态扫描；K个risk cache按需一次；概率缓存一次重建；每候选ensureProbability/风险O(1)，不存在N×K的重复重建 |
| top4子集 | O(V log4)+O(15×4)=O(V) | partial_sort至多4；15子集是常数，不是2^N |
| 无证据排序 | O(V log(V+1)) | 包括动作输出O(A) |
| 有证据单victim/堆回退 | O(V)或O(V+A log(V+1)) | min_element、make_heap线性；每个pop_heap对数；A≤N |
| release（活动mode2） | 等于一次propose加O(1) | mode3的第二次propose/chooseAlternative不可计为实际执行，也不可当贡献 |
| pruneSpills / record | 各O(A) | 两次扫描/压缩erase尾部；记录意图不会遍历系统全状态 |
| 完整overflow/miss/执行预取的periodic | O(N log(N+1)+P+A_prev+C_init) | 已合入上面所有项；固定尺寸且A_prev≤N、P≤N后O(N log(N+1)+C_init) |
| 不执行release的periodic | O(A_prev+P+N_check+C_init) | 失活时调度器自身O(1)；激活后包含update；N_check为可能触发的cycle检查，最大N |

`ensureProbabilities` 的 O(K) 循环出现在候选循环的函数调用内，但 `probability_cache_valid_` 在首次调用后为true，后续调用是常数返回；`refaultReuse` 的算子prior也由 cached_valid_ 每次propose去重。以上两处是为何完整回调没有隐藏 O(NK) 的关键。`step_distance` 的P相关循环与cycle扫描不应遗漏，但P≤N，不改变上述最坏阶。

动作数证明：propose 每个候选最多一次，且排除当前目标，故spill≤N-1；cycle最多一个spill；最多再追加一个目标LOAD；prune只减不增，record只为这些动作生成意图。因此A≤N，且每次update先confirm并清空旧意图，然后本回调才record，A_prev≤N，不会无限累积。这一界依赖官方每回调执行其动作的协议；若外部调用方重复调用record则不适用。

常态与摊还：固定维度、缓存数组已就位、无结构重建、单victim或top4命中时，需释放空间的回调通常 O(N+K)=O(N)，而非O(1)。cycle路径在很靠近recent头就找到候选且版本不变时可短至O(1)，但最坏O(N)。跨T回调只能安全给出 `O(T*N log(N+1)+C_table)` 的一般上界；若每次只走线性分支则为 `O(T*N+C_table)`。没有证明结构重建次数、全排序/大量heap-pop次数稀少，所以不能把所有输入上的均摊复杂度降为O(N)或O(1)。vector扩容和固定查表初始化的摊还，不消除合法输入可能反复触发的逐项扫描。

固定表内存：r74与r75op各1025个double，fastDecay与probabilityDecay各8193个double，总计18,436个double，147,488字节（不计静态对象标记及对齐）；每张表首次真实调用才初始化。它们按固定常数视为 O(1)，但在实现报告中单列可避免隐瞒初始化耗时。表外所有按分区/算子的向量、候选、意图和返回动作均为O(N)；若允许尺寸先大后小且不释放capacity，实际保留空间应按历史N_max描述。官方固定K/P情形为O(N)。

框架额外成本：每次被计时回调前构造SystemState含O(N)复制，临时快照O(N)空间；executeActions另需O(A)但在D计时外。两者不提高回调最坏阶。代码使用CPU标准库/基本数值运算，未见GPU、线程、训练、文件读取、外部推理或C++17依赖；未编译故这里只是源码层面的C++14兼容审阅；另外已读取上述已有命名工程的C++14编译及ELF等价记录，不将其冒充本审计的新运行。

## 8. 七方向消融的可分离性审阅

以下建议已同步实验工程agent。已读取[消融source_manifest.json](https://github.com/cyanneko/HuaweiHackathon/blob/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_ablation_20261031/original/source_manifest.json)、生成器与七个diff，并独立确认全部9方法的源/TU哈希，以及Full/七变体相对命名源的准确文本修改。新版生成器已保留Full原始字节，Full与最终命名源SHA完全相同（2e168451...）；七个变体的语义补丁未改变。这里只确认文本身份和静态路径，不冒充行为有效性运行；实际实验必须冻结补丁和身份再归因。本审计未运行它们。

| 方向 | 可审阅的单独干预 | 必须注明的混杂/残留 |
|---|---|---|
| 去算子快热度差异 | 仅把operator_marginal固定为1/K，保留慢条件分母、先验、share与所有观测 | 测试快算子边际相对均匀边际；不是移除全部算子统计或共享；若保留快统计维护，不能把D解释为完全不维护快统计的成本 |
| 自适应共享→固定共享 | refreshSharing继续算统计，但最终share统一固定0.75；主hier与风险分支都消费这个share | 测试“自适应相对固定0.75”，不是“完全无共享”；只改R79宏无效隔离主hier |
| 统一热度时标 | 快算子半衰期256→2048，慢条件分布保持2048 | 仅统一快边际与慢条件热度；risk的512/128、coverage256、历史统计不变；可视为响应速度干预，不能外推全部时间参数优劣 |
| 去预取动作 | periodic保留update/coverage/sampleNext/observe，只禁止其返回LOAD/相关释放动作 | 后续hit/miss与回调序列会自然改变，这是策略的闭环效果；若连周期update也删，会混杂观测信息损失 |
| 去下一条保护 | 同时移除cycle快路的next skip和一般候选的+1e12 | 保留next_op采样、预取与当前目标排除；否则把“保护”混成“移除前瞻信息” |
| 去I/O成本权重 | 若定义统一单位miss：density=reuse/bytes，top4 loss=Σdensity*bytes；移除额外0.25*bytes/W | 仍保留每字节资源密度与容量约束；不能叫去分区大小；同时保留top4额外写成本会导致权重未完全消除。该变体改变风险代理的单位，需按定义命名；仍保留无PROBE证据时`R>=W`决定是否启用top4的门槛，不能说移除全部带宽信息 |
| 去scan/cycle决策 | 保留observe/步长/后继统计；强制scan=false且uniform_cycle=false，让一般频率/风险路径接管 | 测试结构决策增益，不能把其D差值当作完全不维护结构统计的运行时间节省；实物补丁已把唯一可能置true的赋值改false，构造/重置/函数开头也全false，故缓存/早退不会留下true |

机制之间共享概率、驻留状态与回调可见性；一次改一个方向也不意味着效果可加，组合交互不能由七个单因素差值相加推断。尤其预取会改变未来miss回调与可见样本，属于在线闭环，不能假设两策略看到完全相同样本。

## 9. 可直接采用的说明文本与证据边界

“R81在官方回调提供的状态与单步next_op信息内，使用快算子边际和慢分区条件热度，按算子内异质性调节共享强度；在访问稀疏或结构化模式下保留回访风险、扫描与循环回退。逐出依据每字节代理损失，并保护紧接着的PROBE；仅枚举密度前四候选的至多十五个子集，再以贪心及冗余动作删除满足容量。周期预取限定于有空闲空间或已识别等大小循环的情形，以免过早失去下一次缺失回调提供的前瞻信息。完整单回调最坏O(KP log(KP+1))，额外空间O(KP)，固定查表初始化另计常数成本。”

上述是代码实现机制，不是首次原创、理论最优或因果增益的证明。消融只能在冻结用例/基线/次数/评价器下支持对应差值，需同时报告IO、miss与D、负收益用例；模拟IO加惩罚不等于真实磁盘端到端加速。依据本轮用户提供截图的展示要求，工程上本地自造数据的机制对照不能替代组织方用例上的展示；创新加分是否成立由评审决定，不能由本地分数或此审计预先保证。本文未联网重解释或扩展截图规则。

发布说明：本页仅将本地材料入口替换为固定仓库链接，其余静态分析沿用已有审计；[原审计公开副本](https://github.com/cyanneko/HuaweiHackathon/blob/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports/r81_ablation_20261031/audit/algorithm_and_complexity.md)与[消融结论](R81_ABLATION_20261031.md)分别保留。行号沿用ef1可读基准，不冒称最终命名版同一行号。未重编译、未重跑或修改算法。
