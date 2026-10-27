第20题新版解答、训练与四轮迭代
读取题面：2026年10月26日；网页updateTime：2026年10月20日17:56:27（北京时间）。

先读 ../topic20_updated_solution_20261026.pdf。所有旧报告的Score定义与新版不同。

提交文件
  ../MySpillScheduler.cpp = 本目录MySpillScheduler_score_first.cpp。
    学习冲分版，21节点代价敏感决策树，深度4。运行时最多4次模型阈值比较，只选一次策略。
    根据首次需要淘汰时的合法SystemState选择候选策略；小覆盖Build存在严重尾部退化。
  ../MySpillScheduler_balanced.cpp = 本目录MySpillScheduler.cpp。
    平衡版，默认专家4：最大分区Build、观测代价Probe、短间隔读回反馈和空间预取。
  两个文件均只定义MySpillScheduler及成员，无main、外部模型文件、输入文件访问或第三方依赖。
  两个文件类名相同，选择一个提交，不能一起编译。官方系统提供所有框架类型。

实际编译
  本机已有WSL Ubuntu的g++13.3，使用-std=c++14 -O2，并通过-Wall -Wextra -pedantic-errors检查。
  三个GNU程序gcc_baseline、gcc_recommended、gcc_score_first使用下载的公开参考引擎。
  候选程序仅插入调度器文件并替换make_unique类型，未修改引擎/结构体/计时器/输入解析。
  Windows另用MSVC的C++14、O2和严格模式完成独立回放与交叉核对。

最重要的题面变化
  Score = Total_IO_Time + miss_penalty * Miss + Total_Decision_Time。
  单组得分clamp(10*(1-VAL/BASE),0,10)，总和上限50；VAL=0、BASE=0、未改善和OOM/超时均按规则处理。
  严格在线，只能看SystemState及一个next_op；不得读完整输入、op_lines或新增Hit回调。
  仅标准库、C++14、一个.cpp、无参数构造MySpillScheduler，墙上时间限制60秒。
  最终每分区<=M且保证可行；旧版分区大于M的诊断现在不属于正式合法输入。
  SystemState没有miss_penalty，两个提交都未读取真实惩罚值；32是固定启发式尺度，1仅为题面下界。

最终主结果（实际GNU公开参考引擎，三次中位数）
  最终批次：holdout_20261026_111448_c4e556
  608个新输入，607个BASE正分输入；每个程序运行三次，共5472次实际参考引擎运行。
  学习冲分版：几何相对代价0.706662，降低29.33%；单组公式均值2.239/10；最坏19712.42倍。
  平衡版：几何相对代价0.749044，降低25.10%；单组公式均值1.676/10；最坏1.741倍。
  三组各500万操作完整输入在实际GNU引擎中跑完，最长约8.85秒；包括平衡版退化的输入，全部保留。
  这些是本机合成结果，不是官方隐藏数据成绩；没有全输入最优或任意输入不退化的证明。

最终结果和数据
  current_holdout.txt：指向最终批次。
  最终批次/manifest.json：608个输入的参数、完整路径、种子和SHA-256。
  最终批次/protocol.json：生成时间与模型冻结来源；两个候选在新输入生成前已冻结。
  最终批次/gcc_published_engine_results.jsonl：5472条实际GNU引擎原始输出。
  最终批次/gcc_published_engine_summary.json：主表汇总、最坏输入与跨编译器检查。
  最终批次/rollouts.jsonl、summary.json：Windows三次回放及七策略等消融，作为辅助证据，不与GNU的BASE混用。
  results/gcc_validation.json：严格C++14编译、18次小输入SDK运行及9次500万操作SDK运行。
  results/gcc_scale_results.json：三组最大规模输入的实际Score、CPU决策时间、墙上时间。
  results/final_audit.json：所有主结果、源文件/输入摘要和框架替换范围核验。
  results/tiny_legality.jsonl：307个玩具输入、六种策略，均不低于独立离线最优下界。
  results/regression_results.jsonl：7个历史反例与回归输入，不伪装成新验证。
  results/hidden_penalty_invariance.json：修改输入真实penalty后，平衡版动作相关结果不变。
  results/integration_checks.json：Windows公开参考引擎与独立回放的非计时结果核对。

四轮历史
  round1/：第一轮模型源文件、训练/冻结记录及当时benchmark.exe；holdout_pointer.txt指向第一批608例。
  round2/：安全Build与短间隔读回反馈、13节点模型及当时记录；新608例。
  round3/：首次Miss再选择策略、7节点模型及当时记录；另608例。
  MySpillScheduler_learned_deferred.cpp：延后选择的学习候选，保留负结果，不强制作为主提交。
  所有新输入四轮合计2432个文件；历史开发输入998个，含同源变换的分组处理。
  固定种子用于重放；新批次先取系统熵并记录，再生成输入，未按分数挑选种子。

独立性与可观察性
  训练标签来自自行生成的开发负载上不同策略的Score；运行时不读取未来序列。
  开发集同源种子/键别名分在同一组，不跨训练和开发验证。
  阶段性新验证用于继续迭代后，不再被称作后来版本的未见测试。
  最终两个候选冻结后，才生成最后一批608例；此后没有按该批结果修改候选系数。
  20类负载各24例，另128个二进制端点参数组合；部分随机重命名ID避免只利用热点编号。
  没有完整Hit序列。热度统计来自Miss和合法next Probe，去重后按全局Probe时钟衰减。
  短间隔读回是反馈信号，不等于已证明当时淘汰错误，也不是无偏频率估计。

参考框架的实际差异
  文本说框架自身不计时，但代码把getSystemState放在计时lambda内；本次完全保留该范围。
  同大小分区的公开Naive没有完整平局规则。最终608例有14例BASE在Windows/GNU间的I/O或Miss不同。
  两个候选的608例I/O、Hit/Miss跨Windows独立回放与GNU实际引擎全部一致。
  计时仍随机器与调度波动，不能承诺评测机耗时与本机相同。

复现（本机已有环境）
  Python：C:\Users\liunian\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
  在工作区运行：cmd /c design\iteration_20261026\build.cmd
  该Python执行：design/iteration_20261026/train_and_evaluate.py test
  该Python执行：design/iteration_20261026/extra_validation.py small
  wsl -d Ubuntu --exec python3 /mnt/c/Users/liunian/Desktop/Hackathon20/design/iteration_20261026/gcc_validation.py
  wsl -d Ubuntu --exec python3 /mnt/c/Users/liunian/Desktop/Hackathon20/design/iteration_20261026/gcc_full_holdout.py
  该Python执行：design/iteration_20261026/final_audit.py
  重新拟合研究模型：train_and_evaluate.py collect，然后train --robust。
    训练会改变本目录的研究模型区域和冻结记录；根目录两个已交付文件不自动改写。
  生成新批次：train_and_evaluate.py generate_test；更新current_holdout指针，不删除旧批次。

公开来源与文献
  官方：https://www.chaspark.com/#/races/competitions/1326693349800046592
  topic_20_current.json/html/txt、fetch_provenance.json：公开读取快照及摘要。
  problem_diff.txt：与先前已保存题面的差异。
  GDS：https://static.usenix.org/publications/library/proceedings/usits97/full_papers/cao/cao_html/node8.html
  LeCaR：https://www.usenix.org/conference/hotstorage18/presentation/vietri
  LRB：https://www.usenix.org/conference/nsdi20/presentation/song
  鲁棒预测缓存：https://proceedings.mlr.press/v80/lykouris18a.html
  只借鉴适用思想，没有声称复现论文全部算法、获得其竞争比或继承论文实验收益。
