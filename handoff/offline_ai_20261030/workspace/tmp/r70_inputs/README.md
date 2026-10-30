# R70 新种子数据

24 train / 8 dev / 8 holdout，按完整case划分。固定种子和压力在config.json。四类为均匀、热点、大小/访问倾斜、算子BUILD/PROBE交错。mixed不是不同访问分布组合，不能作此宣称。

沿用冻结生成器与严格输入审核；每个split单独执行run.py --split SPLIT --execute。三个split共40例、441120次操作已全部生成并审核；40个seed、原始SHA和模分区操作流SHA均唯一。

24个train的完整离线教师路径见邻接目录 `../r70/teacher_manifest.json`，已逐例官方回放验证；实际强在线专家路径见 `../r70_expert_rollin/manifest.json`。本目录保存原始输入，不将其与后续同状态候选代价标签混淆。18个静态train有下界证书，6个mixed明确不适用，见 `bounds/train.json`。

holdout不生成拟合标签；仅在模型选择冻结后进行一次正式在线评测。本数据与旧final_dataset、三成员公开套件分开，不变更既有评测版本或榜单。
