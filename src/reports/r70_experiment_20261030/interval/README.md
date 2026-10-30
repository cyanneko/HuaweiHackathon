# R70 静态保留区间教师

这是新的离线可行解启发式，不是精确 OPT，也不是对 FOO/PFOO 的完整复现。

启发来源：[Berger 等，Practical Bounds on Optimal Caching with Variable Object Sizes, SIGMETRICS 2018](https://www.pdl.cmu.edu/PDL-FTP/associated/pomacs32-berger.pdf)。借鉴相邻两次访问间的保留区间表示；论文默认缓存的 miss 目标、允许旁路等建模细节不能直接套用比赛。本实现自行适配全分区必须驻留、SPILL 必须写、LOAD 必须读的约束。

## 实现

只接收整个输入首个 PROBE 之后再无 INSERT 的静态输入。对象 i 在相邻请求 t,j 之间留存，估计避免代价为 `b_i/W+b_i/R+penalty`；按收益除以字节与区间长度等启发式排序，贪心选区间。使用 range-min/range-add 树检查容量，约 O(N log N) 时间、O(N+S) 空间，不承诺近似比。

每个请求位置 q 先预留目标的整个大小 `b_target(q)`；另一个分区的保留区间只在内部 `t<q<j` 占容量。因而不会借用论文的 bypass 假设。实际调度仅在缺空间回调驱逐未受选中区间保护的分区，保留其它空余副本；BUILD 使用已有 cost-aware，periodic 返回空，miss 最后 LOAD 目标。提前丢弃非保护对象不是必要操作。

## 已完成验证

- 5 个测试：线段树与数组对照、互斥大分区、相邻同对象请求、逐时刻目标+区间容量及完整参考回放、静态假设拒绝。
- 4 小例 × 3 规则完整运行，所有路径持久化。hotset `8,505,697.904`（旧 `8,537,653.736`）；skewed `871,040,768.914`（旧 `872,157,740.986`）。这两条新改善路径已由官方 compact harness 完整回放通过，见 `verification.json`。
- beam_06 持平；uniform 新最好 `73,322,239.311`，差于旧 `72,739,702.995`。不替换旧最佳解。
- 26 万热点新 density 为 `368,064,510.923`，旧 `367,194,340.335` 更好；保留负结果。此条未再做官方回放，不当作已认证改善。
- 第一次官方验证因 WSL `E_ACCESSDENIED` 未启动，原始日志保留在 `verified/`；权限调整后成功结果在 `verified_retry/`，算法和输入未变。
- `run_medium.py` 首次因同名 run_pilot 导入优先级错误停止，改为显式 compact_harness 后成功；未改物理模型。

所有值是模拟 IO+miss penalty，不含 D。开发样本收益不能当作在线小网络收益。32 维网络数据/训练工作在独立目录进行。
