# R82 reserved DEV 元数据核验

固定 datasets 提交 `f4a7fcf6e957afde7ffce0a4a7d61253cd8777f9`，新增 `experiments/r82_reserved_dev_150k_20261030`。final、dyna、balanced、inde 与 corner_case 整树均未变化；本轮不接入新输入或评测。

新增 12 条 dev，各 150,000 总操作，共 1,800,000 操作、36,559,012 字节；没有新 train 或 eval。12 个文件来自 6 个 seed（202610310301–306），每个 seed 的 none/hot 两个版本只有 `rare` 参数不同，不能当作 12 个独立 seed。另 38 条训练输入均为引用，其原始 SHA 集合与 R81 的旧 26 条加新 12 条完全一致。

这里的 none 不等同于均匀 IID。已读六条 none 元数据均无指定 rare operator/partition、target_mass=0；其他参数仍包括 slow/fast/burst 算子模式、slow 分区模式及变化速度 0.0025。因此它表示没有额外指定的 rare 标记；本轮没有重新核验生成器的完整概率公式。

数据 manifest 声明 `policy_evaluation_runs=0`；12/12 条目均为 `policy_evaluated=false`、`training_allowed=false`、`reserved=true`。生成审核摘要也记录 scheduler_runs=0、policy_results_read=false。源码监测 agent 在固定 source 提交 `b1246ae64a006c679e57789766dc401da2a9ecb9` 核对报告、advance 和 failure_report：selected 为空、reserved_dev_results_consulted=false、dev12_policy_runs=0，归档 evaluation 只有 train 子树。这些相互一致的发布记录支持“已生成、保留、未报告策略使用”，不能证明仓库外从未执行，也不能单凭目录名称判定未曝光。

已核对 inputs/manifest 的逐例身份、参数范围、声明输入/元数据 SHA、清理路径后的来源清单和生成审核绑定。来源原始 manifest 声明 SHA 为 `9e5dea66e940148def5394da3a4f9e892fc16ebc92534108083b06fc75d047f8`；发布副本清理了路径，实际 SHA 为 `7905f50a3e3d3e84c93da6eed15bf39614973c886dddf1695f6ca7b432d9473d`，两者不能混写为同一文件字节。

新 12 条 raw SHA 与引用 train38、已曝光 R81 dev6 的交集均为 0；6 个 seed 与已核的 R81 新 train6 谱系、dev6 均不重合。旧 26 条引用没有提供本次可直接比对的 seed，紧凑身份表也没有 operation/partition 流指纹，此范围保持 unknown。精确不重复不代表语义独立。

发布者审核声明 12 条完整输入合法、最大分区/M=0.49570058286190033；本监测只验证证据绑定，没有重放输入。新 12 个输入 Git 对象在本地均缺失，未下载或读取原始输入、逐例 sidecar、生成轨迹和方法数值成绩。AI 暂停与既有评测锁保持不变。

冻结证据：[元数据报告](R82_RESERVED_DEV_METADATA_f4a7fcf6e957.json)，SHA-256 `2e854fb187336f571fbff030015ac2bcfcfd24adaf39ba1d9256d5e345f9a7bd`；[核验脚本](audit_r82_metadata.py)。源码交叉证据的具体路径、SHA 和证据来源范围均记在 JSON 中。
