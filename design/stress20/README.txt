第20题：扩展样例、C++回放与确定性反例
日期：2026年10月18日

先看 ../topic20_retest_report.pdf。该报告修正了此前仅200个相似随机输入的判断。

正式采用的主验证批次
  run_20261018_183734_1b7713
  current_run.txt 指向此目录；新运行 --fresh 会更新该指针，不删除旧目录。

总计1309个独立输入，21497848条输入操作，10460次策略回放：
  800个多种子输入：20类负载，各8个开发种子、16个验证A种子、16个验证B种子。
  128个极端参数端点全组合。
  6个边界，60个语义变换输入。
  307个小型精确模型输入（243个穷举序列+64个随机小输入，参数为玩具范围）。
  1个最终原子分区大于M的预期不可行输入。
  4个确定性回归反例。
  3个各500万操作、8算子、64分区的完整输入。
主集994个题面范围内可行输入中，963例基线分为正，31例为零不参与比值；玩具输入单独统计。

输入在哪里
  主批次/cases/：1302个主输入与4个确定性回归。
  主批次/manifest.json：1302个输入的参数、种子、N、路径和SHA-256。
  主批次/targeted_manifest.json：4个确定性回归的索引。
  主批次/scale_manifest.json：三个大输入的相对路径及摘要。
    大输入复用run_20261018_183316_5cf96e/cases/maxN_*.txt，未重复存储。
  主批次/entropy.json：新系统随机熵与冻结的策略/测试源文件摘要。

结果在哪里
  主批次/results/scores.csv：每个输入、每种策略的完整Score、I/O、Hit/Miss与容量。
  主批次/results/scores.jsonl：原始高精度回放结果。
  主批次/results/summary.json：主集/家族/数据组汇总，输赢、尾部、最坏反例。
  主批次/results/final_audit.json：逐输入摘要、策略冻结、分数重算和最终计数的核验。
  主批次/results/targeted_results.json：4个确定性反例结果。
  主批次/results/*_actions.csv：这些反例的有效SPILL/LOAD动作。
  主批次/results/offline_bounds.json：307个小输入的精确离线最优值。
  主批次/results/crosscheck.json：45次C++与旧Python模型交叉核对。
  主批次/results/metamorphic_checks.json：160次同余key变换的完全一致性检查。
  主批次/results/scale_results.json：最大规模输入实跑，含回放时间、进程时间和峰值工作集。
  主批次/results/literal_baseline_diagnostics.json：原样朴素基线的INSERT记账缺陷。
  主批次/results/previous_8317x_replay.json：探索批次8317倍反例与保守版回放结果。

主要发现
  旧版：主集几何平均相对代价0.6782117，626胜/119平/218负，最坏1166.50倍。
  V2激进：0.6343434，653胜/110平/200负；平均更好，仍继承严重BUILD风险。
  Prefix保守版：0.9984692，513胜/450平/0负；收益较小，不宣称任意输入不退化。
  以上输赢都以963个正分输入为分母，较小的改善也可能计为胜；原始数据全部保留。
  70条操作的确定性输入复现旧版5000.500298倍退化，反向热点又使旧版明显优于基线。
  所有可行输入无意外失败；不可行分区>M样例在8种策略上按预期失败，不伪称全部通过。

基线和规则
  naive是排除当前INSERT分区、固定平局为(size,op,pid)降序的安全朴素比较基线。
  这是本地比较基线，不是未知官方BASE值。
  literal_naive保持公开参考的size排序和INSERT选择行为，只用于诊断，不参与性能排名。
  回调仅能观察当前目标和一个next_op；没有向策略提供全部未来或隐藏Hit序列。
  中小输入逐动作核对真实驻留字节之和；500万输入每4096个有效操作完整核对账本，
  但每次动作/操作仍检查容量。数据只按大小模拟，工作集RSS不代表真实Hash表占用。

复现
  编译：从工作区运行 cmd /c design\stress20\compile_runner.cmd
  使用本机已有Visual Studio 2022 Community的MSVC；无需安装新工具。
  Python：C:\Users\liunian\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
  在stress20中使用该Python执行：
    retest.py run
    retest.py summarize
    targeted_checks.py
    scale_tests.py
    final_audit.py
  重跑冻结主批次可使用 retest.py run --run run_20261018_183734_1b7713
  新种子：retest.py all --fresh
  完整新批次：run_all.cmd（重新编译、生成新样例、跑全部检查，保留旧目录）
  PDF重建：build_retest_report.py（需要reportlab，读取当前主批次结果）
  单个输入回放：runner.exe <input.txt> naive,legacy,v2,aggressive,prefix
  输出动作轨迹：runner.exe <input.txt> legacy strict <trace.csv>

目录内其他批次
  run_20261018_183316_5cf96e：旧策略探索，发现8317倍反例，包含最大规模输入原文件。
  其他早期run目录：生成器开发、编译联调或探索记录，不混入本报告主验证结论。
  部分早期目录不含完整结果，这是开发过程记录，并非可用于排名的成功批次。

这些是公开题面下的合成测试。没有官方隐藏输入，没有官方评测分数。
