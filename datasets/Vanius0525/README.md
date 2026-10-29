# Vanius0525 自造工作负载 v0.1.0

train包含dev64、train96、val32，都是开发/拟合来源，不能作为盲测。eval包含holdout64、OOD64、第三轮fresh32、第三轮OOD32和17个合法边界诊断，共209例。名称增加cohort前缀，输入字节未修改。生成种子、参数、SHA256、操作流分组及corner分类见相邻meta与manifest。

全部eval现已曝光，仅用于可复现回归，不宣称代表官方隐藏分布。离线模型没有用eval拟合，但后续已查看结果。manifest明确记录跨split重复操作组和evaluation_eligible；不得把不合格组算作无泄漏外推证据。

内部选型按成员等权，每成员常规80%、corner20%，组内先按相同操作流去重；此权重不是题面官方规则。corner仅17例明确构造的边界/精确oracle诊断，正常热点、扫描、倾斜和OOD不自动算极端。所有例都保留，风险另报最差成本比，不用低权重掩盖非法动作。

生成器为generators/generate.py与generate_ood.py；边界构造来源source/Vanius0525分支src/Vanius0525/level1/check_edges.py（提交aaa92a0）。完整输入可直接复现，不需要框架或其他成员算法。

发布校验发现旧end_insert例缺少必须的SWITCH；原字节保留于diagnostics，不属于合法eval，也不参与内部性能评分。其他401例通过公共校验。
