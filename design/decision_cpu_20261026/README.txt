第20题：在线决策CPU与完整Score权衡，2026-10-26

最终说明：../topic20_decision_cpu_report.pdf
可选候选：../MySpillScheduler_cpu.cpp，单文件C++14，无main，无参数构造MySpillScheduler。
此候选以此前基础控制器flags=351为起点；没有覆盖旧默认提交。

最终保留的小范围改动：
1. Probe计划预留至多两个LOAD的位置，避免同一返回动作vector多次扩容。
2. ghost到期检查只扫描实际Q=K*P个条目，而非始终512。
3. 所有算子进入PROBE后，利用阶段单调性跳过重复阶段遍历，继续保留窗口和读回反馈。

已比较并保留失败结果：
static编译期配置、stack栈计划、sample16固定采样、dynamic自适应维护预算、
scratch缓冲复用、reciprocal倒数外提、indexed增量驻留索引、cached不可变代价缓存、
cold冷路径隔离、frequency过滤比值比较等。这些未给出稳定的总收益，不强行部署。

最终验证：
先冻结源文件，再生成新336例；同一公开引擎、g++ C++14、每配置3次。
610开发例+336新例严格核对动作顺序、读写字节和Hit/Miss，最终版本完全一致。
6个CPU/规模场景各作5轮原版与候选版配对，其中3个历史输入各500万操作。
每次均包含公开引擎决策时间；没有修改框架计时或周期B。

本轮结论：
新336例累计决策时间降低约1.58%，但Score几何比和单组公式均值没有同步改善。
五轮规模结果包含正负变化。当前只能交付可选的等价微优化候选，不能宣称稳定全面更优。
高频空回调约0.28微秒的总计时中，内部函数采样只有约20~30纳秒；框架快照等固定成本形成上限。
默认仍保留此前版本；是否采用该候选应按目标评测机的配对结果决定。

复现：已有Linux/Ubuntu环境中（manifest为绝对路径，换机器需改路径）
python3 experiment.py compile baseline previous active
g++ -std=c++14 -O2 engine_optimized.cpp -o bin_optimized
python3 experiment.py run validation/manifest.json 3 validation baseline,previous,optimized
最终optimized源文件对应MySpillScheduler.cpp；编译接入代码为engine_optimized.cpp。
cpu/scale的5轮原始结果：scale_cpu_runs.jsonl；中位数：scale_cpu_summary.json。
严格行为回放：development_final_strict.jsonl、validation_final_strict.jsonl。
完整摘要核验：python3 audit_final.py。

不要重新运行生成脚本后把新输入当成原测试；源文件冻结和新系统熵均已记录。
诊断用ProfileScheduler添加内部计时，不能用它的Score代替正式无插桩结果。
没有官方隐藏数据成绩，没有跨机器或全输入速度保证。
