# Van paired100 → R79：三个低开销可移植差异

只读审查，未改算法/框架、未编译、未运行 native。引用为冻结本地源码行：

- Van：`round9/candidates/paired_penalty100.cpp`，SHA256 `3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15`，commit `28094bdec34ff7110d9f1614703d0b09d383d4a6`。
- R79：`tmp/r79_adaptive_operator/R79_adaptive/MySpillScheduler.cpp`，SHA256 `8eb171503ce6c30d8e99939dffef33b751dd96f7b276c1d4509c090d439d982d`。

建议按“proxy常数 → next频率排名 → 两方案实际代价差gate”分别冻结有限对照，先区分原因，不把Van总体优势归因于单一机制。以下不是已证明的收益，也不是立即实施授权。

## 1. 固定 miss penalty proxy：1 → 100

精确位置：Van第9行固定100；201、208–211行进入victim density；290、295行也进入paired future/known-next项。R79第318–321行采用文档下界1，随后342行加0.25倍当前写成本。

设b_i为字节、W/R为公开带宽、u_i为当前热度，排序密度为：

`d_i = u_i * (1/R + 1/W + lambda/b_i)`。

R79前4候选子集目标为 `sum_i(u_i*(b_i/R+b_i/W+lambda) + .25*b_i/W)`。把lambda从1固定改为100不增加状态或循环，不更改基础分区热度、算子共享、dense保护、候选数、排序复杂度或动作合法性。常数会相对加强小分区重访的固定miss成本，可能改变多victim与单victim取舍。

在线合法：lambda是全输入一致的预声明代理，不能读取真实隐藏penalty或按文件/家族选择。100不是官方penalty估计，不保证对penalty1或1000同样好。若paired比较也使用代理，应统一常数，避免排序用100而gate仍用1。最小反例测试是相同热度但不同b_i的排序/集合目标，以及改变不可见metadata不改变动作。

## 2. 把已存在的 next-only 样本用于分区排名

Van第35–58行：只采公开next PROBE，半衰期2048，q=hit+miss+1。miss后source2（332行）与periodic source1（339行）分别记来源，但同ordinal只给总样本加一次；当前miss不作为频率样本。其衰减每>=256 ordinal扫描所有分区，是分段近似衰减。`sample_squares_`实际是样本权重平方和W2，不是sum(c_i²)，用于有效样本数。

Van第59–60行对N=K*P个分区使用独立均匀伪计数：

`p_i=(c_i+64/N)/(S+64)`；PROBE且非scan时第203–207行采用 `u_i=64*p_i`。

R79第72–107行已有更精确的lazy next质量，但只用于算子内异质性，第308–317行排序热度仍来自history/refault/shared mix。静态热点下，将next统计用于对象区分是一个明确新增信息用途，不能等同于调大H。

低CPU移植方式：复用R79 next_mass，所有质量在同一统计ordinal t下读取。c_i(t)=stored_i*decay(t-last_i)，S(t)=各op存量统一衰减后的和；K<=8，每release先算一次全局S，候选循环只读一次本分区质量。必须保持t不倒退（已有next可能在实际q+1），不要错误地直接相加不同last的group mass。若要避免每候选exp，可复用小delta LUT；这是后续明确实现选择，不应同时搬入Van的全数组衰减与另一套样本计数。

全局归一化S只聚合原始next样本，不是算子热度或算子先验；不能用h_op去生成c_i。h_part原始refault估计保持独立。**64*p_i是期望次数，可大于1，R79的64/(64+mean_wait)是0..1有界proxy；二者尺度不同，不应不作说明地当相同概率直接混合。** 最干净的用途是产生一个frequency alternative，与原R79动作比较；若直接替换评分，要明确它同时改了目标尺度，而不是只改预测精度。

来源偏置仍在：next暴露由回调/驻留影响，source2并非全局随机采样。不能称无偏真实访问分布。Van还有一个容易漏掉的差异：339行在inactive检查之前采periodic，R79第401–402行在inactive时直接返回；迁移时不要无意改变早期历史/cycle初始化。若要补初始next样本，应单独明确授权，仅初始化/收集该统计。

必要测试：跨callback重复next只加一次、真实miss不加样；长期空窗与跨op质量统一时钟；sum p_i≈1；hot样本提升相应p_i；按统一向量衰减oracle核计数。已知next合法可用，但不能把未来除next以外的输入当特征。

## 3. 两个合法spill集合的 survivor-cost差比较

Van第266–312行：先提案A，再在需要释放、所有op已PROBE、非scan且非uniform cycle时提案B；两者先prune。不是扩大top-k搜索。对两方案共同evict的分区消项，定义 `sign_i=1[i∈B]-1[i∈A]`（280–282行）。留下来的集合是evict集合的补集，所以这是等价的survivor差比较。

令 `c_i=sign_i*(b_i/R+b_i/W+lambda)`。源码计算：

```
I = sum sign_i*b_i/W
    + sign_next*(b_next/R+lambda)          # next为已知PROBE时
mu = sum p_i*c_i
m2 = sum p_i*c_i*c_i
n_eff = S*S/W2
sd = 64*sqrt(max(0,m2-mu*mu)/(n_eff+1))
选择B仅当 I + 64*mu + 2*sd < 0
```

精确位置：291行当前写差；292–295行额外的已知next读/miss差；296–305行均值、二阶矩与保守gate；312行才swap。当前M目标的LOAD相同，所以不用重复加其成本。共同spill取消后只需评估对称差，能避免仅比较victim数量或仅比较总释放字节。

这是固定64请求窗口、代理penalty和IID式标准差构成的启发式，不是精确完整后缀，也不是统计保证。“未来读后还会写回”的系数同样是代理。若所有候选强保护next，该项常为0；仍应保留，不能把下一次真实请求遗漏。

移植到R79时：只调用一次update，先生成原R79 A和next-frequency B，两个planner不得写intent。只对最终选中的有序动作执行现有prune/record；不能先调用完整R79 callback记录A后又替换成B。全局phase/scan/cycle guard保留，当前BUILD/mixed行为不变。单独profile D，因为新增第二次候选生成常数开销真实计入D。

低开销实现可共用一次候选扫描、为每victim存两项density，再分别选前4/枚举最多15子集；比较使用稀疏对称差或复用容量数组，避免每callback额外分配全N sign向量。最坏仍O(KP log KP)，不能因此声称开销免费。若第一步只有proxy差，不需要双提案。

**源码细节须保留在归因说明：** Van第215–219行在dynamic_pool=false时按history `pool_priority`形成前4 shortlist，但229–230行子集loss仍统一读取`v.priority`（next-frequency）；因此其A不是“纯history目标”。如果移植改成两套各自目标，那是一个新候选，不是逐字复现Van。应由root明确选择。

第307行`if(false)`关闭了periodic-only source veto；第62行refreshCore在该文件无调用。不要搬入这些死路径或把它们列为现行策略收益来源；pmean/psecond虽被计算，当前不改变选择。另一个`return_risk_v1.hpp`是shadow observer，完全不是这里执行的paired100方案。

必要测试：A=B时不改动作；集合顺序不同但相同spill集合时不误报差；当前写差符号、next差、shared victim取消正确；门槛相等保留A；最终intent只对应真实B；无释放需求/BUILD/mixed/scan/cycle均保留原R79路线。没有性能执行或策略改动发生于本审查。
