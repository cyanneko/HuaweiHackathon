# R82：组合搜索与立即写盘权重的独立消融

状态：设计审查，无实现、编译或 native。当前R81测评进行中，不依据其成绩选参数。仅建议两个可归因候选，不做组合网格。

父：冻结 `tmp/r80_lazy_transfer/R80_next_hier_fast100/MySpillScheduler.cpp`，SHA256 `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`。不用R81快算子热度，不引入paired。

## 现有目标和局限

父 `propose` 407–424行按priority取top4，枚举15个非空子集；其集合损失为

`L_lambda(A)=Σ_(i∈A) [r_i*b_i + lambda*b_i/W]`，当前lambda=.25。

其中 `r_i=h_i*(1/R+1/W+100/b_i)`，还保留next保护的大常数；普通PROBE的 `h_i=64*p_i`。因此 `r_i*b_i` 是预计重复访问的读、未来写和100us代理之和，单位与立即写盘项一致。不能把单分区density `r_i` 或size直接与整个集合的L比较。

top4无可行子集后，父回退到原min/heap顺序并累计足够字节。这个回退仍可能比任意单分区便宜。callback随后按现有 `pruneSpills` 移除可省动作，最后记录真实action；必须用这个裁剪后实际方案作比较。

## 候选A：R82_singlefit025（建议名称）

只扩充候选集合，不改热度、损失或原baseline方案构造。

1. 保留原propose的一次调用、一次候选统计遍历。新增只在普通PROBE搜索生效的轻量状态：每合法候选的已算loss和全体resident中足够释放need的最低loss单分区。
2. 该单分区必须为正size、in_memory、不是callback目标，且不是合法next PROBE目标；不引入读取隐藏状态。相同最低loss的额外候选按(op,pid)稳定打破平局。
3. 原top4/heap等搜索照常完成；不得因存在single-fit而提前跳过原greedy。原base先执行既有prune，再从缓存求 `L_.25(base)`；比较 `L_.25(single)`。
4. 只有single严格更低才替换。相等保留原base及其动作顺序，不设置新“最小收益阈值”。候选空/无single/need<=0时原流程不变。
5. 在release内部提前prune不会改变原callback最终方案：原prune是幂等的，第二次callback prune应删除0动作。也可把比较安排在原callback prune之后，但三个callback重复逻辑较多，风险更高。
6. 原 `update/confirm/observe/refault` 只走原路径。不得重跑第二次propose来计算base损失，不从risk再次获取priority；使用第一次候选循环已经算出的值。所有record仍仅在原callback结束处一次执行，不记录被拒绝single/base。

建议增强仅在全部算子PROBE且非scan、非uniform_cycle的普通路径启用。BUILD、混合阶段及两类快路原样回退，next软/硬保护保持原语义：新single候选不主动挑next；若没有合法新single，允许原base处理原本的资源极限情形，不改变其行为。

成本：在已有resident循环中维护一个best；每个候选增加若干标量运算和已算loss写入。可复用按ID数组、尺寸首次分配，不必每release清KP：仅查询本次base中一定已赋值的ID；快路返回时必须清“本轮增强有效”标志，避免旧cache泄漏。最终比较O(base动作数)，不增加排序、不枚举更多子集。需要明确首次分配和全部callback工作计入D。

## 候选B：R82_write1（建议名称）

保持原top4范围和回退搜索，不加入候选A，只把普通PROBE、非scan/cycle且全PROBE场景下的subset loss立即写盘系数由.25改1。其他场景继续.25，避免把BUILD/scan回退也纳入这一轮差异。

该候选只改变top4中的组合比较；priority排序、top4 shortlist及无可行子集时的heap回退不变。因此它不是全调度器“按真实成本最优化”，其作用范围必须如实描述。若Root希望全局严格单常数修改，应另行明确放开BUILD/scan行为范围；不在实现时自行扩大。

物理依据：官方TU 643–647行对每个实际SPILL直接累计 `b/W`，没有.25折扣。读取LOAD计 `b/R`，最后Total_Score另加miss真实罚值和D；当前请求共同的LOAD在同状态spill集合比较中抵消。

但.25来源在当前文件只表现为启发式系数，未见推导。`h_i=64*p_i` 不是至少一次再访问的概率，未来写项可与实际驻留/重载耦合；100us不是隐藏真实罚值，预测窗口也有限。因此把.25改1有解释性，但不能断言原式错误或新式一定更优。此消融检验较强惩罚过量spill字节是否有益，不宣称完整未来成本校准。

## 定向例子与必要测试

以下使用测试可注入的Victim字段，W=1，r为已算priority，need=10；不要求公开流精确生成这些浮点值。

1. **A补足top4之外的更好single**：top4均为(b=6,r=0)，原选两个，L=.25*12=3。外部(b=10,r=.01)的L=.1+2.5=2.6，应选择外部single。各目标不与callback/next冲突。
2. **A不能抢掉更好的原greedy**：4个(b=1,r=0)、3个(b=2,r=.01)、1个(b=10,r=1)。top4不足10；原greedy前7个总字节10、L=1+3*.52=2.56，而single为12.5，必须保留原方案。
3. **A与prune后的base比较**：直接构造存在可省前缀动作的暂定方案。先运行原prune，用其剩余动作求loss；不能把被剪掉的动作成本算入base而诱发虚假改善。验证prune二次幂等。
4. **B立即写盘权重确会改变组合**：top4包含(b=20,r=0)与(b=10,r=.4)。lambda.25分别为5和6.5，父选20；lambda1分别为20和14，新版选10。其他top4候选设为不影响选择。无可行top4的例子仍走完全相同的原回退。
5. **保护与记账**：target不能新spill，next即使尺寸适合也不能成为新增single；BUILD/混合阶段/scan/cycle原动作相同；need<=0不新增动作；没有single保留base；等loss保留base；最终miss LOAD位置和容量合法。
6. **不重复统计**：一次真实miss只关闭一个episode，S/H/next样本不因比较额外更新；拒绝的新方案不进入intents，最终record恰为执行action列表。全程只一次propose。
7. **损失oracle**：新增single启用时，返回方案在相同已算r下的L_.25不高于裁剪后原方案（实数定义、数值容差用于测试）；这不是实际future cost必不升的保证。固定少量随机小pool穷举验证比较器即可，不以更多参数扫描代替真实评测。

## 建议执行边界

两候选都继承冻结R80，而非B继承A。A回答“补足全体single候选是否有用”，B回答“原top4组合对立即写盘折扣是否合适”；不同时改变两者。不扩cap6/8，不加入R81热度、不调100代理和horizon。先独立小测与CPU开销门，后续由Root统一同批含D测评；实际收益未知。
