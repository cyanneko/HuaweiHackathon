# R78 scale teacher 独立轻量复核

结论：PASS（限定下述审查范围）。4/4 预定 TRAIN 锚、11/11 实际分支完成，14.362 秒 < 90 秒；CPU RELEASED。未运行 native、未读 dev、未重读或哈希大 trace。核验30份原始 stdout/stderr SHA、11份 force SHA、10项源码 SHA与native binary；4个原R75 control均与baseline的EOF整数账/hit/callback数精确一致。baseline也与上一轮未插桩R75物理成本在输出舍入范围一致。

固定层：fast_shared p3 Overflow、fast_staggered p3 Miss、slow_shared p12 Overflow、burst_staggered p12 Miss。源码按指定kind所有callback的预声明salt/inputSHA/index/kind minhash选锚，无cost或候选池筛选；所有锚在forced branch前固定。独立核验了选中hash和snapshot SHA，未重新遍历大trace验证全局最小hash及eligible计数，不能把该部分称作独立全量选锚重放。

|锚/层|index|候选|R75 regret μs|占原R75后缀成本|占原R75整例成本|最佳候选|
|---|---:|---:|---:|---:|---:|---|
|a00 fast_shared_p3|413|3|6289760.910|2.529876%|2.522241%|old_union_min_x13_different|
|a01 fast_staggered_p3|22962|3|3366497.255|4.225456%|1.116187%|minimum_singlefit|
|a02 slow_shared_p12|28|3|0.000|0.000000%|0.000000%|r75_original,old_union_min_x13_different|
|a03 burst_staggered_p12|35856|2|586378.755|0.085326%|0.027581%|old_union_min_x13_different|

分母：4个锚中3个存在更优候选；7个非control动作中{'better': 4, 'worse': 2, 'tie': 1}；all-tie锚0。11分支含4个control，不能把11当作独立改进机会分母。最后一锚只有2候选，按冻结去重/可行性规则缺1，没有换锚补齐。

整数账：G = Wbytes×Rbw + Rbytes×Wbw + misses×penalty×Wbw×Rbw，标签为final减选锚前账的suffix G；11分支逐项复算一致，真实penalty和带宽来自所选输入合同。μs=G/(Wbw×Rbw)。标签比较同锚共享前缀；局部改进百分比必须注明用原R75后缀还是整例分母。

审计边界：Python仅恢复到选中callback的prefix，沿途核args/q，只有选中点核physical hash；private prehash由native guard核验。FAST分支在该点强制一次实际action并commit，之后真实R75续跑到EOF。本次control证据是EOF ledger/hit/callback数一致，不是完整suffix轨迹逐步相等，也不是全prefix每点physical hash一致。计时由main中冻结配置与输入hash完成后开始，到所有原生基线/选锚/恢复/分支及结果完成14.362秒；前置轻量冻结与hash不包含在该计时，不能称端到端墙钟总耗时。

这是4个训练锚的候选池局部空间，未训练，不能将3/4存在局部收益直接解释成完整policy提升或外推dev。当前没有发现需阻断结果使用的整数账或control错误；所有结论受上述prefix/抽样范围限制。
