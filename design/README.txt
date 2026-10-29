第20题关键项目文件 | source/liunianwww | 2026-10-30

当前本地平均完整Score目标推荐：MySpillScheduler_tree.cpp。
8专家，由最大5层小树动态选择；C++14、仅CPU、无外部推理库。
正式框架仅替换调度器，保持执行、容量和计时范围不变。

编译/运行：python design/tools/run.py --policy recommended --input <正式输入文件>
只编译：python design/tools/run.py --policy tree
policy还支持rule、neural、baseline、scan-fused、experimental、cross-feedback。
每次只接入一个同名MySpillScheduler实现，输出在design/build，禁止混编多个。

最新785例×3：平均Score 67,004,205,540.08 us，比Naive下降29.2936%。
三成员209/48/528，版本及完整分项见CURRENT_SOLUTION.txt。
目前按原始平均Score选推荐。未封顶成员sum与真实成本同时展示，不宣称各集都优于所有版本。

中文PDF：topic20_portfolio_iteration_report.pdf（实现、创新、文献、局部证明、实测与限制）。
当前冻结状态：portfolio_iter_20261029/published_checkpoint.json。
训练、Score搜索与解包复现：portfolio_iter_20261029/README.txt。
单文件部署源码包的引用已归一为相对路径；重编译三程序与计时二进制SHA逐字节相同。
离线下界工具：offline_bounds_20261030；读取未来/p/B仅为评测，绝不能接入在线调度。
文件列表与SHA256：project_manifest.json。

仍保留旧568例、NN和规则历史报告，各自日期/集合/重复数不迁移为本轮成绩。
原始截图、批量输入、工作树、二进制和临时预览不提交。
准备中的collect_full_horizon、categorical_transition、admission工具尚未产生本轮结果；
当前交付模型不包含这些未验证方案。
