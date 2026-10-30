# R69 静态输入 IO 下界

只读输入，不运行策略、solver、模型或官方引擎。本轮只写脚本和待跑小单测，**未执行任何单测或大数据**；暂无 RED/GREEN 或性能实测声明。

接口：`from static_bounds import certify; report = certify(input_path)`。成功返回 `status=certified, certificate_valid=true`；不满足假设抛 `CertificateError`，没有下界证书。CLI：`python -B tmp/r69_root_bounds/static_bounds.py INPUT --output OUTPUT.json`；失败写 `status=rejected, certificate_valid=false`，退出 2，不保留同路径旧证书。成功退出 0。单遍逐行读取，四个窗口各只保存当前 distinct ID 集合；内存 `O(KP + 64+128+256+512)`，不存请求序列。输入 SHA 覆盖实际读到的全部字节，另记录脚本 SHA。

待 Master 空窗执行：`python -B -m unittest discover -s tmp/r69_root_bounds -p test_static_bounds.py -v`。七个小单测覆盖大分区投影、distinct/窗口末尾、MAX 不相加、精确大整数、零/半内存对象、后续增长拒绝、非法 phase/count/penalty/超大分区拒绝。

## 假设和证明

令 W/R 分别为写/读带宽，M 为容量。所有 INSERT 先于整个输入的首个 PROBE，因此此后每个分区大小 b_i 固定；每个 b_i≤M。目标完整分区必须在请求服务后驻留内存，每次 SPILL 写完整分区，每次 LOAD 读完整分区，不能免费丢弃 clean 副本。上述是本题物理模型前提；脚本能验证输入结构、增长位置、大小、phase/count、W/R>0 和 penalty≥0，不能从输入文件证明引擎实现，因此证书分别列 `assumptions_verified` 和 `model_assumptions`。允许任意时刻合法预取/驱逐，会放宽实际 callback 限制，故下界仍覆盖本题。

1. **大分区投影。** 只保留 b_i>M/2 的 PROBE。相邻投影请求若对象不同 a→b，两个对象不可能同时驻留。请求 a 服务后到请求 b 服务后这一段必有 a 的完整 SPILL，及 b 的完整 LOAD。预取 b 若早于 a 服务，就必须先腾出位置给 a，之后仍需再次 LOAD b，故不能逃避该区间的读量。相邻投影请求之间的时间段不重叠，逐次相异切换的 b_a 写量与 b_b 读量可以求和；相同对象不计，首个请求不强加初始加载。令其总和为 E_big、L_big，则下界为 E_big/W+L_big/R。

2. **固定互不重叠窗口。** 对 PROBE 序列从第 0 个请求开始，每 H 个请求为一窗，H∈{64,128,256,512}，末尾不足 H 的窗也纳入。窗口不同请求对象的总 bytes 为 B_j；窗口开始时至多 M bytes 已驻留。这些对象在本窗服务时均需完整驻留，所以本窗 LOAD bytes 至少 max(0,B_j−M)。允许预取没有影响：窗前预取计入开始驻留并受 M 限制；窗内预取计入本窗 LOAD。可以把边界定义为相邻请求之间同一时刻；无需假定窗口以空 cache 开始。对一个固定 H 的不重叠窗口求和得到实际全段读量 L≥L_H=Σ_j max(0,B_j−M)。

3. **静态字节守恒。** 从首个 PROBE 前到输入结束，resident bytes 的变化严格为 LOAD bytes 减 SPILL bytes，所以 E=L+R0−R1，其中 0≤R0,R1≤M。因此 E≥max(0,L−M)≥max(0,L_H−M)。结合读量，下界为 L_H/R+max(0,L_H−M)/W。其他算子的 SWITCH 不改变 bytes，不破坏此证明；此段之后若出现任何 INSERT，脚本直接拒证。BUILD 期间写量未计，是额外非负代价。

4. **组合与目标。** 上述读写量可能指向同一次 IO，跨 H 也重叠，所以只能取 MAX，不能相加。忽略非负 `penalty*misses` 安全。全部计算用精确 Python 整数，定义 `G=(IO+penalty*misses)*W*R`：big 的 `lower_G=E_big*R+L_big*W`；窗口的 `lower_G=L_H*W+max(0,L_H−M)*R`。`lower_bound_G` 为这五个值的 MAX，精确代价分母为 `objective_G_denominator=W*R`；不转换为 float，不声称是官方浮点逐项累加值或 D 的测量。该 IO 下界也是整个输入 IO+miss 目标的下界。

失败条件包括：首 PROBE 后 INSERT、分区总大小>M、负 penalty、非正带宽/内存、非法 key/op/阶段、缺少或重复 SWITCH、声明/实际计数不一致、多余操作或截断。此工具检查证书需要的结构与物理假设，**不代替官方数值范围校验器**；例如小内存诊断输入及巨大整数带宽单测可被接收，但不因此声称正式数据合法。无 PROBE 的合法结构输入给零下界。
