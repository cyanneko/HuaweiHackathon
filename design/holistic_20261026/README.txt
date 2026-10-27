第20题：七项要求联合迭代，2026-10-26

报告：../topic20_holistic_iteration_report.pdf，13页中文说明，已渲染并检查全部页面。
覆盖：跨算子落盘、在线计算成本、回调优化、next_op、学术/业界借鉴、动态自适应、自主贡献。

当前选择
1. 推荐主版仍为 ../MySpillScheduler_final.cpp，和本目录 Previous.cpp 同一内容。
   保守联合加载、被替代miss的压力补偿、跨算子软配额、ghost反馈规则切换、精确单/双候选快路径。
2. ../MySpillScheduler_scan_fused.cpp = Fused.cpp，本轮可选CPU优化。
   合并驻留统计与候选收集；1716条完整输入动作、I/O、Hit/Miss全部一致，6个规模输入也一致。
   500万混合输入决策时间降低3.60%，完整Score降低0.00222%；全驻留500万输入慢0.393%。
   新388例累计CPU增加0.28%，没有证明普遍更快，因此不自动覆盖主版。
3. ../MySpillScheduler_holistic.cpp = 本目录 MySpillScheduler.cpp，研究组合（特征13）。
   阶段保护 + 小n覆盖搜索 + 强制集合证书。420新例几何Score比相对前版0.9999567，变化很小；
   CPU增加4.61%、miss增加661，局部可改善27.35%也可退化21.47%。不作为默认。
4. pressure.cpp：单独实验跨算子回读债务（特征3），新420例几何Score比相对前版1.000634，未默认启用。
这些文件都定义MySpillScheduler，只选择一个单文件提交；无main，C++14，默认构造可用。

自主贡献与证明边界
- 强制集合：size(x)>M-size(目标)的驻留分区必须落盘；该集合够用时，本次写出字节最小。
  不推出后续完整Score最小；会改变输出顺序、配额刷新与后续历史。
- 阶段保护：在保守联合的规则6排序前缀中，拒绝新增的BUILD victim。
  本轮所有回放中拒绝计数为0，没有实测增益证据。
- 可见成本预算：IO字节/max(W,R)+miss是非CPU成本下界，使用其0.1%作枚举体软预算。
  不包含入口/时钟/候选收集开销，会有一个64子集块的超额，不能宣称回调总成本有硬上界。
- 回读债务：按真实跨算子短间隔恢复成本影响软配额；不是严格因果后悔值。
- 扫描合并：原顺序、表达式、比较器全部保留，动作等价；机器计时仍可能有正负变化。
不声称全球首次、全分布最优或官方高分；文献收益不作本题收益。

数据与冻结顺序
- development_manifest.json：876个已见输入，开发用；每配置1轮筛选。
- cross_target_manifest.json：32个新增定向并存BUILD增长压力输入；开发用。
- freeze.json：先固定特征13源码，再产生新系统熵，生成validation/的420例。
- validation_runs.jsonl：baseline、previous、staged、pressure、chosen，各3轮，顺序交替。
- fused_freeze.json：冻结扫描合并源码，再生成fused_validation/的388例；baseline/previous/fused各3轮。
  第二阶段开始后，第一阶段420例已属于回归集，不再声称盲测。
- scale_runs.jsonl：6个历史规模输入，3轮、4配置；fused_scale_runs.jsonl：6输入，5轮、3配置。
  三个规模输入包含500万操作。所有计时串行，无并发负载生成。
- 原始Score含公开引擎Total_Decision_Time，未更改快照、周期B或计算公式。
- BASE=0只从比值/公式统计中排除，没有从原始结果删除；420例有419个比值，388例有386个比值。
- *_summary.json使用每个输入/配置的完整Score中位数求比，不用多个指标中位数相加冒充某一次Score。
  表格的I/O/CPU/miss独立中位数仅用于分解描述。
- 计时自适应枚举可能跨运行产生不同动作；本批三轮未观测到I/O/miss分叉，不能保证跨机确定性。

核验
- development/validation/cross_strict.jsonl：7策略逐步独立记账。
- fused_strict.jsonl：1716个输入，2策略，共3432次完整回放并比较动作哈希。
- 合计12728次完整逐步回放全部通过。
- scale_fast_audit.jsonl：另12次规模回放，每个动作检查；驻留总量每4096步复核。
- final_audit.json：源码、输入、公开执行器替换范围、动作一致性、重复稳定性汇总。
- input_sha256.json、research_sources.json、requirements_coverage.json、fetch_provenance.json：输入、来源和要求对应。
- report_qa.json与report-page-*.png：PDF文本边界与全部页面渲染；report-contact.png为总览。

复现（当前机器已有Ubuntu，保持本目录工作目录）
  wsl -d Ubuntu --cd /mnt/c/Users/liunian/Desktop/Hackathon20/design/holistic_20261026 -- python3 audit_scale.py
  在Windows用已配置Python执行audit.py，可只读核对保存的源码/结果/输入。
  普通重编译：python3 experiment.py compile baseline previous staged pressure cover mandatory pressure_cover stage_cover_mandatory integrated
  重新计时既有输入：python3 experiment.py run validation/manifest.json 3 rerun baseline,previous,staged,pressure
  扫描合并接入文件已保存：g++ -std=c++14 -O2 -Wall -Wextra -pedantic-errors engine_fused.cpp -o bin_fused
  单例运行：./bin_fused <某个既有输入的完整路径>
  严格回放：./strict_fused --batch fused_paths.txt previous,fused

注意validate.py、validate_fused.py、prepare_checks.py会生成新随机输入并覆盖相应目录；
不要用重生成的数据替代原结果后仍称原始验证。现有manifest为当前机器绝对路径，换机器需重定位。
所有新设计、代码、文献清单、输入、原始结果和PDF均位于design目录内。
