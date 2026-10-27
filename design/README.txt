交付说明 | Hash Join Spill-to-Disk 动态调度设计

2026年10月26日最新入口（优先于下方历史报告）：
1. topic20_updated_solution_20261026.pdf：新版题面核对、四轮训练/迭代、g++真实参考引擎结果，共12页。
2. MySpillScheduler.cpp：学习冲分版；21节点模型已内嵌，只有标准库，官方无参数构造可用。
3. MySpillScheduler_balanced.cpp：控制尾部退化的平衡候选。
   两个文件都定义MySpillScheduler，选择一个提交，不要同时编译。
4. CURRENT_SOLUTION.txt 与 iteration_20261026/README.txt：文件索引与复现说明。
新版Score必须包括Total_Decision_Time，评分公式已变；以下旧报告的百分比不能直接作为新版结论。
最终608个新验证输入由实际g++ C++14公开参考引擎运行，每程序三次；607例BASE为正。
GNU主结果：学习版几何平均代价下降29.33%，最坏19712.42倍；平衡版下降25.10%，最坏1.741倍。
以上均非官方隐藏数据成绩，不构成全局最优或任意输入不退化保证。

2026年10月18日历史复测：
topic20_retest_report.pdf 为最新10页报告；以其结论修正此前200组固定种子的性能判断。
实际编译并运行了C++头文件，共1309个输入、21497848条输入操作、10460次策略回放。
包含20类负载、128组极端参数组合、307个小型精确模型检查、4个确定性回归、3个各500万操作输入。
主批次目录：stress20/run_20261018_183734_1b7713；完整索引与复现方法见stress20/README.txt。
旧版主集几何平均相对代价0.6782，但有218/963个正分样例退化；确定性输入复现5000.5倍退化。
新增PrefixScheduler.hpp是保守底座，本轮未观察退化，主集平均收益约0.15%；并非全输入不退化定理。
CostAwareSchedulerV2.hpp包含惰性衰减、空间搭车预取、硬保护及激进双目标等消融选项。
可行输入没有意外失败；最终分区>M的一个输入按预期失败，已单列。未取得官方隐藏数据或官方分数。

1. design_report.pdf：完整中文设计说明。包含题面梳理、歧义、代价模型、算法、接口、正确性、复杂度、创新点、消融验证、实施路线及22张截图索引。
2. CostAwareScheduler.hpp：参考 C++ 调度器。放在题目框架的 SpillScheduler 定义之后；以 std::make_unique<CostAwareScheduler>(miss_penalty) 替换朴素调度器实例。
3. verify_design.py：无第三方依赖的可执行算法模型；运行 python design/verify_design.py 可重新生成验证结果。
4. validation_results.json：固定种子的200组合成工作负载、样例行动轨迹和边界验证结果。
5. sample_corrected.txt：修正题目样例 N=11 的输入（原截图 N=10 会少执行最后一条 PROBE）。
6. build_report.py：PDF 的可维护生成源，需要 reportlab。运行 python design/build_report.py 重建说明书。
7. screenshot_inventory.csv：全部22张原始截图的阅读索引。

新增研究成果：
8. innovation_report.pdf：四篇核验文献、五个针对本题的新方案、正确性边界、构造例与消融计划。
9. innovation_checks.py / innovation_checks.json：相邻双Probe、BUILD写费守恒、空闲预取及等待信息反例的可复现检查。
10. build_innovation_report.py：新增PDF的生成源，需要reportlab。

新增方案O1/O2/O5做了构造性模型检查；O3/O4仍为设计提案。没有新增方案的完整C++实现或官方性能成绩。旧版200组合成结果仅对应旧实现，不能归给新增方案。

2026年10月14日新增全赛事选题分析：
11. topic_selection_report.pdf：34道赛题逐项判断、优先建议、公式推导、已验证结果和全部官方链接。
12. topic_selection.json：34题结构化结论与选题优先级。
13. research/selection_proof_checks.py / selection_proof_results.json：第15、13、16、27题的可复现检查；无第三方依赖。
14. research/topic_01至topic_34：公开题面阅读副本；figures内保存用于识别图片题面和公式的素材。该目录属于研究资料。

全赛事分析未取得官方隐藏数据或实际比赛分数。公开样例最优、局部证书和等价加速属于已验证范围；不能宣称完整提交已获90或100分。

完成范围：设计说明、接口兼容参考实现、可运行验证模型，以及2026年10月18日新增的实际C++编译与扩展复测。此前报告中的“C++尚未编译”为历史状态；合成数据成绩仍不是比赛成绩。

关键兼容事项：参考引擎在 INSERT 回调后无条件增加内存，因此禁止选择当前 INSERT 分区落盘；需要加载的分区必须不大于 M；标准接口不能观察每次命中，miss-pressure 只是受删失的观测信号。上述限制在PDF中详细解释。
