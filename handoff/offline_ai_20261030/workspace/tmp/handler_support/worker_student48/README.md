# 学生轨迹46状态：配对教师标签交接

冻结学生在12个train输入上取样；实际46个新起点，train_skewed_15缺2个O起点，缺格保留。没有读取新增dyna holdout。原370标签及既有离线实验保持不变。

| 项目 | 结果 |
|---|---:|
| 共同完整起点 | 46/46 |
| 完整动作×后续策略分支 | 1152/1152 |
| 选定完整输入路径官方回放 | 91/91 |
| 最优首动作变化 | 4 |
| 最优集合变化 | 5 |
| 归一化target变化 | 34/224 |
| 严格候选pair反转 | 15 |
| 非零公共offset行 | 5 |
| 每臂保留全cost平局行 | 4 |

执行墙时 151.0672 秒，统一上限180秒。未记录独立进程CPU秒，不是正式D。没有换样、续跑、GPU训练或框架改动。

## 标签接口与三臂

- fixed_labels.jsonl：同一新起点与候选，使用该case原teacher_method完成整个suffix。
- portfolio_labels.jsonl：同一批、同序、同pool/x/tie的46行，每个动作取其适用H中一条完整suffix的最小成本。
- 两份cost均为当前动作加剩余suffix的真实整数增量G/write/read/miss；target先整数做差，再按本状态maxgap归一。当前miss不重复计罚。
- 全cost平局行保留scale0并在训练中零权；未完成矩阵不会只放进fixed臂。
- A只用原370，须同seed/200epoch精确复现旧模型；B为原370+新fixed；C为原370+新portfolio。原24case各自总权相等，B/C新增行严格配对。

## 首动作变化

| 新起点 | fixed选择 → portfolio选择 | 旧首动作在portfolio下的额外后缀代价 | 相对portfolio最低suffix |
|---|---|---:|---:|
| hotset07/M raw3834 | 47→24 改为 36→24 | 2214.069 模拟us | 0.866070% |
| uniform03/O raw516 | 1 改为 44（旧best有三动作tie） | 1968.152 模拟us | 0.006451% |
| uniform05/O raw256 | 23 改为 14 | 8673.478 模拟us | 0.007069% |
| uniform05/M raw4787 | 19→12 改为 62→12 | 5694.555 模拟us | 0.012357% |

另有uniform03/M raw6511最优集合扩张但选中动作不变、regret为0。公共offset行只表示所有动作的共同continuation改善，不算新的相对偏好。上述数值不是学生闭环收益，也不能把重叠suffix差相加为轨迹加速。

## 质量门与验证边界

独立保存产物审计通过：1152条精确整数账、1335次prefix/suffix/native文件哈希、B/C同序身份及原FP32特征/动作/tie。全部24个唯一最佳集合变化fixed/portfolio端点和38个唯一严格反转端点均有native验证（集合间重合）。

同特征异成本组：fixed 0，portfolio 0。这类确定性特征冲突不能靠增大网络消除；训练仍按既定规则排除对应pair。

91/1152分支完成独立官方compact回放，其余1061分支仅reference合法完整执行/重放。没有逐回调跨引擎比较全部分区状态；every_branch_independently_official_replayed=false、full_partition_state_compared=false。

交付身份见training_handoff.json，最终质量门见artifact_audit.json；原始矩阵与全pair gap在diagnostic_rows.jsonl，全部分支witness在w/，独立native请求覆盖在native_queue.json。没有把有限H条件最小值称为Q*，网络效果需由独立三臂闭环实验判断。
