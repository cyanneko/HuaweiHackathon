# R70 VanBest 强在线专家真实轨迹

冻结源码 SHA256：`2cd6440fb6e78a406a9abac1cab642a98ec94bd07f46f2e55f641d04a23ae1db`。

24 个新训练用例全部完成原样 VanBest 官方运行与独立参考动作回放，包含完整回调、内存使用、字节账、公开 next_op、IO/hit/miss 和 EOF 校验。官方引擎后缀只替换调度器工厂；外部装饰器记录动作，不修改调度器及引擎物理规则。不属于正式 D 测量；也没有输出全分区逐回调状态。

## 产物

- `manifest.json`：24 例报告、每例原始输入 SHA、程序/框架 SHA、witness/anchor SHA 和实际代价。
- `runs/<case>/witness.json`：`vanbest-full-actions-v1`，每回调含 raw/stage/kind/actions；P 的真实预取动作完整保留。**不能交给旧 core.rollout 的空 P witness 接口。**
- `runs/<case>/anchors.json`：每例 24 个 O/M 回调，确定性 reservoir 采样，共 576 个。`snapshot` 可由 `core.State.from_snapshot(case, row['snapshot'])` 恢复，包含完整物理状态和独立因果观察器历史，随后可生成在线候选并计算同状态后缀代价。`expert_actions` 是真实 VanBest 行为，未保证落在小网络合法候选池内。

## 真实周期动作与历史定义

本批 168 次周期回调中，3 次非空、3 次预取：`train_skewed_16` 两次，`train_uniform_03` 一次，其余 22 例均无非空周期动作。若当前训练接口只接受原 R65 历史契约，可先消费另外 22 例的 528 个 anchor；不得把这两例的 P 动作删除后伪装成同一状态。

观察器为 `r65-causal-with-executed-periodic-intents-v1`，**不是 VanBest 私有 history**。每次合法 O/M/P 回调通过原 `History.observe` 观察当前公开状态；实际执行的 SPILL/LOAD 通过 `History.record` 记录动作意图。P 的 LOAD 使用与 miss LOAD 一样的加载意图/后续 refault 确认，不增加 miss_count。不存在逐命中额外回调或隐藏未来输入。对于没有非空 P 的 22 例，此扩展与原 R65 因果观察器行为一致。

## 验证和故障记录

3 个单测覆盖 P 免费空间预取、P 驱逐后预取、P OOM 拒绝，全部通过。编译 5.71 秒。首次 native 正常结束，但 WSL 输出 UTF-16 localhost 警告前缀，默认 GBK 读取失败；原 stdout/trace 保留 `first_decode_failure/`，随后使用与 R69 相同的 UTF-8 replacement 解码和明确 trace 标记重新核验。算法、输入和引擎未变。

后续 23 例连同首次成功结果复用的整批运行外层 8.16 秒，未超 60 秒预算；非正式执行，不用于比较调度耗时。
