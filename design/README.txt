第20题关键项目文件 | source/liunianwww | 2026-10-30

当前本地平均完整Score目标推荐：MySpillScheduler_tree.cpp。
8专家，由最大5层小树动态选择；C++14、仅CPU、无外部推理库。
正式框架仅替换调度器，保持执行、容量和计时范围不变。

编译/运行：python design/tools/run.py --policy recommended --input <正式输入文件>
只编译：python design/tools/run.py --policy tree
policy还支持rule、neural、baseline、scan-fused、experimental、cross-feedback。
每次只接入一个同名MySpillScheduler实现，输出在design/build，禁止混编多个。

最新785例×3：平均Score 66,823,205,678.74 us，比Naive下降29.4846%。
三成员209/48/528，版本及完整分项见CURRENT_SOLUTION.txt。
目前按原始平均Score选推荐。未封顶成员sum与真实成本同时展示，不宣称各集都优于所有版本。
选择目标是785例raw平均Score，并非每个成员分别最优；原NN在部分成员原始均值上仍更好。

中文PDF：topic20_portfolio_iteration_report.pdf（实现、创新、文献、局部证明、实测与限制）。
当前冻结状态：portfolio_iter_20261029/published_checkpoint.json。
训练、Score搜索与解包复现：portfolio_iter_20261029/README.txt。
当前测量接入方式：three independently compiled programs; argv contains input path only；源码、二进制身份及重复数以checkpoint绑定记录为准。
当前checkpoint已确认独立程序部署复测完成。
离线下界工具：offline_bounds_20261030；读取未来/p/B仅为评测，绝不能接入在线调度。
文件列表与SHA256：project_manifest.json。

仍保留旧568例、NN和规则历史报告，各自日期/集合/重复数不迁移为本轮成绩。
原始截图、批量输入、工作树、二进制和临时预览不提交。
完整后缀标签已采集，3854个状态、覆盖783份train、840份train inventory；用于前轮类别节点更新，本轮继续沿用；当前部署状态另见checkpoint。
前轮类别113已验证采用：节点22左侧ID集合{0,1,2}→{0,1,3}，mask=11。本轮沿用31节点、深度5，仅扩展next目标保护比较，不重新训练类别树。
当前继承142的next_deficit_shift=0（按字段存在性判断，0也有效），树和8类专家不变；保留forced_cover及admission=2。
next目标q保护：d=max(0,qsize-(M-used+f1-sizep))，阈值qRead+max(1,floor(d/2^k)/W)。
只有新增接受区有两已知PROBE服务前缀IO证书；q可periodic预载，不能假设必miss。范围排除q服务后的periodic，不保证D、未知未来或全Score。
members_r12同批785例×3，相对父113平均完整Score：142下降0.13890%、143下降0.13656%、144下降0.10412%。额外收益不挪作历史r10/r11同层消融成绩。
当前checkpoint已确认独立接入复测完成。
正式固定expert1范围诊断见next_deficit_scope_verification.json；其前缀收益与追加未知访问后的反转均不等于当前在线树路由成绩。
当前额外启用exact_next_credit_shift=1（0也有效），保留142的旧缺口条件；树、8类专家和admission=2不变。
旧比较失败后，先检查(f2-f1)/W<=sizeq/R+floor(sizep/2^k)/W；可能通过时，扫描已计算的other，核对其每个牺牲分区都满足s(x)>M-sizep-sizeq。
合法且无重复的other由强制集合组成时，达到固定p、q共存需求的立即写量下界。原方案在q服务时若还保留p，必须已写出该集合且额外写读q；若p已不在，则至少额外写过sizep且读q。
新增接受区的局部IO证书截止q服务结束、q之后的periodic之前；原启发式区域、D、未知未来、全Score与浮点机器认证均不保证。额外只扫描other，不新增规划或全分区扫描。
members_r13同批785例×3，相对142完整平均Score：145上升0.02850%、146下降0.00400%、147下降0.00001%；研究程序D已计入，独立部署采用当前checkpoint数据。
完整train_g10最优145在回归反而退化；146按已观察开发回归结果选择，不能把该集合当作未见盲测。
同批r13仅3例动作改变（2例改善/1例退化，均liunianwww），782例物理相同；剔D平均净收益2,673,041.05 us，主要集中一例。Vanius/Cy微小差异仅D，不称普遍提升；来源exact_credit_result.json。
固定expert1的全量补偿正例及未知A尾部反转见exact_next_credit_scope_verification.json。该例shift1/2保持父方案，不能冒充当前树路由或完整Score的理论保证。
完整后缀全树重拟合已生成8候选；118/121在840份train优胜，但members_r9同批785例相对108的平均Score118上升1.0930%、121上升3.6131%，未采用。
历史类别113在members_r9同批平均Score为66,918,828,195.97 us，相对108下降0.1274%；不含后续next保护公共层，最终交付另以checkpoint为准。
周期admission公共层已实现并启用，factor=4，保持8专家。
admission：4档候选已完成840份train评分；785例×3次已测mode 98/99/108；109无本批成员结果。
admission研究配对轮相对mode 92的平均Score：98上升0.065618%，99上升0.007852%，108下降0.000003947%；微小收益不等于隐藏测试保证。
admission为公共提前处置层，非第9类专家；局部证书截止下条INSERT写入结束、其后periodic动作之前。
后续增长、Probe与回调D可能改变收益，不宣称完整Score的理论保证。
训练labeltimer仅为离线成本代理，最终性能以正式框架回调计时与完整Score为准。
