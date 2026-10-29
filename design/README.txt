第20题关键项目文件 | source/liunianwww | 2026-10-30

当前本地785例平均Score目标推荐：MySpillScheduler_tree.cpp。
单文件C++14，定义MySpillScheduler、无main，接入公开2026-10-26执行器。
8种互补专家，由4层小树按当前状态/历史逐次选择，只执行选中的专家。
所有设计和报告均在design目录，截图与批量原始输入不在源码分支。

编译并运行（Python 3、g++）：
  python design/tools/run.py --policy recommended --input <正式输入文件>
只编译：python design/tools/run.py --policy tree
policy：recommended/tree（本轮新树）、rule（原规则）、neural（原NN）、
baseline（官方Naive）、scan-fused、experimental、cross-feedback。
公开执行器仅替换调度器实例，不改变执行、容量或计时范围。
输出写design/build，不提交；同名MySpillScheduler实现一次只接入一个。

本轮最新完整测试：785例×3次，三成员209/48/528。
平均Score 67,222,897,889.92 us，比Naive下降29.0629%，比父树下降0.4480%。
树+专家完整决策耗时1532.47 us/例；含该耗时的Score已用于比较。
Vanius单集比父树退步约10.78%，不同取舍已完整保留，不声称各集一致改善。
本地已观察开发/回归数据，不推断官方未知分布成绩。

中文PDF：topic20_portfolio_iteration_report.pdf。
当前状态/哈希：portfolio_iter_20261029/published_checkpoint.json。
三人分别结果：member_eval_20261030/members_r3_members.json。
独立动作及SDK语义核查：member_eval_20261030/members_r3_action_verification.json。
训练、完整Score搜索、原始证据解包与复现：portfolio_iter_20261029/README.txt。
source-only程序快照和原字节测量包已提供；不包含生成输入或二进制。
文件列表与SHA256：project_manifest.json。

保留历史：topic20_neural_selector_report.pdf、topic20_merged_dataset_report.pdf、
topic20_holistic_iteration_report.pdf，以及neural_selector、dataset_integration_20261029。
历史NN/规则/568例结果均保留原集合、重复数与口径，不改写成785例测量。
