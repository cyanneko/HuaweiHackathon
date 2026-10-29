第20题关键项目文件 | source/liunianwww | 2026-10-30

当前本地平均完整Score目标推荐：MySpillScheduler_tree.cpp。
8专家，由最大5层小树动态选择；C++14、仅CPU、无外部推理库。
正式框架仅替换调度器，保持执行、容量和计时范围不变。

编译/运行：python design/tools/run.py --policy recommended --input <正式输入文件>
只编译：python design/tools/run.py --policy tree
policy还支持rule、neural、baseline、scan-fused、experimental、cross-feedback。
每次只接入一个同名MySpillScheduler实现，输出在design/build，禁止混编多个。

最新785例×3：平均Score 66,918,827,769.94 us，比Naive下降29.3837%。
三成员209/48/528，版本及完整分项见CURRENT_SOLUTION.txt。
目前按原始平均Score选推荐。未封顶成员sum与真实成本同时展示，不宣称各集都优于所有版本。
当前方案相对108，Vanius0525、cyanneko的原始平均Score略退步；选择目标是785例raw平均Score，并非每个成员分别最优；原NN在部分成员原始均值上仍更好。

中文PDF：topic20_portfolio_iteration_report.pdf（实现、创新、文献、局部证明、实测与限制）。
当前冻结状态：portfolio_iter_20261029/published_checkpoint.json。
训练、Score搜索与解包复现：portfolio_iter_20261029/README.txt。
当前测量接入方式：three independently compiled programs; argv contains input path only；源码、二进制身份及重复数以checkpoint绑定记录为准。
离线下界工具：offline_bounds_20261030；读取未来/p/B仅为评测，绝不能接入在线调度。
文件列表与SHA256：project_manifest.json。

仍保留旧568例、NN和规则历史报告，各自日期/集合/重复数不迁移为本轮成绩。
原始截图、批量输入、工作树、二进制和临时预览不提交。
完整后缀标签已采集，3854个状态、覆盖783份train、840份train inventory；已用于当前类别节点更新，并完成完整Score回归及独立部署复测。
当前类别更新mode 113已采用：节点22左侧ID集合{0,1,2}→{0,1,3}，mask=11；仍为深度5，已完成785例×3独立部署。
完整后缀全树重拟合已生成8候选；118/121在840份train优胜，但members_r9同批785例相对108的平均Score118上升1.0930%、121上升3.6131%，未采用。
类别113在members_r9同批平均Score为66,918,828,195.97 us，相对108下降0.1274%；最终交付成绩另以独立部署checkpoint为准。
周期admission公共层已实现并启用，factor=4，保持8专家。
admission：4档候选已完成840份train评分；785例×3次已测mode 98/99/108；109无本批成员结果。
admission研究配对轮相对mode 92的平均Score：98上升0.065618%，99上升0.007852%，108下降0.000003947%；微小收益不等于隐藏测试保证。
admission为公共提前处置层，非第9类专家；局部证书截止下条INSERT写入结束、其后periodic动作之前。
后续增长、Probe与回调D可能改变收益，不宣称完整Score的理论保证。
训练labeltimer仅为离线成本代理，最终性能以正式框架回调计时与完整Score为准。
