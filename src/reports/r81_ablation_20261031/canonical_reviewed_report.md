# 双时间尺度分层复用调度器：创新机制与消融独立复核报告

最终分析含94例×9方法的846个有效计分单元，但来自两个预先冻结的批次。原始846格运行仍为INCOMPLETE，不能说原一次运行成功：原845格有效、1格局部预算截断；经明确授权，仅将最后一个stat用例的全部9方法同批重测，排除该用例原8格成功结果和1格失败结果。最终使用837格原结果+9格恢复结果，总计855次计分尝试。

Full的本地归一分S在旧dyna12/final72分别为4.455849488和3.713166337分；两套先各均分再50/50得到4.084507912分。合并来源的stat10独立为3.439812321分，不进入主分母。七个干预不是可相加的贡献拆分；有负向和零物理差异结果，均保留。最终算法仍为冻结Full，BuildBestFit不在本消融中，也不据消融自动换版。

## 1. 证据完整性、失败及固定恢复

|批次/数据|计划|有效|失败|状态|控制器时间/额度（秒）|
|---|---:|---:|---:|---|---:|
|原批/dyna|108|108|0|PASS|780.849/1000|
|原批/final|648|648|0|PASS|335.407/500|
|原批/stat|90|89|1|INCOMPLETE|451.517/450|
|恢复批/仅stat case09全部九法|9|9|0|COMPLETE_FIXED_RECOVERY|115.080/180|

原失败格为`eval_09_mixed_mixed_staggered`的`UniformOperatorMarginal`：局部450秒预算只剩3.636723秒，watchdog以-9终止，stdout/stderr为空且无metrics。它不是已证明超过60秒单格限时的算法失败。原stat有90个terminal行、89个valid；ALL_CELLS_TERMINAL不等于全部有效，原completion_gate与aggregate=null保留不改。原全局耗时1669.249/2200秒，未耗尽全局预算。

恢复规则在GO前冻结：前9个stat用例81格不变；case09全部9格统一采用恢复批的新成本、新Naive和新D，原8个成功格也全部排除；不择优、不改算法、0次重新编译。原完整dyna108格与final648格不重跑。恢复批180秒包括输入/ELF核对、9格执行、审核与发布；此次通过。

独立复核覆盖原845个有效stdout、原1个失败日志、恢复9个stdout的哈希/五指标，以及最终选用846格的唯一性、来源映射、188个同输入历史Full/Naive物理对照。原始C严格取stdout Total_Score；源/TU/ELF、两批GO、输出及发布绑定均核对。原批与恢复批活动子进程均为0，CPU已释放。独立复核没有读取输入正文、没有运行native。

## 2. Naive对照、代码来源与能主张什么

Naive是冻结的官方朴素策略：从驻留非空分区中排除当前目标，按data_size降序std::sort，依次落盘到空间足够；miss后LOAD目标；周期回调不主动调整。同大小保留该官方比较器行为，不另造最大ID等平局规则。它是本轮每个用例同批新测的分母，不复用历史D。源SHA为`f15181df02b7f36624a9d11507e3167ab70617f52e587ed7215bc058e07db6ea`。

Full实际源为`tmp/r81_named_20261031/MySpillScheduler.cpp`，SHA `2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`，已发布代码commit为`3064e270fde0473810cd8c0e57b738ee48356254`、路径`submission/MySpillScheduler.cpp`。原算法、可读版和语义宏命名版已有预处理tokens/ELF等价证据；本轮Full ELF再次匹配`bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1`。所有方法CPU C++14、g++ -O2、无计时插桩。

对外机制名称采用快算子边际、慢分区条件分布、异质性共享、回访风险、next保护/受限预取、有限子集逐出与结构回退，不用实验编号代替解释。源码能证明这些机制如何组合，消融能提供所选输入上的条件效果；不据此声称指数衰减、共享、预取或贪心本身首次原创，也不声称全局最优。没有开展新的文献优先权检索，代码机制与理论原创性严格区分。

按用户提供截图要求，本报告给出具体方案/复杂度、同轮Naive对照与来源/改动解释。这里的输入是已观察本地合成数据，不等于组织方隐藏用例；本地实测不能替代组织方用例展示，创新评审是否成立与是否获得分值由评审决定，不承诺30分或隐藏集表现。

## 3. 评分与统计口径

C是越小越好的成本，直接取stdout Total_Score；定义为模拟IO+输入penalty×Miss+本轮实测D。physical=IO+penalty×Miss用于分解；真实隐藏惩罚不在SystemState中，策略固定100微秒只是假设代理。D包括框架状态复制等调度计时，不是磁盘端到端耗时。

本地既有0–10归一分S越大越好，不是官方程序名为Total_Score的成本C。零截断会掩盖负例，不能把S/10直接解释成平均成本下降率；未截断相对变化须依据raw或实际C比。

逐例score=clip(10×(1−C/C_Naive),0,10)，C/Naive为非正时按冻结规则记0；raw points=10×(1−C/C_Naive)不截断，零分母显式未定义并计数。先对每套用例等权均分，再将dyna12与final72各权0.5，不能把84例池化平均；stat10单列。尾部使用nearest-rank ceil(q×n)，每个比值保留planned/defined/undefined。C比和physical比是逐例比值的均值，不是总成本之比。

表中的“保留机制分数差”定义为Full−干预版；为正表示该干预在此口径下降分，为负表示干预版得分更高。它是一次条件移除效果，不是独立可相加的贡献、因果份额或新增点数。因截断和不同Naive权重，成本比均值与均分差可能方向不同；raw表揭示这些边界。单次D仅描述，统计维护仍保留，不能把D差叫作可删除模块的全部运行开销。

## 4. 同轮Naive与全部方法得分

|方法|dyna12 score|final72 score|主50/50 score|主50/50 raw points|stat10 score|stat10 raw points|主保留机制分数差Full−干预|
|---|---:|---:|---:|---:|---:|---:|---:|
|Naive|0.000000000|0.000000000|0.000000000|0.000000000|0.000000000|0.000000000|+4.084507912|
|Full|4.455849488|3.713166337|4.084507912|4.003620157|3.439812321|3.439812321|+0.000000000|
|FixedShare075|4.458017537|3.639784785|4.048901161|4.001341409|3.408577701|3.408577701|+0.035606751|
|UnifiedSlow2048|4.306732593|3.709111805|4.007922199|3.950047842|3.494851339|3.494851339|+0.076585713|
|NoPeriodicPrefetch|4.455155689|3.710343805|4.082749747|4.000593294|3.445588140|3.445588140|+0.001758165|
|NoNextProtection|4.434520653|3.683534013|4.059027333|3.981019923|3.421778951|3.421778951|+0.025480579|
|UnitMissCost|4.133023835|3.207240512|3.670132173|3.664231445|2.602840797|2.602840797|+0.414375739|
|NoStructurePolicy|4.455852364|3.713121148|4.084486756|4.003693221|3.439700271|3.439700271|+0.000021156|
|UniformOperatorMarginal|1.725921918|3.651430345|2.688676132|2.455915973|3.309180302|3.309180302|+1.395831780|

## 5. 七个干预的准确语义与结果边界

|干预|实际关闭/替换内容|仍保留什么|主50/50 Full−干预|stat Full−干预|
|---|---|---|---:|---:|
|FixedShare075|异质性自适应共享→固定0.75|不是无共享；保留异质性统计、快边际、全部样本；主hier与risk均固定share|+0.035606751|+0.031234620|
|UnifiedSlow2048|快边际半衰期256→2048|慢分区2048不变；risk128/512、coverage256与历史统计不变|+0.076585713|-0.055039017|
|NoPeriodicPrefetch|去周期预取动作|周期update/coverage/next采样保留；闭环后续miss与可见样本会改变|+0.001758165|-0.005775819|
|NoNextProtection|去next PROBE保护|同时去cycle跳过和一般priority+1e12；next采样及当前目标排除保留|+0.025480579|+0.018033370|
|UnitMissCost|异质IO/100代理成本→单位miss密度|priority=reuse/bytes，top4损失=Σpriority×bytes；字节容量和冷启动R≥W门仍保留|+0.414375739|+0.836971525|
|NoStructurePolicy|去scan/cycle决策|保留历史/后继/步长维护；同时关闭cycle预取例外；不是分别隔离scan和cycle|+0.000021156|+0.000112051|
|UniformOperatorMarginal|快算子边际→均匀1/K|慢条件分布、共享、快统计维护及risk算子信息保留|+1.395831780|+0.130632019|

快算子边际、异质成本项的移除在主口径上退化较明显；这支持它们在本冻结组合/输入上的条件作用，不代表可外推或将分差相加。

算子热度的主贡献明显依赖dyna：Full−均匀算子边际分别为dyna +2.729927570、final +0.061735991、stat +0.130632019个归一分；主50/50分差+1.395831780主要由dyna驱动，不能宣传为所有分布均有同等大的优势。固定共享在dyna优于Full、在final及stat低于Full；统一慢时标与去预取也存在数据集间方向不同的结果，不能只报有利一套。

NoStructurePolicy的物理差异必须单独判读：下表按完整IO/hit/miss三项完全一致计数。若全相同，则本轮观察到的物理贡献为零；分数/D小差不计作结构机制的创新增益，也不能由输出相同反推该分支从未执行或对所有未来输入都无用。

|干预|dyna物理相同/12|final物理相同/72|stat物理相同/10|
|---|---:|---:|---:|
|FixedShare075|0|1|0|
|UnifiedSlow2048|0|15|3|
|NoPeriodicPrefetch|0|16|0|
|NoNextProtection|0|24|1|
|UnitMissCost|0|0|0|
|NoStructurePolicy|12|72|10|
|UniformOperatorMarginal|0|15|3|

## 6. 每套raw、IO+miss与D完整分解

IO、惩罚项、D均为本套所有用例之和，单位10^6微秒；它们是分解展示，C仍以原stdout为准。raw未定义和负raw例数显式保留。

|数据集|方法|score均值|raw均值|raw已定义/未定义|raw负例|IO总量|penalty×Miss总量|D总量|
|---|---|---:|---:|---|---:|---:|---:|---:|
|dyna|Naive|0.000000000|0.000000000|12/0|0|6048364.434505|2489.804900|27.581874|
|dyna|Full|4.455849488|4.455849488|12/0|0|3866939.293984|1740.374300|30.477814|
|dyna|FixedShare075|4.458017537|4.458017537|12/0|0|3867967.961369|1727.356400|28.474659|
|dyna|UnifiedSlow2048|4.306732593|4.306732593|12/0|0|3936915.971157|1770.359400|31.312424|
|dyna|NoPeriodicPrefetch|4.455155689|4.455155689|12/0|0|3867401.088504|1741.045400|29.623276|
|dyna|NoNextProtection|4.434520653|4.434520653|12/0|0|3878931.079446|1745.814000|29.163491|
|dyna|UnitMissCost|4.133023835|4.133023835|12/0|0|3973699.690888|1654.516700|30.166251|
|dyna|NoStructurePolicy|4.455852364|4.455852364|12/0|0|3866939.293984|1740.374300|29.913709|
|dyna|UniformOperatorMarginal|1.725921918|1.469611176|12/0|5|5254795.046409|2675.870000|49.148129|
|final|Naive|0.000000000|0.000000000|72/0|0|111199.504836|764.224592|3.085838|
|final|Full|3.713166337|3.551390827|72/0|5|84157.635922|718.086246|2.004545|
|final|FixedShare075|3.639784785|3.544665280|72/0|5|85123.990898|703.199707|2.004402|
|final|UnifiedSlow2048|3.709111805|3.593363090|72/0|5|84184.085737|705.240530|1.907500|
|final|NoPeriodicPrefetch|3.710343805|3.546030899|72/0|5|84166.223772|719.798874|1.951126|
|final|NoNextProtection|3.683534013|3.527519194|72/0|6|85453.368457|727.167764|1.906145|
|final|UnitMissCost|3.207240512|3.195439056|72/0|3|86547.634130|558.516174|1.671421|
|final|NoStructurePolicy|3.713121148|3.551534078|72/0|5|84157.635922|718.086246|1.952424|
|final|UniformOperatorMarginal|3.651430345|3.442220771|72/0|7|84250.105149|726.353057|2.018947|
|stat|Naive|0.000000000|0.000000000|10/0|0|7155969.977378|450.530370|11.613617|
|stat|Full|3.439812321|3.439812321|10/0|0|4907268.587897|852.594720|11.833671|
|stat|FixedShare075|3.408577701|3.408577701|10/0|0|4958399.033361|854.172710|10.152447|
|stat|UnifiedSlow2048|3.494851339|3.494851339|10/0|0|4904900.769099|843.390260|10.061081|
|stat|NoPeriodicPrefetch|3.445588140|3.445588140|10/0|0|4907275.616204|860.438920|10.982137|
|stat|NoNextProtection|3.421778951|3.421778951|10/0|0|4957865.453627|855.883070|9.858090|
|stat|UnitMissCost|2.602840797|2.602840797|10/0|0|5237365.340519|395.479390|8.105824|
|stat|NoStructurePolicy|3.439700271|3.439700271|10/0|0|4907268.587897|852.594720|12.315487|
|stat|UniformOperatorMarginal|3.309180302|3.309180302|10/0|0|4909334.282735|841.849430|10.187371|

## 7. 成本比与物理比的尾部及所有负向方向

以下比值均为方法/Full；胜表示<1，负表示>1。每套每法均保留，不能用一次D差异证明稳定时延优势。全部逐例成本坏例另见../r81_ablation_20261031/REVIEWED_NEGATIVE_CASES.csv；不只列最坏一例。

|数据集|方法|比值|有效/未定义|均值|P50|P90|最坏|胜/平/负|最坏用例|
|---|---|---|---|---:|---:|---:|---:|---|---|
|dyna|Naive|C|12/0|3.314813282|1.429221410|8.568244756|14.452661636|0/0/12|train_slow_shared_01|
|dyna|Naive|physical|12/0|3.315025879|1.429225231|8.568388729|14.454417532|0/0/12|train_slow_shared_01|
|dyna|Full|C|12/0|1.000000000|1.000000000|1.000000000|1.000000000|0/12/0|dev_burst_staggered_09, dev_fast_shared_08, dev_slow_staggered_07, holdout_burst_shared_12, holdout_fast_staggered_11, holdout_slow_shared_10, train_burst_shared_05, train_burst_staggered_06, train_fast_shared_03, train_fast_staggered_04, train_slow_shared_01, train_slow_staggered_02|
|dyna|Full|physical|12/0|1.000000000|1.000000000|1.000000000|1.000000000|0/12/0|dev_burst_staggered_09, dev_fast_shared_08, dev_slow_staggered_07, holdout_burst_shared_12, holdout_fast_staggered_11, holdout_slow_shared_10, train_burst_shared_05, train_burst_staggered_06, train_fast_shared_03, train_fast_staggered_04, train_slow_shared_01, train_slow_staggered_02|
|dyna|FixedShare075|C|12/0|0.998659566|0.999881725|1.000318180|1.007497164|7/0/5|holdout_burst_shared_12|
|dyna|FixedShare075|physical|12/0|0.998665567|0.999884012|1.000318345|1.007497882|7/0/5|holdout_burst_shared_12|
|dyna|UnifiedSlow2048|C|12/0|1.024461703|1.008919353|1.074508917|1.135754352|5/0/7|holdout_fast_staggered_11|
|dyna|UnifiedSlow2048|physical|12/0|1.024466987|1.008918677|1.074511171|1.135766165|5/0/7|holdout_fast_staggered_11|
|dyna|NoPeriodicPrefetch|C|12/0|1.000121357|1.000106730|1.000487017|1.000640288|4/0/8|train_burst_staggered_06|
|dyna|NoPeriodicPrefetch|physical|12/0|1.000124503|1.000105513|1.000486344|1.000640465|4/0/8|train_burst_staggered_06|
|dyna|NoNextProtection|C|12/0|1.003206176|1.001464880|1.005372289|1.016462860|0/0/12|dev_burst_staggered_09|
|dyna|NoNextProtection|physical|12/0|1.003209533|1.001466420|1.005371278|1.016463289|0/0/12|dev_burst_staggered_09|
|dyna|UnitMissCost|C|12/0|1.065655475|1.032406060|1.204545028|1.256158958|0/0/12|dev_burst_staggered_09|
|dyna|UnitMissCost|physical|12/0|1.065661636|1.032406631|1.204551767|1.256159122|0/0/12|dev_burst_staggered_09|
|dyna|NoStructurePolicy|C|12/0|0.999997637|0.999999735|1.000001250|1.000001859|8/0/4|train_fast_shared_03|
|dyna|NoStructurePolicy|physical|12/0|1.000000000|1.000000000|1.000000000|1.000000000|0/12/0|dev_burst_staggered_09, dev_fast_shared_08, dev_slow_staggered_07, holdout_burst_shared_12, holdout_fast_staggered_11, holdout_slow_shared_10, train_burst_shared_05, train_burst_staggered_06, train_fast_shared_03, train_fast_staggered_04, train_slow_shared_01, train_slow_staggered_02|
|dyna|UniformOperatorMarginal|C|12/0|1.698372263|1.668893095|2.210709704|2.311455048|0/0/12|holdout_fast_staggered_11|
|dyna|UniformOperatorMarginal|physical|12/0|1.698375961|1.668895806|2.210697519|2.311462208|0/0/12|holdout_fast_staggered_11|
|final|Naive|C|72/0|2.173634518|1.510713888|4.130298295|9.791988125|5/0/67|eval_015_random_hotspot|
|final|Naive|physical|72/0|2.174444759|1.510717350|4.130434514|9.801739687|5/0/67|eval_015_random_hotspot|
|final|Full|C|72/0|1.000000000|1.000000000|1.000000000|1.000000000|0/72/0|eval_000_random_hotspot, eval_003_random_zipf, eval_004_random_zipf, eval_005_random_lognormal, eval_006_random_hotspot, eval_008_random_zipf, eval_009_random_lognormal, eval_011_random_zipf, eval_013_random_lognormal, eval_014_random_hotspot, eval_015_random_hotspot, eval_016_random_hotspot, eval_017_random_lognormal, eval_018_random_hotspot, eval_019_random_hotspot, eval_022_random_hotspot, eval_023_random_hotspot, eval_024_random_zipf, eval_025_random_zipf, eval_026_random_hotspot, eval_027_random_hotspot, eval_028_random_zipf, eval_029_random_zipf, eval_031_random_zipf, eval_033_random_zipf, eval_034_random_lognormal, eval_036_random_lognormal, eval_038_random_zipf, eval_039_random_lognormal, eval_040_random_hotspot, eval_042_random_hotspot, eval_043_random_hotspot, eval_044_random_zipf, eval_045_random_lognormal, eval_046_random_zipf, eval_047_random_zipf, eval_050_random_zipf, eval_051_random_zipf, eval_052_random_zipf, eval_053_random_zipf, eval_054_random_zipf, eval_055_random_zipf, eval_056_random_zipf, eval_057_random_zipf, eval_058_random_zipf, eval_059_random_zipf, eval_060_random_zipf, eval_061_random_zipf, eval_062_random_zipf, eval_063_random_zipf, eval_064_random_hotspot, eval_065_random_hotspot, eval_066_random_hotspot, eval_067_random_hotspot, eval_068_random_hotspot, eval_069_random_hotspot, eval_070_random_hotspot, eval_071_random_hotspot, eval_072_random_hotspot, eval_073_random_hotspot, eval_074_random_hotspot, eval_075_random_hotspot, eval_076_random_hotspot, eval_077_random_hotspot, eval_078_random_lognormal, eval_079_random_lognormal, eval_080_random_lognormal, eval_081_random_lognormal, eval_082_random_lognormal, eval_083_random_lognormal, eval_084_random_lognormal, eval_085_random_lognormal|
|final|Full|physical|72/0|1.000000000|1.000000000|1.000000000|1.000000000|0/72/0|eval_000_random_hotspot, eval_003_random_zipf, eval_004_random_zipf, eval_005_random_lognormal, eval_006_random_hotspot, eval_008_random_zipf, eval_009_random_lognormal, eval_011_random_zipf, eval_013_random_lognormal, eval_014_random_hotspot, eval_015_random_hotspot, eval_016_random_hotspot, eval_017_random_lognormal, eval_018_random_hotspot, eval_019_random_hotspot, eval_022_random_hotspot, eval_023_random_hotspot, eval_024_random_zipf, eval_025_random_zipf, eval_026_random_hotspot, eval_027_random_hotspot, eval_028_random_zipf, eval_029_random_zipf, eval_031_random_zipf, eval_033_random_zipf, eval_034_random_lognormal, eval_036_random_lognormal, eval_038_random_zipf, eval_039_random_lognormal, eval_040_random_hotspot, eval_042_random_hotspot, eval_043_random_hotspot, eval_044_random_zipf, eval_045_random_lognormal, eval_046_random_zipf, eval_047_random_zipf, eval_050_random_zipf, eval_051_random_zipf, eval_052_random_zipf, eval_053_random_zipf, eval_054_random_zipf, eval_055_random_zipf, eval_056_random_zipf, eval_057_random_zipf, eval_058_random_zipf, eval_059_random_zipf, eval_060_random_zipf, eval_061_random_zipf, eval_062_random_zipf, eval_063_random_zipf, eval_064_random_hotspot, eval_065_random_hotspot, eval_066_random_hotspot, eval_067_random_hotspot, eval_068_random_hotspot, eval_069_random_hotspot, eval_070_random_hotspot, eval_071_random_hotspot, eval_072_random_hotspot, eval_073_random_hotspot, eval_074_random_hotspot, eval_075_random_hotspot, eval_076_random_hotspot, eval_077_random_hotspot, eval_078_random_lognormal, eval_079_random_lognormal, eval_080_random_lognormal, eval_081_random_lognormal, eval_082_random_lognormal, eval_083_random_lognormal, eval_084_random_lognormal, eval_085_random_lognormal|
|final|FixedShare075|C|72/0|1.013427370|1.008637946|1.112003522|1.313169039|25/0/47|eval_042_random_hotspot|
|final|FixedShare075|physical|72/0|1.013421235|1.008639030|1.112011854|1.313177234|25/1/46|eval_042_random_hotspot|
|final|UnifiedSlow2048|C|72/0|0.997693412|0.999993282|1.012506280|1.112513932|45/0/27|eval_051_random_zipf|
|final|UnifiedSlow2048|physical|72/0|0.997716657|1.000000000|1.012843835|1.112254821|33/15/24|eval_051_random_zipf|
|final|NoPeriodicPrefetch|C|72/0|1.001145397|1.000001984|1.005464779|1.023862625|30/0/42|eval_069_random_hotspot|
|final|NoPeriodicPrefetch|physical|72/0|1.001155277|1.000000000|1.005465300|1.023652579|21/16/35|eval_069_random_hotspot|
|final|NoNextProtection|C|72/0|1.003855377|1.000368668|1.015251568|1.104193618|25/0/47|eval_016_random_hotspot|
|final|NoNextProtection|physical|72/0|1.003889643|1.000368885|1.015251791|1.104194268|10/24/38|eval_016_random_hotspot|
|final|UnitMissCost|C|72/0|1.107041861|1.037563661|1.381649006|2.358820368|20/0/52|eval_039_random_lognormal|
|final|UnitMissCost|physical|72/0|1.107249487|1.037953932|1.382321009|2.362486453|20/0/52|eval_039_random_lognormal|
|final|NoStructurePolicy|C|72/0|0.999992505|0.999999734|1.000034615|1.000401538|43/0/29|eval_069_random_hotspot|
|final|NoStructurePolicy|physical|72/0|1.000000000|1.000000000|1.000000000|1.000000000|0/72/0|eval_000_random_hotspot, eval_003_random_zipf, eval_004_random_zipf, eval_005_random_lognormal, eval_006_random_hotspot, eval_008_random_zipf, eval_009_random_lognormal, eval_011_random_zipf, eval_013_random_lognormal, eval_014_random_hotspot, eval_015_random_hotspot, eval_016_random_hotspot, eval_017_random_lognormal, eval_018_random_hotspot, eval_019_random_hotspot, eval_022_random_hotspot, eval_023_random_hotspot, eval_024_random_zipf, eval_025_random_zipf, eval_026_random_hotspot, eval_027_random_hotspot, eval_028_random_zipf, eval_029_random_zipf, eval_031_random_zipf, eval_033_random_zipf, eval_034_random_lognormal, eval_036_random_lognormal, eval_038_random_zipf, eval_039_random_lognormal, eval_040_random_hotspot, eval_042_random_hotspot, eval_043_random_hotspot, eval_044_random_zipf, eval_045_random_lognormal, eval_046_random_zipf, eval_047_random_zipf, eval_050_random_zipf, eval_051_random_zipf, eval_052_random_zipf, eval_053_random_zipf, eval_054_random_zipf, eval_055_random_zipf, eval_056_random_zipf, eval_057_random_zipf, eval_058_random_zipf, eval_059_random_zipf, eval_060_random_zipf, eval_061_random_zipf, eval_062_random_zipf, eval_063_random_zipf, eval_064_random_hotspot, eval_065_random_hotspot, eval_066_random_hotspot, eval_067_random_hotspot, eval_068_random_hotspot, eval_069_random_hotspot, eval_070_random_hotspot, eval_071_random_hotspot, eval_072_random_hotspot, eval_073_random_hotspot, eval_074_random_hotspot, eval_075_random_hotspot, eval_076_random_hotspot, eval_077_random_hotspot, eval_078_random_lognormal, eval_079_random_lognormal, eval_080_random_lognormal, eval_081_random_lognormal, eval_082_random_lognormal, eval_083_random_lognormal, eval_084_random_lognormal, eval_085_random_lognormal|
|final|UniformOperatorMarginal|C|72/0|1.015308019|1.000109420|1.048096280|1.581177009|29/0/43|eval_061_random_zipf|
|final|UniformOperatorMarginal|physical|72/0|1.015323594|1.000110737|1.048088336|1.581186338|20/15/37|eval_061_random_zipf|
|stat|Naive|C|10/0|1.701623656|1.528780705|2.050766526|3.200466508|0/0/10|eval_05_hotspot_slow_shared|
|stat|Naive|physical|10/0|1.701697924|1.528783015|2.050797179|3.200477093|0/0/10|eval_05_hotspot_slow_shared|
|stat|Full|C|10/0|1.000000000|1.000000000|1.000000000|1.000000000|0/10/0|eval_00_uniform_static_staggered, eval_01_uniform_fast_staggered, eval_02_zipf_slow_shared, eval_03_zipf_burst_shared, eval_04_hotspot_fast_staggered, eval_05_hotspot_slow_shared, eval_06_lognormal_burst_shared, eval_07_lognormal_static_shared, eval_08_mixed_mixed_shared, eval_09_mixed_mixed_staggered|
|stat|Full|physical|10/0|1.000000000|1.000000000|1.000000000|1.000000000|0/10/0|eval_00_uniform_static_staggered, eval_01_uniform_fast_staggered, eval_02_zipf_slow_shared, eval_03_zipf_burst_shared, eval_04_hotspot_fast_staggered, eval_05_hotspot_slow_shared, eval_06_lognormal_burst_shared, eval_07_lognormal_static_shared, eval_08_mixed_mixed_shared, eval_09_mixed_mixed_staggered|
|stat|FixedShare075|C|10/0|1.009567710|1.007893059|1.028864499|1.066642334|3/0/7|eval_05_hotspot_slow_shared|
|stat|FixedShare075|physical|10/0|1.009570740|1.007893138|1.028864418|1.066645396|3/0/7|eval_05_hotspot_slow_shared|
|stat|UnifiedSlow2048|C|10/0|0.991844011|0.997947278|0.999999984|1.009424256|9/0/1|eval_09_mixed_mixed_staggered|
|stat|UnifiedSlow2048|physical|10/0|0.991847627|0.997947481|1.000000000|1.009432163|6/3/1|eval_09_mixed_mixed_staggered|
|stat|NoPeriodicPrefetch|C|10/0|0.999215876|0.999469035|1.000176762|1.001117856|7/0/3|eval_05_hotspot_slow_shared|
|stat|NoPeriodicPrefetch|physical|10/0|0.999218913|0.999467016|1.000176099|1.001120689|7/0/3|eval_05_hotspot_slow_shared|
|stat|NoNextProtection|C|10/0|1.002790555|1.000433657|1.007035621|1.013501056|3/0/7|eval_08_mixed_mixed_shared|
|stat|NoNextProtection|physical|10/0|1.002795705|1.000433942|1.007038498|1.013501068|2/1/7|eval_08_mixed_mixed_shared|
|stat|UnitMissCost|C|10/0|1.145914067|1.092182468|1.250494772|1.303589604|0/0/10|eval_07_lognormal_static_shared|
|stat|UnitMissCost|physical|10/0|1.145968424|1.092183134|1.250615139|1.303598933|0/0/10|eval_07_lognormal_static_shared|
|stat|NoStructurePolicy|C|10/0|1.000022295|1.000000031|1.000000683|1.000229622|4/0/6|eval_09_mixed_mixed_staggered|
|stat|NoStructurePolicy|physical|10/0|1.000000000|1.000000000|1.000000000|1.000000000|0/10/0|eval_00_uniform_static_staggered, eval_01_uniform_fast_staggered, eval_02_zipf_slow_shared, eval_03_zipf_burst_shared, eval_04_hotspot_fast_staggered, eval_05_hotspot_slow_shared, eval_06_lognormal_burst_shared, eval_07_lognormal_static_shared, eval_08_mixed_mixed_shared, eval_09_mixed_mixed_staggered|
|stat|UniformOperatorMarginal|C|10/0|1.020687761|1.000000745|1.023254879|1.164040802|4/0/6|eval_02_zipf_slow_shared|
|stat|UniformOperatorMarginal|physical|10/0|1.020692418|1.000000000|1.023252928|1.164064351|2/3/5|eval_02_zipf_slow_shared|

## 8. 分族与原始split

完整family、原train/dev/holdout标签统计见../r81_ablation_20261031/REVIEWED_GROUPS.csv，保持每套内部均值；其数据没有回流训练。dyna原holdout已暴露，不能当成未见测试。主表不混其他成员数据、final新版本或BUILD实验。

## 9. 逐例完整表（846行）

每个方法/用例一行，失败原格不用于下表；stat case09九行统一来自恢复批。C、IO、惩罚项、D显示单位10^6微秒，计算使用原stdout全值；原精度及全部delta字段保存在../r81_ablation_20261031/REVIEWED_PER_CASE.csv。raw与比值未定义显示“—”。

|数据集|用例|方法|批次|score|raw points|C|C/Full|IO|penalty×Miss|D|physical/Full|
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|dyna|dev_burst_staggered_09|Naive|original|0.000000000|0.000000000|322429.919943|1.296905104|322310.567439|118.881800|0.470704|1.296908687|
|dyna|dev_burst_staggered_09|Full|original|2.289335613|2.289335613|248614.890097|1.000000000|248471.520627|142.319800|1.049670|1.000000000|
|dyna|dev_burst_staggered_09|FixedShare075|original|2.295735124|2.295735124|248408.550715|0.999170044|248265.355640|142.196100|0.998975|0.999170245|
|dyna|dev_burst_staggered_09|UnifiedSlow2048|original|2.290966164|2.290966164|248562.316270|0.999788533|248419.384165|141.944200|0.987905|0.999788781|
|dyna|dev_burst_staggered_09|NoPeriodicPrefetch|original|2.291209811|2.291209811|248554.460334|0.999756934|248411.183989|142.299200|0.977145|0.999757225|
|dyna|dev_burst_staggered_09|NoNextProtection|original|2.162396025|2.162396025|252707.802234|1.016462860|252562.645432|144.196400|0.960402|1.016463289|
|dyna|dev_burst_staggered_09|UnitMissCost|original|0.314179856|0.314179856|312299.821352|1.256158958|312182.682364|115.861100|1.277888|1.256159122|
|dyna|dev_burst_staggered_09|NoStructurePolicy|original|2.289337659|2.289337659|248614.824140|0.999999735|248471.520627|142.319800|0.983713|1.000000000|
|dyna|dev_burst_staggered_09|UniformOperatorMarginal|original|1.216931768|1.216931768|283192.398699|1.139080602|283057.478423|133.674400|1.245877|1.139080400|
|dyna|dev_fast_shared_08|Naive|original|0.000000000|0.000000000|191836.481148|1.393645444|191567.027150|266.021700|3.432298|1.393664447|
|dyna|dev_fast_shared_08|Full|original|2.824573821|2.824573821|137650.850896|1.000000000|137452.233356|194.277800|4.339740|1.000000000|
|dyna|dev_fast_shared_08|FixedShare075|original|2.823532014|2.823532014|137670.836559|1.000145191|137472.443494|194.307300|4.085764|1.000147041|
|dyna|dev_fast_shared_08|UnifiedSlow2048|original|2.289940585|2.289940585|147907.066760|1.074508917|147694.079676|208.634200|4.352884|1.074511171|
|dyna|dev_fast_shared_08|NoPeriodicPrefetch|original|2.822709108|2.822709108|137686.622899|1.000259875|137488.114030|194.383000|4.125869|1.000261437|
|dyna|dev_fast_shared_08|NoNextProtection|original|2.814062682|2.814062682|137852.492882|1.001464880|137653.790885|194.567800|4.134197|1.001466420|
|dyna|dev_fast_shared_08|UnitMissCost|original|2.814200877|2.814200877|137849.841798|1.001445621|137652.030808|193.782800|4.028189|1.001447930|
|dyna|dev_fast_shared_08|NoStructurePolicy|original|2.824588400|2.824588400|137650.571204|0.999997968|137452.233356|194.277800|4.060049|1.000000000|
|dyna|dev_fast_shared_08|UniformOperatorMarginal|original|0.000000000|-0.183783296|195362.115237|1.419258319|195080.437551|275.754000|5.923686|1.419260030|
|dyna|dev_slow_staggered_07|Naive|original|0.000000000|0.000000000|20275.717646|2.228910902|20077.061673|195.040900|3.615073|2.229281359|
|dyna|dev_slow_staggered_07|Full|original|5.513503931|5.513503931|9096.692752|1.000000000|8992.742251|100.817200|3.133301|1.000000000|
|dyna|dev_slow_staggered_07|FixedShare075|original|5.523899279|5.523899279|9075.615437|0.997682970|8972.120959|100.576400|2.918078|0.997705839|
|dyna|dev_slow_staggered_07|UnifiedSlow2048|original|5.263645040|5.263645040|9603.299584|1.055691321|9493.981450|106.175400|3.142734|1.055709472|
|dyna|dev_slow_staggered_07|NoPeriodicPrefetch|original|5.514155868|5.514155868|9095.370903|0.999854689|8991.483720|100.861600|3.025583|0.999866485|
|dyna|dev_slow_staggered_07|NoNextProtection|original|5.510257985|5.510257985|9103.274139|1.000723492|8999.299270|100.879800|3.095069|1.000727946|
|dyna|dev_slow_staggered_07|UnitMissCost|original|5.309794488|5.309794488|9509.728265|1.045405020|9409.717330|96.964800|3.046135|1.045430250|
|dyna|dev_slow_staggered_07|NoStructurePolicy|original|5.513504653|5.513504653|9096.691288|0.999999839|8992.742251|100.817200|3.131838|1.000000000|
|dyna|dev_slow_staggered_07|UniformOperatorMarginal|original|0.081659603|0.081659603|20110.146941|2.210709704|19880.815914|222.293400|7.037627|2.210697519|
|dyna|holdout_burst_shared_12|Naive|original|0.000000000|0.000000000|1143122.663518|8.568244756|1142915.672299|204.065200|2.926019|8.568388729|
|dyna|holdout_burst_shared_12|Full|original|8.832899820|8.832899820|133413.866671|1.000000000|133312.225150|99.058300|2.583221|1.000000000|
|dyna|holdout_burst_shared_12|FixedShare075|original|8.824149878|8.824149878|134414.092347|1.007497164|134319.696049|91.889400|2.506898|1.007497882|
|dyna|holdout_burst_shared_12|UnifiedSlow2048|original|8.851237701|8.851237701|131317.621853|0.984287654|131220.559496|94.475400|2.586957|0.984287322|
|dyna|holdout_burst_shared_12|NoPeriodicPrefetch|original|8.832331422|8.832331422|133478.841554|1.000487017|133377.047030|99.120200|2.674325|1.000486344|
|dyna|holdout_burst_shared_12|NoNextProtection|original|8.831389746|8.831389746|133586.486624|1.001293868|133484.624589|99.174500|2.687535|1.001293111|
|dyna|holdout_burst_shared_12|UnitMissCost|original|8.740286972|8.740286972|144000.651144|1.079352954|143909.763718|88.083400|2.804026|1.079352836|
|dyna|holdout_burst_shared_12|NoStructurePolicy|original|8.832900065|8.832900065|133413.838643|0.999999790|133312.225150|99.058300|2.555193|1.000000000|
|dyna|holdout_burst_shared_12|UniformOperatorMarginal|original|7.456075741|7.456075741|290801.747451|2.179696569|290586.649521|209.550700|5.547230|2.179697194|
|dyna|holdout_fast_staggered_11|Naive|original|0.000000000|0.000000000|22870.352788|2.798451676|22761.095363|108.433600|0.823824|2.798607942|
|dyna|holdout_fast_staggered_11|Full|original|6.426595433|6.426595433|8172.502310|1.000000000|8124.876413|46.875200|0.750697|1.000000000|
|dyna|holdout_fast_staggered_11|FixedShare075|original|6.433879337|6.433879337|8155.843764|0.997961634|8108.361758|46.815600|0.666406|0.997971762|
|dyna|holdout_fast_staggered_11|UnifiedSlow2048|original|5.941490213|5.941490213|9281.955063|1.135754352|9228.058088|53.140900|0.756075|1.135766165|
|dyna|holdout_fast_staggered_11|NoPeriodicPrefetch|original|6.425871745|6.425871745|8174.157411|1.000202521|8126.490684|46.904400|0.762327|1.000201116|
|dyna|holdout_fast_staggered_11|NoNextProtection|original|6.423112306|6.423112306|8180.468345|1.000974736|8132.799859|46.928400|0.740086|1.000976124|
|dyna|holdout_fast_staggered_11|UnitMissCost|original|6.158468849|6.158468849|8785.717267|1.075033929|8738.764688|46.143400|0.809179|1.075033665|
|dyna|holdout_fast_staggered_11|NoStructurePolicy|original|6.426604380|6.426604380|8172.481849|0.999997496|8124.876413|46.875200|0.730235|1.000000000|
|dyna|holdout_fast_staggered_11|UniformOperatorMarginal|original|1.740235974|1.740235974|18890.371721|2.311455048|18781.788031|106.907000|1.676690|2.311462208|
|dyna|holdout_slow_shared_10|Naive|original|0.000000000|0.000000000|1518469.848060|1.229115879|1518204.729179|262.548500|2.570382|1.229117077|
|dyna|holdout_slow_shared_10|Full|original|1.864070613|1.864070613|1235416.346027|1.000000000|1235194.446541|218.603900|3.295585|1.000000000|
|dyna|holdout_slow_shared_10|FixedShare075|original|1.861481921|1.861481921|1235809.431144|1.000318180|1235587.663802|218.674100|3.093242|1.000318345|
|dyna|holdout_slow_shared_10|UnifiedSlow2048|original|1.789552021|1.789552021|1246731.769488|1.009159198|1246508.030625|220.447200|3.291664|1.009159226|
|dyna|holdout_slow_shared_10|NoPeriodicPrefetch|original|1.864093909|1.864093909|1235412.808549|0.999997137|1235190.954972|218.642000|3.211577|0.999997205|
|dyna|holdout_slow_shared_10|NoNextProtection|original|1.845153184|1.845153184|1238288.900535|1.002325171|1238066.551361|219.116700|3.232474|1.002325228|
|dyna|holdout_slow_shared_10|UnitMissCost|original|1.838594396|1.838594396|1239284.832803|1.003131322|1239064.847938|216.692800|3.292065|1.003131334|
|dyna|holdout_slow_shared_10|NoStructurePolicy|original|1.864070232|1.864070232|1235416.403857|1.000000047|1235194.446541|218.603900|3.353415|1.000000000|
|dyna|holdout_slow_shared_10|UniformOperatorMarginal|original|0.000000000|-0.472246766|1590179.095498|1.287160479|1589890.462710|284.441800|4.190988|1.287160520|
|dyna|train_burst_shared_05|Naive|original|0.000000000|0.000000000|651954.183151|1.429221410|651745.318021|205.887100|2.978030|1.429225231|
|dyna|train_burst_shared_05|Full|original|3.003183463|3.003183463|456160.381027|1.000000000|456000.680541|156.397500|3.302986|1.000000000|
|dyna|train_burst_shared_05|FixedShare075|original|3.005067171|3.005067171|456037.571882|0.999730776|455878.033891|156.327600|3.210390|0.999730977|
|dyna|train_burst_shared_05|UnifiedSlow2048|original|3.040130579|3.040130579|453751.598324|0.994719439|453594.107127|154.313000|3.178197|0.994719674|
|dyna|train_burst_shared_05|NoPeriodicPrefetch|original|3.000284835|3.000284835|456349.358286|1.000414278|456189.582684|156.484900|3.290702|1.000414308|
|dyna|train_burst_shared_05|NoNextProtection|original|2.993117218|2.993117218|456816.654090|1.001438689|456656.775209|156.620900|3.257981|1.001438798|
|dyna|train_burst_shared_05|UnitMissCost|original|2.776444210|2.776444210|470942.741478|1.032406060|470796.613726|142.978400|3.149352|1.032406631|
|dyna|train_burst_shared_05|NoStructurePolicy|original|3.003182775|3.003182775|456160.425861|1.000000098|456000.680541|156.397500|3.347820|1.000000000|
|dyna|train_burst_shared_05|UniformOperatorMarginal|original|0.000000000|-1.823154694|770815.516066|1.689790583|770514.903301|294.992600|5.620164|1.689790498|
|dyna|train_burst_staggered_06|Naive|original|0.000000000|0.000000000|67612.490351|2.234815545|67365.775054|243.845300|2.869997|2.234886406|
|dyna|train_burst_staggered_06|Full|original|5.525357776|5.525357776|30254.170419|1.000000000|30086.671473|165.255500|2.243446|1.000000000|
|dyna|train_burst_staggered_06|FixedShare075|original|5.524612876|5.524612876|30259.206877|1.000166472|30091.648470|165.315000|2.243407|1.000166485|
|dyna|train_burst_staggered_06|UnifiedSlow2048|original|5.528379796|5.528379796|30233.737792|0.999324634|30067.140124|164.362700|2.234968|0.999324865|
|dyna|train_burst_staggered_06|NoPeriodicPrefetch|original|5.522492715|5.522492715|30273.541811|1.000640288|30105.971085|165.331200|2.239526|1.000640465|
|dyna|train_burst_staggered_06|NoNextProtection|original|5.510684471|5.510684471|30353.380286|1.003279213|30185.306805|165.876000|2.197481|1.003280976|
|dyna|train_burst_staggered_06|UnitMissCost|original|4.610091955|4.610091955|36442.510570|1.204545028|36294.746390|145.265700|2.498480|1.204551767|
|dyna|train_burst_staggered_06|NoStructurePolicy|original|5.525352183|5.525352183|30254.208237|1.000001250|30086.671473|165.255500|2.281263|1.000000000|
|dyna|train_burst_staggered_06|UniformOperatorMarginal|original|1.610501953|1.610501953|56723.485573|1.874898065|56462.542942|256.629900|4.312731|1.874894544|
|dyna|train_fast_shared_03|Naive|original|0.000000000|0.000000000|320508.256233|1.289788331|320285.813604|221.362900|1.079729|1.289792549|
|dyna|train_fast_shared_03|Full|original|2.246789834|2.246789834|248496.787039|1.000000000|248319.663998|175.473200|1.649841|1.000000000|
|dyna|train_fast_shared_03|FixedShare075|original|2.247222295|2.247222295|248482.926335|0.999944222|248305.840759|175.465900|1.619676|0.999944343|
|dyna|train_fast_shared_03|UnifiedSlow2048|original|2.177636214|2.177636214|250713.217656|1.008919353|250534.376020|177.009100|1.832536|1.008918677|
|dyna|train_fast_shared_03|NoPeriodicPrefetch|original|2.245962332|2.245962332|248523.309158|1.000106730|248345.852013|175.504700|1.952444|1.000105513|
|dyna|train_fast_shared_03|NoNextProtection|original|2.205137347|2.205137347|249831.783634|1.005372289|249653.458315|176.415300|1.910019|1.005371278|
|dyna|train_fast_shared_03|UnitMissCost|original|2.246536917|2.246536917|248504.893243|1.000032621|248327.952733|174.944200|1.996310|1.000031227|
|dyna|train_fast_shared_03|NoStructurePolicy|original|2.246775419|2.246775419|248497.249078|1.000001859|248319.663998|175.473200|2.111880|1.000000000|
|dyna|train_fast_shared_03|UniformOperatorMarginal|original|0.000000000|-0.504213551|336668.716849|1.354821207|336427.636284|238.743000|2.337564|1.354820795|
|dyna|train_fast_staggered_04|Naive|original|0.000000000|0.000000000|1487544.788970|1.202373624|1487279.620268|262.346100|2.822602|1.202374948|
|dyna|train_fast_staggered_04|Full|original|1.683117626|1.683117626|1237173.503642|1.000000000|1236948.375880|221.417700|3.710063|1.000000000|
|dyna|train_fast_staggered_04|FixedShare075|original|1.682216146|1.682216146|1237307.602774|1.000108392|1237082.913138|221.436400|3.253237|1.000108761|
|dyna|train_fast_staggered_04|UnifiedSlow2048|original|1.369492565|1.369492565|1283826.636042|1.037709450|1283591.904385|230.038600|4.693057|1.037708769|
|dyna|train_fast_staggered_04|NoPeriodicPrefetch|original|1.681840064|1.681840064|1237363.546653|1.000153611|1237138.652093|221.640400|3.254161|1.000153980|
|dyna|train_fast_staggered_04|NoNextProtection|original|1.667042749|1.667042749|1239564.713562|1.001932801|1239339.892333|221.854700|2.966528|1.001933408|
|dyna|train_fast_staggered_04|UnitMissCost|original|1.654254184|1.654254184|1241467.069895|1.003470464|1241244.846524|219.067800|3.155572|1.003470923|
|dyna|train_fast_staggered_04|NoStructurePolicy|original|1.683120321|1.683120321|1237173.102714|0.999999676|1236948.375880|221.417700|3.309135|1.000000000|
|dyna|train_fast_staggered_04|UniformOperatorMarginal|original|0.020478437|0.020478437|1484498.529745|1.199911351|1484226.182270|268.149300|4.198175|1.199911556|
|dyna|train_slow_shared_01|Naive|original|0.000000000|0.000000000|111539.371742|14.452661636|111394.624986|144.033500|0.713256|14.454417532|
|dyna|train_slow_shared_01|Full|original|9.308085926|9.308085926|7717.566117|1.000000000|7661.561756|55.017500|0.986861|1.000000000|
|dyna|train_slow_shared_01|FixedShare075|original|9.321019167|9.321019167|7573.309553|0.981308024|7523.087652|49.508800|0.713101|0.981341110|
|dyna|train_slow_shared_01|UnifiedSlow2048|original|9.328845568|9.328845568|7486.014372|0.969996792|7434.225069|51.082400|0.706902|0.970029235|
|dyna|train_slow_shared_01|NoPeriodicPrefetch|original|9.308392122|9.308392122|7714.150818|0.999557464|7658.393116|54.970400|0.787302|0.999583269|
|dyna|train_slow_shared_01|NoNextProtection|original|9.306727191|9.306727191|7732.721359|1.001963733|7676.853085|55.110000|0.758274|1.001993607|
|dyna|train_slow_shared_01|UnitMissCost|original|9.256654175|9.256654175|8291.232628|1.074332568|8238.060532|52.414000|0.758096|1.074371720|
|dyna|train_slow_shared_01|NoStructurePolicy|original|9.308102926|9.308102926|7717.376494|0.999975430|7661.561756|55.017500|0.797238|1.000000000|
|dyna|train_slow_shared_01|UniformOperatorMarginal|original|8.585179539|8.585179539|15780.818539|2.044792140|15668.726836|110.446700|1.645003|2.044840468|
|dyna|train_slow_staggered_02|Naive|original|0.000000000|0.000000000|192717.747729|1.653625076|192457.129469|257.338300|3.279960|1.653645635|
|dyna|train_slow_staggered_02|Full|original|3.952679996|3.952679996|116542.589101|1.000000000|116374.295998|164.860700|3.432403|1.000000000|
|dyna|train_slow_staggered_02|FixedShare075|original|3.953395242|3.953395242|116528.805044|0.999881725|116360.795758|164.843800|3.165486|0.999884012|
|dyna|train_slow_staggered_02|UnifiedSlow2048|original|3.809474676|3.809474676|119302.409775|1.023680791|119130.124931|168.736300|3.548544|1.023680492|
|dyna|train_slow_staggered_02|NoPeriodicPrefetch|original|3.952524343|3.952524343|116545.588803|1.000025739|116377.363088|164.903400|3.322315|1.000026685|
|dyna|train_slow_staggered_02|NoNextProtection|original|3.945166928|3.945166928|116687.379246|1.001242380|116519.082302|165.073500|3.223445|1.001244209|
|dyna|train_slow_staggered_02|UnitMissCost|original|3.876779135|3.876779135|118005.333396|1.012551157|117839.664137|162.318300|3.350959|1.012552225|
|dyna|train_slow_staggered_02|NoStructurePolicy|original|3.952689360|3.952689360|116542.408627|0.999998451|116374.295998|164.860700|3.251929|1.000000000|
|dyna|train_slow_staggered_02|UniformOperatorMarginal|original|0.000000000|-0.092330598|194497.122220|1.668893095|194217.422626|274.287200|5.412393|1.668895806|
|final|eval_000_random_hotspot|Naive|original|0.000000000|0.000000000|110.068705|3.497637826|108.213358|1.704050|0.151296|3.499797561|
|final|eval_000_random_hotspot|Full|original|7.140927535|7.140927535|31.469440|1.000000000|30.553340|0.853450|0.062650|1.000000000|
|final|eval_000_random_hotspot|FixedShare075|original|7.173320667|7.173320667|31.112893|0.988670056|30.309935|0.744225|0.058733|0.988772166|
|final|eval_000_random_hotspot|UnifiedSlow2048|original|7.152765287|7.152765287|31.339144|0.995859583|30.439325|0.843975|0.055844|0.996068020|
|final|eval_000_random_hotspot|NoPeriodicPrefetch|original|7.143255802|7.143255802|31.443813|0.999185657|30.528403|0.855050|0.060360|0.999256940|
|final|eval_000_random_hotspot|NoNextProtection|original|7.142985455|7.142985455|31.446789|0.999280214|30.541131|0.853250|0.052408|0.999604877|
|final|eval_000_random_hotspot|UnitMissCost|original|7.033530306|7.033530306|32.651548|1.037563661|31.977327|0.621475|0.052746|1.037953932|
|final|eval_000_random_hotspot|NoStructurePolicy|original|7.141559549|7.141559549|31.462484|0.999778945|30.553340|0.853450|0.055693|1.000000000|
|final|eval_000_random_hotspot|UniformOperatorMarginal|original|7.150874414|7.150874414|31.359956|0.996520942|30.447093|0.854625|0.058238|0.996654479|
|final|eval_003_random_zipf|Naive|original|0.000000000|0.000000000|10.843709|1.060433114|10.806433|0.036738|0.000538|1.060561829|
|final|eval_003_random_zipf|Full|original|0.569890864|0.569890864|10.225736|1.000000000|10.100123|0.123864|0.001748|1.000000000|
|final|eval_003_random_zipf|FixedShare075|original|0.959771073|0.959771073|9.802961|0.958655812|9.736877|0.064818|0.001266|0.958695900|
|final|eval_003_random_zipf|UnifiedSlow2048|original|1.046445304|1.046445304|9.708974|0.949464589|9.622570|0.084864|0.001540|0.949476316|
|final|eval_003_random_zipf|NoPeriodicPrefetch|original|0.585823439|0.585823439|10.208459|0.998310457|10.081970|0.124878|0.001611|0.998323630|
|final|eval_003_random_zipf|NoNextProtection|original|0.570022747|0.570022747|10.225593|0.999986015|10.100123|0.123864|0.001605|1.000000000|
|final|eval_003_random_zipf|UnitMissCost|original|0.070277847|0.070277847|10.767501|1.052980619|10.730069|0.036348|0.001084|1.053054614|
|final|eval_003_random_zipf|NoStructurePolicy|original|0.570054526|0.570054526|10.225558|0.999982645|10.100123|0.123864|0.001571|1.000000000|
|final|eval_003_random_zipf|UniformOperatorMarginal|original|0.246391035|0.246391035|10.576529|1.034304993|10.426013|0.148746|0.001770|1.034308720|
|final|eval_004_random_zipf|Naive|original|0.000000000|0.000000000|734.437719|1.110539227|725.991220|8.444088|0.002411|1.110544604|
|final|eval_004_random_zipf|Full|original|0.995365357|0.995365357|661.334333|1.000000000|653.139848|8.189112|0.005373|1.000000000|
|final|eval_004_random_zipf|FixedShare075|original|0.879271985|0.879271985|669.860668|1.012892624|661.347124|8.508828|0.004716|1.012893722|
|final|eval_004_random_zipf|UnifiedSlow2048|original|0.942527086|0.942527086|665.214975|1.005867897|656.951822|8.257338|0.005815|1.005867277|
|final|eval_004_random_zipf|NoPeriodicPrefetch|original|0.995331390|0.995331390|661.336827|1.000003772|653.139848|8.191602|0.005377|1.000003765|
|final|eval_004_random_zipf|NoNextProtection|original|0.975432569|0.975432569|662.798272|1.002213614|654.420906|8.371878|0.005488|1.002213458|
|final|eval_004_random_zipf|UnitMissCost|original|0.967371844|0.967371844|663.390282|1.003108789|656.036967|7.348488|0.004827|1.003109640|
|final|eval_004_random_zipf|NoStructurePolicy|original|0.995367355|0.995367355|661.334186|0.999999778|653.139848|8.189112|0.005226|1.000000000|
|final|eval_004_random_zipf|UniformOperatorMarginal|original|0.950681633|0.950681633|664.616074|1.004962303|656.259347|8.350962|0.005764|1.004961751|
|final|eval_005_random_lognormal|Naive|original|0.000000000|0.000000000|24.910560|3.163296604|23.036676|1.811328|0.062556|3.165243831|
|final|eval_005_random_lognormal|Full|original|6.838740956|6.838740956|7.874873|1.000000000|6.508954|1.341312|0.024608|1.000000000|
|final|eval_005_random_lognormal|FixedShare075|original|6.491253851|6.491253851|8.740483|1.109920478|7.584800|1.124544|0.031139|1.109433101|
|final|eval_005_random_lognormal|UnifiedSlow2048|original|6.870216663|6.870216663|7.796466|0.990043300|6.511048|1.262016|0.023402|0.990165752|
|final|eval_005_random_lognormal|NoPeriodicPrefetch|original|6.825562208|6.825562208|7.907702|1.004168829|6.561362|1.321536|0.024805|1.004156815|
|final|eval_005_random_lognormal|NoNextProtection|original|6.839574048|6.839574048|7.872798|0.999736468|6.508954|1.341312|0.022533|1.000000000|
|final|eval_005_random_lognormal|UnitMissCost|original|5.072015656|5.072015656|12.275885|1.558867614|11.388092|0.866496|0.021297|1.561041270|
|final|eval_005_random_lognormal|NoStructurePolicy|original|6.838952605|6.838952605|7.874346|0.999933049|6.508954|1.341312|0.024081|1.000000000|
|final|eval_005_random_lognormal|UniformOperatorMarginal|original|6.678973309|6.678973309|8.272864|1.050539245|6.875993|1.371648|0.025223|1.050619345|
|final|eval_006_random_hotspot|Naive|original|0.000000000|0.000000000|4.500893|0.907013462|3.859677|0.640780|0.000435|0.907327589|
|final|eval_006_random_hotspot|Full|original|0.000000000|-1.025194686|4.962322|1.000000000|3.856868|1.103256|0.002198|1.000000000|
|final|eval_006_random_hotspot|FixedShare075|original|0.000000000|-0.640073399|4.788983|0.965068981|3.830309|0.956792|0.001882|0.965117088|
|final|eval_006_random_hotspot|UnifiedSlow2048|original|0.000000000|-1.025335925|4.962385|1.000012811|3.856868|1.103256|0.002261|1.000000000|
|final|eval_006_random_hotspot|NoPeriodicPrefetch|original|0.000000000|-1.024812429|4.962150|0.999965329|3.856868|1.103256|0.002026|1.000000000|
|final|eval_006_random_hotspot|NoNextProtection|original|0.000000000|-1.025192576|4.962321|0.999999809|3.856868|1.103256|0.002197|1.000000000|
|final|eval_006_random_hotspot|UnitMissCost|original|0.000000000|-0.229359055|4.604125|0.927816637|3.902472|0.700082|0.001571|0.927911045|
|final|eval_006_random_hotspot|NoStructurePolicy|original|0.000000000|-1.024919074|4.962198|0.999975002|3.856868|1.103256|0.002074|1.000000000|
|final|eval_006_random_hotspot|UniformOperatorMarginal|original|0.000000000|-1.024670990|4.962086|0.999952500|3.856868|1.103256|0.001962|1.000000000|
|final|eval_008_random_zipf|Naive|original|0.000000000|0.000000000|53.801459|1.531351352|53.132620|0.667446|0.001393|1.531422081|
|final|eval_008_random_zipf|Full|original|3.469819983|3.469819983|35.133322|1.000000000|34.093629|1.037160|0.002532|1.000000000|
|final|eval_008_random_zipf|FixedShare075|original|2.648962230|2.648962230|39.549656|1.125702163|38.493846|1.052640|0.003170|1.125693062|
|final|eval_008_random_zipf|UnifiedSlow2048|original|2.890979921|2.890979921|38.247566|1.088640751|37.293520|0.951762|0.002283|1.088654228|
|final|eval_008_random_zipf|NoPeriodicPrefetch|original|3.447086909|3.447086909|35.255629|1.003481232|34.233992|1.019100|0.002537|1.003481358|
|final|eval_008_random_zipf|NoNextProtection|original|3.470523897|3.470523897|35.129534|0.999892206|34.087613|1.039224|0.002697|0.999887516|
|final|eval_008_random_zipf|UnitMissCost|original|1.873991734|1.873991734|43.719110|1.244377375|43.106001|0.611460|0.001650|1.244420116|
|final|eval_008_random_zipf|NoStructurePolicy|original|3.469765015|3.469765015|35.133617|1.000008418|34.093629|1.037160|0.002828|1.000000000|
|final|eval_008_random_zipf|UniformOperatorMarginal|original|3.425273551|3.425273551|35.372988|1.006821624|34.254251|1.115850|0.002887|1.006812015|
|final|eval_009_random_lognormal|Naive|original|0.000000000|0.000000000|3084.157840|1.089023886|3066.243436|17.909760|0.004644|1.089026157|
|final|eval_009_random_lognormal|Full|original|0.817464952|0.817464952|2832.038746|1.000000000|2815.754608|16.273968|0.010170|1.000000000|
|final|eval_009_random_lognormal|FixedShare075|original|0.814215480|0.814215480|2833.040935|1.000353875|2816.742977|16.289232|0.008725|1.000354387|
|final|eval_009_random_lognormal|UnifiedSlow2048|original|0.817467884|0.817467884|2832.037842|0.999999681|2815.754608|16.273968|0.009265|1.000000000|
|final|eval_009_random_lognormal|NoPeriodicPrefetch|original|0.817446732|0.817446732|2832.044365|1.000001984|2815.754608|16.280328|0.009429|1.000002246|
|final|eval_009_random_lognormal|NoNextProtection|original|0.776098242|0.776098242|2844.796892|1.004504933|2828.287619|16.500808|0.008465|1.004505552|
|final|eval_009_random_lognormal|UnitMissCost|original|0.842696940|0.842696940|2824.256803|0.997252176|2808.118253|16.129808|0.008742|0.997252671|
|final|eval_009_random_lognormal|NoStructurePolicy|original|0.817470803|0.817470803|2832.036941|0.999999363|2815.754608|16.273968|0.008365|1.000000000|
|final|eval_009_random_lognormal|UniformOperatorMarginal|original|0.817468621|0.817468621|2832.037614|0.999999600|2815.754608|16.273968|0.009038|1.000000000|
|final|eval_011_random_zipf|Naive|original|0.000000000|0.000000000|605.853898|1.214280862|601.748025|4.104275|0.001598|1.214294341|
|final|eval_011_random_zipf|Full|original|1.764672977|1.764672977|498.940498|1.000000000|492.709617|6.224027|0.006854|1.000000000|
|final|eval_011_random_zipf|FixedShare075|original|1.693536670|1.693536670|503.250319|1.008637946|496.903652|6.340294|0.006372|1.008639030|
|final|eval_011_random_zipf|UnifiedSlow2048|original|1.720388519|1.720388519|501.623489|1.005377377|495.375349|6.241492|0.006648|1.005377864|
|final|eval_011_random_zipf|NoPeriodicPrefetch|original|1.719668738|1.719668738|501.667097|1.005464779|495.424463|6.236003|0.006631|1.005465300|
|final|eval_011_random_zipf|NoNextProtection|original|1.632671476|1.632671476|506.937860|1.016028690|500.753329|6.178119|0.006412|1.016029796|
|final|eval_011_random_zipf|UnitMissCost|original|1.009005258|1.009005258|544.722921|1.091759285|540.740408|3.978527|0.003986|1.091766295|
|final|eval_011_random_zipf|NoStructurePolicy|original|1.764678150|1.764678150|498.940184|0.999999372|492.709617|6.224027|0.006541|1.000000000|
|final|eval_011_random_zipf|UniformOperatorMarginal|original|1.747421447|1.747421447|499.985688|1.002094820|493.631628|6.347280|0.006780|1.002094997|
|final|eval_013_random_lognormal|Naive|original|0.000000000|0.000000000|62.639934|2.752488544|61.893898|0.745056|0.000980|2.752728338|
|final|eval_013_random_lognormal|Full|original|6.366924025|6.366924025|22.757564|1.000000000|22.045018|0.710208|0.002338|1.000000000|
|final|eval_013_random_lognormal|FixedShare075|original|5.403756909|5.403756909|28.790836|1.265110645|27.975148|0.812880|0.002809|1.265117228|
|final|eval_013_random_lognormal|UnifiedSlow2048|original|6.467744960|6.467744960|22.126022|0.972249153|21.425529|0.697680|0.002814|0.972225413|
|final|eval_013_random_lognormal|NoPeriodicPrefetch|original|6.366877735|6.366877735|22.757854|1.000012741|22.045018|0.710352|0.002484|1.000006328|
|final|eval_013_random_lognormal|NoNextProtection|original|6.312639709|6.312639709|23.097601|1.014941696|22.353106|0.742032|0.002462|1.014937787|
|final|eval_013_random_lognormal|UnitMissCost|original|5.553304030|5.553304030|27.854074|1.223947972|27.385704|0.466560|0.001810|1.223994197|
|final|eval_013_random_lognormal|NoStructurePolicy|original|6.366884155|6.366884155|22.757814|1.000010974|22.045018|0.710208|0.002588|1.000000000|
|final|eval_013_random_lognormal|UniformOperatorMarginal|original|6.304477285|6.304477285|23.148730|1.017188394|22.453487|0.692784|0.002459|1.017184872|
|final|eval_014_random_hotspot|Naive|original|0.000000000|0.000000000|278.487190|1.365682660|273.981728|4.502526|0.002936|1.365711706|
|final|eval_014_random_hotspot|Full|original|2.677654705|2.677654705|203.917936|1.000000000|199.552648|4.358802|0.006487|1.000000000|
|final|eval_014_random_hotspot|FixedShare075|original|2.289026644|2.289026644|214.740730|1.053074261|209.907407|4.826082|0.007241|1.053072249|
|final|eval_014_random_hotspot|UnifiedSlow2048|original|2.693639748|2.693639748|203.472774|0.997816950|199.110035|4.356678|0.006061|0.997818969|
|final|eval_014_random_hotspot|NoPeriodicPrefetch|original|2.676915497|2.676915497|203.938523|1.000100952|199.568824|4.363758|0.005940|1.000103635|
|final|eval_014_random_hotspot|NoNextProtection|original|2.658468029|2.658468029|204.452261|1.002620291|200.068587|4.377918|0.005756|1.002623958|
|final|eval_014_random_hotspot|UnitMissCost|original|2.411204653|2.411204653|211.338229|1.036388622|207.966683|3.366540|0.005006|1.036397040|
|final|eval_014_random_hotspot|NoStructurePolicy|original|2.677636700|2.677636700|203.918438|1.000002459|199.552648|4.358802|0.006988|1.000000000|
|final|eval_014_random_hotspot|UniformOperatorMarginal|original|2.690686133|2.690686133|203.555028|0.998220321|199.199261|4.349244|0.006523|0.998220088|
|final|eval_015_random_hotspot|Naive|original|0.000000000|0.000000000|48.150548|9.791988125|42.026546|6.079150|0.044851|9.801739687|
|final|eval_015_random_hotspot|Full|original|8.978756931|8.978756931|4.917341|1.000000000|3.892298|1.015575|0.009468|1.000000000|
|final|eval_015_random_hotspot|FixedShare075|original|8.969380116|8.969380116|4.962491|1.009181767|3.953399|0.999625|0.009467|1.009199610|
|final|eval_015_random_hotspot|UnifiedSlow2048|original|8.972762640|8.972762640|4.946204|1.005869603|3.873674|1.064525|0.008005|1.006179017|
|final|eval_015_random_hotspot|NoPeriodicPrefetch|original|8.976865844|8.976865844|4.926447|1.001851751|3.900051|1.018325|0.008071|1.002140043|
|final|eval_015_random_hotspot|NoNextProtection|original|8.979002131|8.979002131|4.916161|0.999759901|3.892298|1.015575|0.008287|1.000000000|
|final|eval_015_random_hotspot|UnitMissCost|original|8.272665341|8.272665341|8.317211|1.691404047|7.176898|1.129700|0.010613|1.692504521|
|final|eval_015_random_hotspot|NoStructurePolicy|original|8.978896188|8.978896188|4.916671|0.999863640|3.892298|1.015575|0.008797|1.000000000|
|final|eval_015_random_hotspot|UniformOperatorMarginal|original|8.975147635|8.975147635|4.934720|1.003534219|3.908788|1.016675|0.009257|1.003583962|
|final|eval_016_random_hotspot|Naive|original|0.000000000|0.000000000|1817.749320|1.510713888|1814.043417|3.703000|0.002904|1.510717350|
|final|eval_016_random_hotspot|Full|original|3.380612912|3.380612912|1203.238638|1.000000000|1200.130958|3.103000|0.004680|1.000000000|
|final|eval_016_random_hotspot|FixedShare075|original|3.420153833|3.420153833|1196.051090|0.994026498|1192.900690|3.146200|0.004199|0.994026875|
|final|eval_016_random_hotspot|UnifiedSlow2048|original|3.400629313|3.400629313|1199.600158|0.996976095|1196.480935|3.115000|0.004223|0.996976463|
|final|eval_016_random_hotspot|NoPeriodicPrefetch|original|3.380610432|3.380610432|1203.239089|1.000000375|1200.130958|3.104000|0.004131|1.000000831|
|final|eval_016_random_hotspot|NoNextProtection|original|2.690915021|2.690915021|1328.608425|1.104193618|1325.119040|3.485000|0.004386|1.104194268|
|final|eval_016_random_hotspot|UnitMissCost|original|3.057058861|3.057058861|1262.052654|1.048879760|1259.109733|2.936400|0.006521|1.048878420|
|final|eval_016_random_hotspot|NoStructurePolicy|original|3.380613216|3.380613216|1203.238583|0.999999954|1200.130958|3.103000|0.004625|1.000000000|
|final|eval_016_random_hotspot|UniformOperatorMarginal|original|3.375562177|3.375562177|1204.156735|1.000763022|1201.045341|3.104800|0.006594|1.000761434|
|final|eval_017_random_lognormal|Naive|original|0.000000000|0.000000000|1315.143301|1.844311471|1290.377486|24.757460|0.008355|1.844346723|
|final|eval_017_random_lognormal|Full|original|4.577922354|4.577922354|713.080909|1.000000000|691.872875|21.189875|0.018159|1.000000000|
|final|eval_017_random_lognormal|FixedShare075|original|3.943841403|3.943841403|796.471641|1.116944277|772.191078|24.262994|0.017569|1.116948083|
|final|eval_017_random_lognormal|UnifiedSlow2048|original|4.577942005|4.577942005|713.078325|0.999996376|691.872875|21.189875|0.015575|1.000000000|
|final|eval_017_random_lognormal|NoPeriodicPrefetch|original|4.577015848|4.577015848|713.200128|1.000167188|691.959321|21.224462|0.016344|1.000169737|
|final|eval_017_random_lognormal|NoNextProtection|original|4.361445143|4.361445143|741.550765|1.039925140|719.599514|21.934136|0.017114|1.039927622|
|final|eval_017_random_lognormal|UnitMissCost|original|4.361250935|4.361250935|741.576306|1.039960958|723.260168|18.301647|0.014491|1.039967121|
|final|eval_017_random_lognormal|NoStructurePolicy|original|4.577943712|4.577943712|713.078100|0.999996061|691.872875|21.189875|0.015350|1.000000000|
|final|eval_017_random_lognormal|UniformOperatorMarginal|original|4.577941708|4.577941708|713.078364|0.999996430|691.872875|21.189875|0.015614|1.000000000|
|final|eval_018_random_hotspot|Naive|original|0.000000000|0.000000000|8.595767|1.125846230|8.439433|0.155652|0.000682|1.126511922|
|final|eval_018_random_hotspot|Full|original|1.117792346|1.117792346|7.634939|1.000000000|7.106766|0.523056|0.005117|1.000000000|
|final|eval_018_random_hotspot|FixedShare075|original|1.278365132|1.278365132|7.496914|0.981921973|7.111691|0.380970|0.004253|0.982023073|
|final|eval_018_random_hotspot|UnifiedSlow2048|original|1.159949549|1.159949549|7.598702|0.995253747|7.104146|0.489396|0.005160|0.995245010|
|final|eval_018_random_hotspot|NoPeriodicPrefetch|original|1.263776859|1.263776859|7.509454|0.983564389|6.998902|0.505614|0.004939|0.983576779|
|final|eval_018_random_hotspot|NoNextProtection|original|1.117720276|1.117720276|7.635001|1.000008114|7.106766|0.523056|0.005179|1.000000000|
|final|eval_018_random_hotspot|UnitMissCost|original|0.589929139|0.589929139|8.088678|1.059429280|7.909543|0.176970|0.002165|1.059856054|
|final|eval_018_random_hotspot|NoStructurePolicy|original|1.117264168|1.117264168|7.635393|1.000059465|7.106766|0.523056|0.005571|1.000000000|
|final|eval_018_random_hotspot|UniformOperatorMarginal|original|1.252491235|1.252491235|7.519155|0.984834976|7.021406|0.492762|0.004987|0.984841921|
|final|eval_019_random_hotspot|Naive|original|0.000000000|0.000000000|406.475094|2.707040771|388.912960|17.556028|0.006106|2.707175338|
|final|eval_019_random_hotspot|Full|original|6.305929298|6.305929298|150.154774|1.000000000|139.744335|10.400719|0.009719|1.000000000|
|final|eval_019_random_hotspot|FixedShare075|original|5.892180368|5.892180368|166.972637|1.112003522|154.265724|12.697356|0.009557|1.112011854|
|final|eval_019_random_hotspot|UnifiedSlow2048|original|6.305949416|6.305949416|150.153956|0.999994554|139.744335|10.400719|0.008902|1.000000000|
|final|eval_019_random_hotspot|NoPeriodicPrefetch|original|6.307265411|6.307265411|150.100464|0.999638309|139.693595|10.398234|0.008635|0.999645508|
|final|eval_019_random_hotspot|NoNextProtection|original|6.288781262|6.288781262|150.851798|1.004642043|140.399961|10.442467|0.009370|1.004644669|
|final|eval_019_random_hotspot|UnitMissCost|original|6.282358140|6.282358140|151.112882|1.006380809|141.743320|9.361492|0.008071|1.006392201|
|final|eval_019_random_hotspot|NoStructurePolicy|original|6.305961641|6.305961641|150.153459|0.999991245|139.744335|10.400719|0.008405|1.000000000|
|final|eval_019_random_hotspot|UniformOperatorMarginal|original|6.305941049|6.305941049|150.154296|0.999996819|139.744335|10.400719|0.009242|1.000000000|
|final|eval_022_random_hotspot|Naive|original|0.000000000|0.000000000|979.145264|2.329441727|977.346533|1.797224|0.001507|2.329476591|
|final|eval_022_random_hotspot|Full|original|5.707125925|5.707125925|420.334732|1.000000000|417.429756|2.898038|0.006938|1.000000000|
|final|eval_022_random_hotspot|FixedShare075|original|5.780007435|5.780007435|413.198573|0.983022677|410.236435|2.955524|0.006614|0.983023167|
|final|eval_022_random_hotspot|UnifiedSlow2048|original|5.699328535|5.699328535|421.098210|1.001816357|418.188012|2.903758|0.006440|1.001817572|
|final|eval_022_random_hotspot|NoPeriodicPrefetch|original|5.695349338|5.695349338|421.487831|1.002743287|418.526495|2.954666|0.006670|1.002743970|
|final|eval_022_random_hotspot|NoNextProtection|original|5.754258951|5.754258951|415.719724|0.989020636|412.726047|2.986984|0.006693|0.989021037|
|final|eval_022_random_hotspot|UnitMissCost|original|5.311054313|5.311054313|459.115896|1.092262574|457.777092|1.335334|0.003470|1.092272347|
|final|eval_022_random_hotspot|NoStructurePolicy|original|5.707126939|5.707126939|420.334633|0.999999764|417.429756|2.898038|0.006839|1.000000000|
|final|eval_022_random_hotspot|UniformOperatorMarginal|original|5.796487167|5.796487167|411.584968|0.979183819|408.634414|2.943512|0.007042|0.979183228|
|final|eval_023_random_hotspot|Naive|original|0.000000000|0.000000000|559.791446|4.890528171|540.804397|18.978519|0.008530|4.890642862|
|final|eval_023_random_hotspot|Full|original|7.955231081|7.955231081|114.464415|1.000000000|110.110571|4.349415|0.004428|1.000000000|
|final|eval_023_random_hotspot|FixedShare075|original|7.924544735|7.924544735|116.182210|1.015007244|111.836586|4.340721|0.004903|1.015003675|
|final|eval_023_random_hotspot|UnifiedSlow2048|original|7.967101222|7.967101222|113.799935|0.994194874|109.520854|4.274550|0.004531|0.994193755|
|final|eval_023_random_hotspot|NoPeriodicPrefetch|original|7.957657199|7.957657199|114.328603|0.998813500|109.975090|4.348932|0.004581|0.998812122|
|final|eval_023_random_hotspot|NoNextProtection|original|7.948240234|7.948240234|114.855757|1.003418894|110.486480|4.364871|0.004406|1.003419223|
|final|eval_023_random_hotspot|UnitMissCost|original|7.966197858|7.966197858|113.850504|0.994636667|110.504073|3.342843|0.003588|0.994643803|
|final|eval_023_random_hotspot|NoStructurePolicy|original|7.955229023|7.955229023|114.464530|1.000001007|110.110571|4.349415|0.004544|1.000000000|
|final|eval_023_random_hotspot|UniformOperatorMarginal|original|7.954953697|7.954953697|114.479943|1.000135656|110.125987|4.349415|0.004540|1.000134682|
|final|eval_024_random_zipf|Naive|original|0.000000000|0.000000000|944.202252|1.232271678|939.675890|4.524660|0.001702|1.232280785|
|final|eval_024_random_zipf|Full|original|1.884906406|1.884906406|766.228965|1.000000000|760.358817|5.863104|0.007044|1.000000000|
|final|eval_024_random_zipf|FixedShare075|original|1.297546794|1.297546794|821.687592|1.072378661|815.496073|6.185808|0.005711|1.072381067|
|final|eval_024_random_zipf|UnifiedSlow2048|original|1.887734958|1.887734958|765.961892|0.999651446|760.054981|5.901984|0.004927|0.999654206|
|final|eval_024_random_zipf|NoPeriodicPrefetch|original|1.884629582|1.884629582|766.255103|1.000034112|760.382438|5.867478|0.005186|1.000036537|
|final|eval_024_random_zipf|NoNextProtection|original|1.799971817|1.799971817|774.248508|1.010466249|768.264084|5.979744|0.004680|1.010469431|
|final|eval_024_random_zipf|UnitMissCost|original|1.583616753|1.583616753|794.676802|1.037127071|790.438862|4.234032|0.003908|1.037131506|
|final|eval_024_random_zipf|NoStructurePolicy|original|1.884923126|1.884923126|766.227386|0.999997940|760.358817|5.863104|0.005465|1.000000000|
|final|eval_024_random_zipf|UniformOperatorMarginal|original|1.849524925|1.849524925|769.569692|1.004359960|763.625958|5.938434|0.005300|1.004362276|
|final|eval_025_random_zipf|Naive|original|0.000000000|0.000000000|8.869957|1.332946763|8.543663|0.325707|0.000587|1.333558149|
|final|eval_025_random_zipf|Full|original|2.497824910|2.497824910|6.654397|1.000000000|5.347625|1.303281|0.003491|1.000000000|
|final|eval_025_random_zipf|FixedShare075|original|2.173991954|2.173991954|6.941635|1.043165209|5.937230|1.000224|0.004181|1.043084088|
|final|eval_025_random_zipf|UnifiedSlow2048|original|2.645211064|2.645211064|6.523666|0.980354210|5.295207|1.225365|0.003094|0.980403545|
|final|eval_025_random_zipf|NoPeriodicPrefetch|original|2.498178700|2.498178700|6.654083|0.999952842|5.347625|1.303281|0.003177|1.000000000|
|final|eval_025_random_zipf|NoNextProtection|original|2.498525838|2.498525838|6.653775|0.999906570|5.347625|1.303281|0.002869|1.000000000|
|final|eval_025_random_zipf|UnitMissCost|original|2.139076699|2.139076699|6.972605|1.047819227|6.629434|0.342015|0.001156|1.048195370|
|final|eval_025_random_zipf|NoStructurePolicy|original|2.498333289|2.498333289|6.653946|0.999932236|5.347625|1.303281|0.003040|1.000000000|
|final|eval_025_random_zipf|UniformOperatorMarginal|original|2.521117651|2.521117651|6.633736|0.996895202|5.328564|1.302375|0.002797|0.996997878|
|final|eval_026_random_hotspot|Naive|original|0.000000000|0.000000000|10.527068|1.181959026|10.256746|0.269744|0.000578|1.182131980|
|final|eval_026_random_hotspot|Full|original|1.539469828|1.539469828|8.906458|1.000000000|8.273178|0.631488|0.001792|1.000000000|
|final|eval_026_random_hotspot|FixedShare075|original|1.246539071|1.246539071|9.214828|1.034623215|8.522708|0.689632|0.002488|1.034552015|
|final|eval_026_random_hotspot|UnifiedSlow2048|original|1.215121492|1.215121492|9.247902|1.038336644|8.551419|0.694416|0.002067|1.038313477|
|final|eval_026_random_hotspot|NoPeriodicPrefetch|original|1.536884882|1.536884882|8.909179|1.000305530|8.275943|0.631120|0.002116|1.000269237|
|final|eval_026_random_hotspot|NoNextProtection|original|1.539233969|1.539233969|8.906706|1.000027878|8.273178|0.631488|0.002040|1.000000000|
|final|eval_026_random_hotspot|UnitMissCost|original|2.226658887|2.226658887|8.183049|0.918777069|7.910446|0.271216|0.001387|0.918806219|
|final|eval_026_random_hotspot|NoStructurePolicy|original|1.539436970|1.539436970|8.906493|1.000003884|8.273178|0.631488|0.001827|1.000000000|
|final|eval_026_random_hotspot|UniformOperatorMarginal|original|1.443021000|1.443021000|9.007990|1.011399856|8.378419|0.627808|0.001763|1.011405394|
|final|eval_027_random_hotspot|Naive|original|0.000000000|0.000000000|22.000191|1.049227041|21.708100|0.291060|0.001031|1.049358314|
|final|eval_027_random_hotspot|Full|original|0.469174350|0.469174350|20.967998|1.000000000|20.562508|0.401885|0.003605|1.000000000|
|final|eval_027_random_hotspot|FixedShare075|original|0.477389537|0.477389537|20.949924|0.999138040|20.569461|0.376475|0.003989|0.999119616|
|final|eval_027_random_hotspot|UnifiedSlow2048|original|0.495644820|0.495644820|20.909763|0.997222647|20.508511|0.397705|0.003546|0.997225000|
|final|eval_027_random_hotspot|NoPeriodicPrefetch|original|0.486380460|0.486380460|20.930144|0.998194688|20.525111|0.401500|0.003533|0.998197817|
|final|eval_027_random_hotspot|NoNextProtection|original|0.505335664|0.505335664|20.888442|0.996205857|20.482945|0.402160|0.003337|0.996217998|
|final|eval_027_random_hotspot|UnitMissCost|original|0.409265328|0.409265328|21.099799|1.006285817|20.803296|0.293535|0.002968|1.006317288|
|final|eval_027_random_hotspot|NoStructurePolicy|original|0.469090955|0.469090955|20.968182|1.000008750|20.562508|0.401885|0.003789|1.000000000|
|final|eval_027_random_hotspot|UniformOperatorMarginal|original|0.531026305|0.531026305|20.831923|0.993510326|20.425136|0.403370|0.003417|0.993518219|
|final|eval_028_random_zipf|Naive|original|0.000000000|0.000000000|235.662288|1.095678680|232.600106|3.059095|0.003087|1.095714972|
|final|eval_028_random_zipf|Full|original|0.873236667|0.873236667|215.083393|1.000000000|209.700460|5.372991|0.009942|1.000000000|
|final|eval_028_random_zipf|FixedShare075|original|0.659041117|0.659041117|220.131174|1.023468950|214.246970|5.873907|0.010297|1.023468381|
|final|eval_028_random_zipf|UnifiedSlow2048|original|0.863538626|0.863538626|215.311939|1.001062594|209.796206|5.505630|0.010103|1.001061894|
|final|eval_028_random_zipf|NoPeriodicPrefetch|original|0.893431867|0.893431867|214.607468|0.997787255|209.239133|5.358665|0.009670|0.997788414|
|final|eval_028_random_zipf|NoNextProtection|original|0.781461677|0.781461677|217.246183|1.010055590|211.832494|5.402878|0.010812|1.010052009|
|final|eval_028_random_zipf|UnitMissCost|original|0.853175670|0.853175670|215.556155|1.002198041|212.531630|3.019081|0.005444|1.002219053|
|final|eval_028_random_zipf|NoStructurePolicy|original|0.873243321|0.873243321|215.083236|0.999999271|209.700460|5.372991|0.009785|1.000000000|
|final|eval_028_random_zipf|UniformOperatorMarginal|original|0.871822394|0.871822394|215.116722|1.000154959|210.175063|4.932343|0.009316|1.000157874|
|final|eval_029_random_zipf|Naive|original|0.000000000|0.000000000|394.230831|1.154792627|387.047341|7.181130|0.002360|1.154808748|
|final|eval_029_random_zipf|Full|original|1.340436575|1.340436575|341.386689|1.000000000|333.664829|7.715050|0.006809|1.000000000|
|final|eval_029_random_zipf|FixedShare075|original|1.204264510|1.204264510|346.755011|1.015725050|338.764062|7.984360|0.006589|1.015726008|
|final|eval_029_random_zipf|UnifiedSlow2048|original|1.339823050|1.339823050|341.410876|1.000070849|333.749765|7.654420|0.006690|1.000071200|
|final|eval_029_random_zipf|NoPeriodicPrefetch|original|1.342804375|1.342804375|341.293343|0.999726568|333.564164|7.723040|0.006138|0.999728528|
|final|eval_029_random_zipf|NoNextProtection|original|1.285145124|1.285145124|343.566448|1.006385016|335.958630|7.601780|0.006038|1.006387403|
|final|eval_029_random_zipf|UnitMissCost|original|1.116086455|1.116086455|350.231262|1.025907786|343.880485|6.346410|0.004367|1.025915457|
|final|eval_029_random_zipf|NoStructurePolicy|original|1.340442405|1.340442405|341.386459|0.999999327|333.664829|7.715050|0.006580|1.000000000|
|final|eval_029_random_zipf|UniformOperatorMarginal|original|1.339489050|1.339489050|341.424043|1.000109420|333.563983|7.853700|0.006360|1.000110737|
|final|eval_031_random_zipf|Naive|original|0.000000000|0.000000000|8.469700|1.049761935|8.012116|0.456870|0.000714|1.049887791|
|final|eval_031_random_zipf|Full|original|0.474030671|0.474030671|8.068210|1.000000000|7.174018|0.892545|0.001647|1.000000000|
|final|eval_031_random_zipf|FixedShare075|original|0.227806332|0.227806332|8.276755|1.025847694|7.597048|0.678240|0.001467|1.025875348|
|final|eval_031_random_zipf|UnifiedSlow2048|original|0.071401572|0.071401572|8.409225|1.042266470|7.099899|1.307496|0.001831|1.042252354|
|final|eval_031_random_zipf|NoPeriodicPrefetch|original|0.422726351|0.422726351|8.111664|1.005385732|7.214963|0.894900|0.001801|1.005367804|
|final|eval_031_random_zipf|NoNextProtection|original|0.427184809|0.427184809|8.107887|1.004917700|7.179860|0.926457|0.001571|1.004928164|
|final|eval_031_random_zipf|UnitMissCost|original|0.279811420|0.279811420|8.232708|1.020388398|7.783201|0.448392|0.001115|1.020458493|
|final|eval_031_random_zipf|NoStructurePolicy|original|0.474124417|0.474124417|8.068131|0.999990159|7.174018|0.892545|0.001568|1.000000000|
|final|eval_031_random_zipf|UniformOperatorMarginal|original|0.337082303|0.337082303|8.184201|1.014376318|7.288494|0.893958|0.001750|1.014366547|
|final|eval_033_random_zipf|Naive|original|0.000000000|0.000000000|159.799072|4.631848933|157.303021|2.488925|0.007126|4.633102874|
|final|eval_033_random_zipf|Full|original|7.841034942|7.841034942|34.500061|1.000000000|31.570481|2.918705|0.010876|1.000000000|
|final|eval_033_random_zipf|FixedShare075|original|7.595249625|7.595249625|38.427688|1.113844046|35.869863|2.545910|0.011914|1.113849822|
|final|eval_033_random_zipf|UnifiedSlow2048|original|7.814034321|7.814034321|34.931529|1.012506280|32.098271|2.820105|0.013153|1.012444183|
|final|eval_033_random_zipf|NoPeriodicPrefetch|original|7.843674368|7.843674368|34.457884|0.998777458|31.513251|2.933205|0.011427|0.998761071|
|final|eval_033_random_zipf|NoNextProtection|original|7.843619568|7.843619568|34.458759|0.998802840|31.514095|2.933495|0.011170|0.998793932|
|final|eval_033_random_zipf|UnitMissCost|original|6.078888022|6.078888022|62.659006|1.816199833|60.768265|1.880215|0.010525|1.816467360|
|final|eval_033_random_zipf|NoStructurePolicy|original|7.840963129|7.840963129|34.501209|1.000033263|31.570481|2.918705|0.012023|1.000000000|
|final|eval_033_random_zipf|UniformOperatorMarginal|original|7.819661222|7.819661222|34.841611|1.009899984|31.848798|2.981925|0.010888|1.009902731|
|final|eval_034_random_lognormal|Naive|original|0.000000000|0.000000000|412.909727|4.501941348|410.377869|2.527664|0.004194|4.502309496|
|final|eval_034_random_lognormal|Full|original|7.778736054|7.778736054|91.718149|1.000000000|89.031245|2.678473|0.008431|1.000000000|
|final|eval_034_random_lognormal|FixedShare075|original|7.654860035|7.654860035|96.833110|1.055768257|94.322032|2.502569|0.008509|1.055772533|
|final|eval_034_random_lognormal|UnifiedSlow2048|original|7.795101698|7.795101698|91.042396|0.992632283|88.418977|2.614899|0.008519|0.992630648|
|final|eval_034_random_lognormal|NoPeriodicPrefetch|original|7.757458868|7.757458868|92.596705|1.009578865|89.891904|2.695920|0.008881|1.009574842|
|final|eval_034_random_lognormal|NoNextProtection|original|7.765319967|7.765319967|92.272112|1.006039844|89.552680|2.710499|0.008934|1.006034923|
|final|eval_034_random_lognormal|UnitMissCost|original|7.102977223|7.102977223|119.620888|1.304222663|118.042683|1.572142|0.006064|1.304276449|
|final|eval_034_random_lognormal|NoStructurePolicy|original|7.778725603|7.778725603|91.718580|1.000004705|89.031245|2.678473|0.008863|1.000000000|
|final|eval_034_random_lognormal|UniformOperatorMarginal|original|7.671901521|7.671901521|96.129451|1.048096280|93.135970|2.983915|0.009565|1.048088336|
|final|eval_036_random_lognormal|Naive|original|0.000000000|0.000000000|5.421509|1.634845323|5.099918|0.321456|0.000135|1.635105499|
|final|eval_036_random_lognormal|Full|original|3.883213377|3.883213377|3.316222|1.000000000|2.954639|0.360972|0.000610|1.000000000|
|final|eval_036_random_lognormal|FixedShare075|original|4.192305626|4.192305626|3.148647|0.949468198|2.834647|0.313464|0.000536|0.949481247|
|final|eval_036_random_lognormal|UnifiedSlow2048|original|3.928449950|3.928449950|3.291697|0.992604520|2.931001|0.360084|0.000611|0.992602971|
|final|eval_036_random_lognormal|NoPeriodicPrefetch|original|3.883310767|3.883310767|3.316169|0.999984078|2.954639|0.360972|0.000558|1.000000000|
|final|eval_036_random_lognormal|NoNextProtection|original|4.530172593|4.530172593|2.965472|0.894232175|2.742187|0.222888|0.000397|0.894277185|
|final|eval_036_random_lognormal|UnitMissCost|original|4.206247205|4.206247205|3.141088|0.947188966|2.934196|0.206460|0.000432|0.947233009|
|final|eval_036_random_lognormal|NoStructurePolicy|original|3.883269967|3.883269967|3.316191|0.999990749|2.954639|0.360972|0.000580|1.000000000|
|final|eval_036_random_lognormal|UniformOperatorMarginal|original|3.847435886|3.847435886|3.335618|1.005849066|2.942010|0.392940|0.000668|1.005832683|
|final|eval_038_random_zipf|Naive|original|0.000000000|0.000000000|15689.649704|1.002457563|15652.333755|37.309350|0.006599|1.002458161|
|final|eval_038_random_zipf|Full|original|0.024515385|0.024515385|15651.185923|1.000000000|15613.973788|37.196224|0.015911|1.000000000|
|final|eval_038_random_zipf|FixedShare075|original|0.024360869|0.024360869|15651.428354|1.000015490|15614.214295|37.198200|0.015859|1.000015493|
|final|eval_038_random_zipf|UnifiedSlow2048|original|0.024515882|0.024515882|15651.185144|0.999999950|15613.973788|37.196224|0.015132|1.000000000|
|final|eval_038_random_zipf|NoPeriodicPrefetch|original|0.024510980|0.024510980|15651.192834|1.000000442|15613.973788|37.203140|0.015906|1.000000442|
|final|eval_038_random_zipf|NoNextProtection|original|0.014469678|0.014469678|15666.947285|1.001007039|15629.655350|37.276746|0.015189|1.001007087|
|final|eval_038_random_zipf|UnitMissCost|original|0.025022556|0.025022556|15650.390190|0.999949158|15613.187102|37.187826|0.015262|0.999949200|
|final|eval_038_random_zipf|NoStructurePolicy|original|0.024515706|0.024515706|15651.185419|0.999999968|15613.973788|37.196224|0.015407|1.000000000|
|final|eval_038_random_zipf|UniformOperatorMarginal|original|0.024515283|0.024515283|15651.186083|1.000000010|15613.973788|37.196224|0.016071|1.000000000|
|final|eval_039_random_lognormal|Naive|original|0.000000000|0.000000000|28.739374|3.483443683|27.389757|1.333728|0.015889|3.489228680|
|final|eval_039_random_lognormal|Full|original|7.129277545|7.129277545|8.250277|1.000000000|6.968300|1.263744|0.018232|1.000000000|
|final|eval_039_random_lognormal|FixedShare075|original|6.736651488|6.736651488|9.378659|1.136769076|8.188988|1.170432|0.019240|1.136949632|
|final|eval_039_random_lognormal|UnifiedSlow2048|original|7.130864327|7.130864327|8.245716|0.999447254|6.995204|1.233792|0.016720|0.999629721|
|final|eval_039_random_lognormal|NoPeriodicPrefetch|original|7.130463970|7.130463970|8.246867|0.999586716|6.943171|1.282608|0.021088|0.999238895|
|final|eval_039_random_lognormal|NoNextProtection|original|7.096566802|7.096566802|8.344285|1.011394603|7.049659|1.274544|0.020082|1.011195120|
|final|eval_039_random_lognormal|UnitMissCost|original|3.228481402|3.228481402|19.460921|2.358820368|18.605117|0.842976|0.012828|2.362486453|
|final|eval_039_random_lognormal|NoStructurePolicy|original|7.129268941|7.129268941|8.250301|1.000002997|6.968300|1.263744|0.018257|1.000000000|
|final|eval_039_random_lognormal|UniformOperatorMarginal|original|7.068707583|7.068707583|8.424351|1.021099205|7.101991|1.302192|0.020168|1.020910842|
|final|eval_040_random_hotspot|Naive|original|0.000000000|0.000000000|24.768115|5.845783742|17.649885|7.093307|0.024924|5.848572020|
|final|eval_040_random_hotspot|Full|original|8.289365389|8.289365389|4.236920|1.000000000|2.753006|1.477632|0.006281|1.000000000|
|final|eval_040_random_hotspot|FixedShare075|original|8.326674695|8.326674695|4.144511|0.978189787|2.754430|1.383837|0.006244|0.978166171|
|final|eval_040_random_hotspot|UnifiedSlow2048|original|8.261056364|8.261056364|4.307036|1.016548844|2.801483|1.498796|0.006756|1.016461193|
|final|eval_040_random_hotspot|NoPeriodicPrefetch|original|8.289343445|8.289343445|4.236974|1.000012828|2.753006|1.477632|0.006336|1.000000000|
|final|eval_040_random_hotspot|NoNextProtection|original|8.289335548|8.289335548|4.236993|1.000017444|2.753006|1.477632|0.006355|1.000000000|
|final|eval_040_random_hotspot|UnitMissCost|original|8.441936819|8.441936819|3.859029|0.910810041|2.743640|1.109667|0.005722|0.910809776|
|final|eval_040_random_hotspot|NoStructurePolicy|original|8.289356345|8.289356345|4.236942|1.000005287|2.753006|1.477632|0.006304|1.000000000|
|final|eval_040_random_hotspot|UniformOperatorMarginal|original|8.315754704|8.315754704|4.171558|0.984573377|2.710005|1.454544|0.007010|0.984378347|
|final|eval_042_random_hotspot|Naive|original|0.000000000|0.000000000|503.099588|7.945892271|501.792660|1.299375|0.007553|7.946155395|
|final|eval_042_random_hotspot|Full|original|8.741488097|8.741488097|63.315682|1.000000000|63.085067|0.227568|0.003047|1.000000000|
|final|eval_042_random_hotspot|FixedShare075|original|8.347361135|8.347361135|83.144193|1.313169039|82.845856|0.294855|0.003483|1.313177234|
|final|eval_042_random_hotspot|UnifiedSlow2048|original|8.734409635|8.734409635|63.671799|1.005624470|63.444574|0.224631|0.002594|1.005631892|
|final|eval_042_random_hotspot|NoPeriodicPrefetch|original|8.741496034|8.741496034|63.315283|0.999993694|63.085067|0.227568|0.002648|1.000000000|
|final|eval_042_random_hotspot|NoNextProtection|original|8.735804975|8.735804975|63.601600|1.004515748|63.370157|0.228657|0.002786|1.004520090|
|final|eval_042_random_hotspot|UnitMissCost|original|8.661526935|8.661526935|67.338525|1.063536278|67.122093|0.213708|0.002724|1.063544442|
|final|eval_042_random_hotspot|NoStructurePolicy|original|8.741494494|8.741494494|63.315360|0.999994917|63.085067|0.227568|0.002725|1.000000000|
|final|eval_042_random_hotspot|UniformOperatorMarginal|original|8.741832879|8.741832879|63.298336|0.999726040|63.067067|0.228591|0.002678|0.999731855|
|final|eval_043_random_hotspot|Naive|original|0.000000000|0.000000000|15.822049|3.082322763|14.696626|1.122949|0.002475|3.084409458|
|final|eval_043_random_hotspot|Full|original|6.755693427|6.755693427|5.133158|1.000000000|4.295988|0.832895|0.004275|1.000000000|
|final|eval_043_random_hotspot|FixedShare075|original|6.859250226|6.859250226|4.969310|0.968080452|4.187570|0.778566|0.003174|0.968268624|
|final|eval_043_random_hotspot|UnifiedSlow2048|original|6.841399656|6.841399656|4.997553|0.973582574|4.204278|0.789791|0.003484|0.973714802|
|final|eval_043_random_hotspot|NoPeriodicPrefetch|original|6.756157090|6.756157090|5.132424|0.999857084|4.295988|0.832895|0.003541|1.000000000|
|final|eval_043_random_hotspot|NoNextProtection|original|6.756452361|6.756452361|5.131957|0.999766072|4.295988|0.832895|0.003074|1.000000000|
|final|eval_043_random_hotspot|UnitMissCost|original|6.453434316|6.453434316|5.611394|1.093166014|5.127018|0.482226|0.002149|1.093658129|
|final|eval_043_random_hotspot|NoStructurePolicy|original|6.756435322|6.756435322|5.131984|0.999771324|4.295988|0.832895|0.003101|1.000000000|
|final|eval_043_random_hotspot|UniformOperatorMarginal|original|6.770129540|6.770129540|5.110317|0.995550324|4.322294|0.783954|0.004069|0.995586713|
|final|eval_044_random_zipf|Naive|original|0.000000000|0.000000000|75.054778|1.201157174|74.696445|0.357417|0.000917|1.201187811|
|final|eval_044_random_zipf|Full|original|1.674694856|1.674694856|62.485393|1.000000000|61.525847|0.957189|0.002357|1.000000000|
|final|eval_044_random_zipf|FixedShare075|original|3.089119725|3.089119725|51.869459|0.830105342|50.834894|1.031934|0.002631|0.830094542|
|final|eval_044_random_zipf|UnifiedSlow2048|original|2.682991555|2.682991555|54.917645|0.878887719|53.929027|0.986181|0.002437|0.878881870|
|final|eval_044_random_zipf|NoPeriodicPrefetch|original|1.629842609|1.629842609|62.822031|1.005387460|61.864768|0.955377|0.001886|1.005395196|
|final|eval_044_random_zipf|NoNextProtection|original|1.674705912|1.674705912|62.485310|0.999998672|61.525847|0.957189|0.002274|1.000000000|
|final|eval_044_random_zipf|UnitMissCost|original|0.683433261|0.683433261|69.925285|1.119066098|69.583457|0.340656|0.001173|1.119089543|
|final|eval_044_random_zipf|NoStructurePolicy|original|1.674632399|1.674632399|62.485862|1.000007502|61.525847|0.957189|0.002826|1.000000000|
|final|eval_044_random_zipf|UniformOperatorMarginal|original|1.978267698|1.978267698|60.206934|0.963536130|59.255670|0.949035|0.002229|0.963536802|
|final|eval_045_random_lognormal|Naive|original|0.000000000|0.000000000|165.122115|1.948045777|154.308770|10.808340|0.005005|1.948156518|
|final|eval_045_random_lognormal|Full|original|4.866650406|4.866650406|84.762954|1.000000000|77.559488|7.196079|0.007387|1.000000000|
|final|eval_045_random_lognormal|FixedShare075|original|4.323086009|4.323086009|93.738404|1.105888833|86.022235|7.708552|0.007617|1.105895345|
|final|eval_045_random_lognormal|UnifiedSlow2048|original|4.803313968|4.803313968|85.808779|1.012338228|78.588592|7.213045|0.007142|1.012342200|
|final|eval_045_random_lognormal|NoPeriodicPrefetch|original|4.859972251|4.859972251|84.873225|1.001300935|77.650054|7.216039|0.007133|1.001304053|
|final|eval_045_random_lognormal|NoNextProtection|original|4.828540278|4.828540278|85.392236|1.007424027|78.162730|7.222526|0.006981|1.007429470|
|final|eval_045_random_lognormal|UnitMissCost|original|4.607828527|4.607828527|89.036676|1.050419687|83.170904|5.859757|0.006014|1.050440278|
|final|eval_045_random_lognormal|NoStructurePolicy|original|4.866685081|4.866685081|84.762381|0.999993245|77.559488|7.196079|0.006815|1.000000000|
|final|eval_045_random_lognormal|UniformOperatorMarginal|original|4.845802435|4.845802435|85.107200|1.004061280|77.860046|7.239991|0.007164|1.004064273|
|final|eval_046_random_zipf|Naive|original|0.000000000|0.000000000|6372.787329|1.385122591|6359.974449|12.807919|0.004961|1.385124259|
|final|eval_046_random_zipf|Full|original|2.780422424|2.780422424|4600.883250|1.000000000|4591.228058|9.646072|0.009120|1.000000000|
|final|eval_046_random_zipf|FixedShare075|original|2.779997694|2.779997694|4601.153921|1.000058830|4591.491769|9.652855|0.009297|1.000058792|
|final|eval_046_random_zipf|UnifiedSlow2048|original|2.782869937|2.782869937|4599.323502|0.999660989|4589.695183|9.619263|0.009056|0.999661003|
|final|eval_046_random_zipf|NoPeriodicPrefetch|original|2.780371856|2.780371856|4600.915476|1.000007004|4591.228058|9.677403|0.010015|1.000006810|
|final|eval_046_random_zipf|NoNextProtection|original|2.870270012|2.870270012|4543.625293|0.987555008|4533.582136|10.032380|0.010777|0.987554623|
|final|eval_046_random_zipf|UnitMissCost|original|2.650320478|2.650320478|4683.794453|1.018020715|4674.541944|9.243291|0.009218|1.018020729|
|final|eval_046_random_zipf|NoStructurePolicy|original|2.780421024|2.780421024|4600.884142|1.000000194|4591.228058|9.646072|0.010012|1.000000000|
|final|eval_046_random_zipf|UniformOperatorMarginal|original|2.767880385|2.767880385|4608.876025|1.001737226|4599.155367|9.710995|0.009662|1.001737112|
|final|eval_047_random_zipf|Naive|original|0.000000000|0.000000000|147.222489|1.269545453|146.315315|0.906360|0.000814|1.269563804|
|final|eval_047_random_zipf|Full|original|2.123165047|2.123165047|115.964725|1.000000000|114.087528|1.874880|0.002317|1.000000000|
|final|eval_047_random_zipf|FixedShare075|original|1.921779505|1.921779505|118.929573|1.025566810|117.010171|1.916880|0.002522|1.025565552|
|final|eval_047_random_zipf|UnifiedSlow2048|original|2.123165076|2.123165076|115.964725|0.999999996|114.087528|1.874880|0.002317|1.000000000|
|final|eval_047_random_zipf|NoPeriodicPrefetch|original|2.095019506|2.095019506|116.379091|1.003573204|114.482710|1.893780|0.002600|1.003570834|
|final|eval_047_random_zipf|NoNextProtection|original|2.075234660|2.075234660|116.670368|1.006084980|114.780705|1.887480|0.002183|1.006086257|
|final|eval_047_random_zipf|UnitMissCost|original|1.427863320|1.427863320|126.201130|1.088271715|125.342144|0.857640|0.001346|1.088281856|
|final|eval_047_random_zipf|NoStructurePolicy|original|2.123145874|2.123145874|115.965007|1.000002434|114.087528|1.874880|0.002599|1.000000000|
|final|eval_047_random_zipf|UniformOperatorMarginal|original|2.123156952|2.123156952|115.964844|1.000001028|114.087528|1.874880|0.002436|1.000000000|
|final|eval_050_random_zipf|Naive|original|0.000000000|0.000000000|21.062003|2.389456094|17.596898|3.458400|0.006705|2.392791744|
|final|eval_050_random_zipf|Full|original|5.814947166|5.814947166|8.814559|1.000000000|5.264345|3.535125|0.015090|1.000000000|
|final|eval_050_random_zipf|FixedShare075|original|6.105364024|6.105364024|8.202883|0.930606167|4.785922|3.403125|0.013836|0.930629628|
|final|eval_050_random_zipf|UnifiedSlow2048|original|5.389727732|5.389727732|9.710157|1.101604317|5.457117|4.235550|0.017489|1.101505866|
|final|eval_050_random_zipf|NoPeriodicPrefetch|original|5.814974072|5.814974072|8.814503|0.999993571|5.264345|3.535125|0.015033|1.000000000|
|final|eval_050_random_zipf|NoNextProtection|original|5.815409501|5.815409501|8.813586|0.999889527|5.264345|3.535125|0.014116|1.000000000|
|final|eval_050_random_zipf|UnitMissCost|original|3.971002687|3.971002687|12.698276|1.440602437|10.435801|2.253075|0.009399|1.442004682|
|final|eval_050_random_zipf|NoStructurePolicy|original|5.814433829|5.814433829|8.815641|1.000122660|5.264345|3.535125|0.016171|1.000000000|
|final|eval_050_random_zipf|UniformOperatorMarginal|original|5.097515114|5.097515114|10.325615|1.171427239|6.588301|3.723225|0.014089|1.171834909|
|final|eval_051_random_zipf|Naive|original|0.000000000|0.000000000|1.169714|1.254348569|1.121986|0.047430|0.000299|1.256034294|
|final|eval_051_random_zipf|Full|original|2.027734361|2.027734361|0.932527|1.000000000|0.740853|0.190185|0.001489|1.000000000|
|final|eval_051_random_zipf|FixedShare075|original|1.889212252|1.889212252|0.948730|1.017375501|0.734719|0.212040|0.001972|1.016884863|
|final|eval_051_random_zipf|UnifiedSlow2048|original|1.130743406|1.130743406|1.037450|1.112513932|0.810957|0.224595|0.001898|1.112254821|
|final|eval_051_random_zipf|NoPeriodicPrefetch|original|2.027006491|2.027006491|0.932612|1.000091300|0.740853|0.190185|0.001574|1.000000000|
|final|eval_051_random_zipf|NoNextProtection|original|2.027226886|2.027226886|0.932587|1.000063655|0.740853|0.190185|0.001549|1.000000000|
|final|eval_051_random_zipf|UnitMissCost|original|0.000000000|-0.434958925|1.220592|1.308907580|1.155280|0.064635|0.000677|1.310274419|
|final|eval_051_random_zipf|NoStructurePolicy|original|2.025043618|2.025043618|0.932842|1.000337513|0.740853|0.190185|0.001804|1.000000000|
|final|eval_051_random_zipf|UniformOperatorMarginal|original|2.493019321|2.493019321|0.878102|0.941637048|0.708819|0.167865|0.001418|0.941619830|
|final|eval_052_random_zipf|Naive|original|0.000000000|0.000000000|10055.328172|1.886562888|10047.465797|7.859544|0.002831|1.886564949|
|final|eval_052_random_zipf|Full|original|4.699355074|4.699355074|5329.972425|1.000000000|5320.391847|9.573256|0.007322|1.000000000|
|final|eval_052_random_zipf|FixedShare075|original|4.644404495|4.644404495|5385.227036|1.010366772|5373.800081|11.419408|0.007547|1.010366744|
|final|eval_052_random_zipf|UnifiedSlow2048|original|4.679182137|4.679182137|5350.256975|1.003805751|5340.264370|9.985360|0.007245|1.003805771|
|final|eval_052_random_zipf|NoPeriodicPrefetch|original|4.699355008|4.699355008|5329.972492|1.000000013|5320.391847|9.573256|0.007389|1.000000000|
|final|eval_052_random_zipf|NoNextProtection|original|4.691708946|4.691708946|5337.660858|1.001442490|5327.808730|9.844912|0.007216|1.001442512|
|final|eval_052_random_zipf|UnitMissCost|original|4.555661337|4.555661337|5474.461194|1.027108727|5468.105948|6.349728|0.005518|1.027109103|
|final|eval_052_random_zipf|NoStructurePolicy|original|4.699355327|4.699355327|5329.972171|0.999999952|5320.391847|9.573256|0.007067|1.000000000|
|final|eval_052_random_zipf|UniformOperatorMarginal|original|4.722682272|4.722682272|5306.516162|0.995599177|5298.271345|8.238384|0.006432|0.995599338|
|final|eval_053_random_zipf|Naive|original|0.000000000|0.000000000|534.860599|1.290160904|512.717000|22.136600|0.006999|1.290224855|
|final|eval_053_random_zipf|Full|original|2.249028810|2.249028810|414.568909|1.000000000|383.575856|30.967080|0.025973|1.000000000|
|final|eval_053_random_zipf|FixedShare075|original|2.213289145|2.213289145|416.480483|1.004610992|387.491448|28.964820|0.024215|1.004615523|
|final|eval_053_random_zipf|UnifiedSlow2048|original|2.249074158|2.249074158|414.566484|0.999994149|383.575856|30.967080|0.023548|1.000000000|
|final|eval_053_random_zipf|NoPeriodicPrefetch|original|2.249557954|2.249557954|414.540607|0.999931732|383.313067|31.201432|0.026108|0.999931403|
|final|eval_053_random_zipf|NoNextProtection|original|2.197761318|2.197761318|417.311005|1.006614331|386.183965|31.102980|0.024061|1.006619360|
|final|eval_053_random_zipf|UnitMissCost|original|1.618157379|1.618157379|448.311736|1.081392566|429.045157|19.251292|0.015288|1.081423442|
|final|eval_053_random_zipf|NoStructurePolicy|original|2.249040230|2.249040230|414.568298|0.999998527|383.575856|30.967080|0.025363|1.000000000|
|final|eval_053_random_zipf|UniformOperatorMarginal|original|2.249058940|2.249058940|414.567298|0.999996113|383.575856|30.967080|0.024362|1.000000000|
|final|eval_054_random_zipf|Naive|original|0.000000000|0.000000000|3828.655793|1.192493576|3826.623446|2.028780|0.003567|1.192498276|
|final|eval_054_random_zipf|Full|original|1.614210594|1.614210594|3210.630119|1.000000000|3206.335005|4.279470|0.015644|1.000000000|
|final|eval_054_random_zipf|FixedShare075|original|1.521040861|1.521040861|3246.301603|1.011110431|3241.815576|4.471870|0.014157|1.011110948|
|final|eval_054_random_zipf|UnifiedSlow2048|original|1.621220370|1.621220370|3207.946317|0.999164089|3203.741996|4.189900|0.014421|0.999164465|
|final|eval_054_random_zipf|NoPeriodicPrefetch|original|1.620927744|1.620927744|3208.058354|0.999198984|3203.726249|4.316780|0.015324|0.999199080|
|final|eval_054_random_zipf|NoNextProtection|original|1.462846668|1.462846668|3268.582156|1.018050051|3264.173829|4.393090|0.015237|1.018050265|
|final|eval_054_random_zipf|UnitMissCost|original|0.633881086|0.633881086|3585.964544|1.116903664|3583.934074|2.022410|0.008060|1.116906596|
|final|eval_054_random_zipf|NoStructurePolicy|original|1.614209946|1.614209946|3210.630367|1.000000077|3206.335005|4.279470|0.015892|1.000000000|
|final|eval_054_random_zipf|UniformOperatorMarginal|original|1.487877929|1.487877929|3258.998548|1.015065089|3254.580269|4.401280|0.016999|1.015064740|
|final|eval_055_random_zipf|Naive|original|0.000000000|0.000000000|159.267248|2.056654788|158.215681|1.049000|0.002567|2.056810084|
|final|eval_055_random_zipf|Full|original|5.137735289|5.137735289|77.439952|1.000000000|72.314857|5.118000|0.007095|1.000000000|
|final|eval_055_random_zipf|FixedShare075|original|5.851655989|5.851655989|66.069533|0.853171157|63.988747|2.077000|0.003786|0.853200436|
|final|eval_055_random_zipf|UnifiedSlow2048|original|5.106289242|5.106289242|77.940784|1.006467366|75.230031|2.706000|0.004753|1.006498200|
|final|eval_055_random_zipf|NoPeriodicPrefetch|original|5.149657564|5.149657564|77.250069|0.997548000|72.280462|4.963000|0.006607|0.997554080|
|final|eval_055_random_zipf|NoNextProtection|original|5.137737265|5.137737265|77.439920|0.999999594|72.314857|5.118000|0.007063|1.000000000|
|final|eval_055_random_zipf|UnitMissCost|original|4.172970896|4.172970896|92.805489|1.198418731|92.030019|0.773000|0.002470|1.198496644|
|final|eval_055_random_zipf|NoStructurePolicy|original|5.137770331|5.137770331|77.439394|0.999992793|72.314857|5.118000|0.006537|1.000000000|
|final|eval_055_random_zipf|UniformOperatorMarginal|original|5.537279195|5.537279195|71.076526|0.917827611|65.976590|5.093000|0.006936|0.917822135|
|final|eval_056_random_zipf|Naive|original|0.000000000|0.000000000|3570.059298|1.006767200|3561.243655|8.812800|0.002843|1.006769502|
|final|eval_056_random_zipf|Full|original|0.067217132|0.067217132|3546.062383|1.000000000|3532.818213|13.233240|0.010930|1.000000000|
|final|eval_056_random_zipf|FixedShare075|original|0.000000000|-0.234847785|3653.901350|1.030410905|3639.433945|14.455800|0.011604|1.030410809|
|final|eval_056_random_zipf|UnifiedSlow2048|original|0.106527184|0.106527184|3532.028461|0.996042393|3518.727029|13.290480|0.010952|0.996042374|
|final|eval_056_random_zipf|NoPeriodicPrefetch|original|0.067867050|0.067867050|3545.830358|0.999934568|3532.586240|13.233240|0.010879|0.999934583|
|final|eval_056_random_zipf|NoNextProtection|original|0.000000000|-0.084273376|3600.145393|1.015251568|3586.591887|13.543200|0.010306|1.015251791|
|final|eval_056_random_zipf|UnitMissCost|original|0.661707480|0.661707480|3333.825803|0.940148662|3325.439613|8.380260|0.005931|0.940149887|
|final|eval_056_random_zipf|NoStructurePolicy|original|0.067221281|0.067221281|3546.060902|0.999999582|3532.818213|13.233240|0.009449|1.000000000|
|final|eval_056_random_zipf|UniformOperatorMarginal|original|0.000000000|-0.010256598|3573.720964|1.007799801|3560.554609|13.156020|0.010334|1.007799993|
|final|eval_057_random_zipf|Naive|original|0.000000000|0.000000000|5371.691657|1.198446520|5368.592799|3.092904|0.005953|1.198449049|
|final|eval_057_random_zipf|Full|original|1.655864631|1.655864631|4482.212235|1.000000000|4477.926031|4.271778|0.014426|1.000000000|
|final|eval_057_random_zipf|FixedShare075|original|1.228371724|1.228371724|4711.848242|1.051232739|4707.260232|4.573260|0.014750|1.051232831|
|final|eval_057_random_zipf|UnifiedSlow2048|original|1.671127857|1.671127857|4474.013300|0.998170784|4469.715967|4.281984|0.015349|0.998170572|
|final|eval_057_random_zipf|NoPeriodicPrefetch|original|1.659291258|1.659291258|4480.371556|0.999589337|4476.075788|4.280850|0.014918|0.999589226|
|final|eval_057_random_zipf|NoNextProtection|original|1.639596582|1.639596582|4490.950928|1.001949639|4486.663126|4.273884|0.013919|1.001949758|
|final|eval_057_random_zipf|UnitMissCost|original|1.104963465|1.104963465|4778.139354|1.066022559|4775.149081|2.980314|0.009959|1.066023768|
|final|eval_057_random_zipf|NoStructurePolicy|original|1.655866852|1.655866852|4482.211041|0.999999734|4477.926031|4.271778|0.013232|1.000000000|
|final|eval_057_random_zipf|UniformOperatorMarginal|original|1.590240943|1.590240943|4517.463256|1.007864648|4513.060696|4.387770|0.014791|1.007864592|
|final|eval_058_random_zipf|Naive|original|0.000000000|0.000000000|534.669790|1.713538238|533.683270|0.960230|0.026290|1.713664776|
|final|eval_058_random_zipf|Full|original|4.164122063|4.164122063|312.026763|1.000000000|308.922196|3.066186|0.038382|1.000000000|
|final|eval_058_random_zipf|FixedShare075|original|4.016011419|4.016011419|319.945792|1.025379325|316.555355|3.348098|0.042339|1.025369763|
|final|eval_058_random_zipf|UnifiedSlow2048|original|4.388689937|4.388689937|300.019798|0.961519436|296.849081|3.133520|0.037197|0.961518500|
|final|eval_058_random_zipf|NoPeriodicPrefetch|original|4.187974488|4.187974488|310.751446|0.995912796|307.353135|3.360412|0.037899|0.995913839|
|final|eval_058_random_zipf|NoNextProtection|original|4.164151932|4.164151932|312.025166|0.999994882|308.922196|3.066186|0.036785|1.000000000|
|final|eval_058_random_zipf|UnitMissCost|original|3.193308365|3.193308365|363.933239|1.166352639|363.064706|0.838400|0.030133|1.166399544|
|final|eval_058_random_zipf|NoStructurePolicy|original|4.164187099|4.164187099|312.023286|0.999988856|308.922196|3.066186|0.034904|1.000000000|
|final|eval_058_random_zipf|UniformOperatorMarginal|original|3.777698990|3.777698990|332.687638|1.066215071|329.541664|3.109416|0.036558|1.066229064|
|final|eval_059_random_zipf|Naive|original|0.000000000|0.000000000|28.516561|0.702602017|23.890806|4.586938|0.038817|0.703961052|
|final|eval_059_random_zipf|Full|original|0.000000000|-4.232808564|40.587075|1.000000000|22.647334|17.806244|0.133497|1.000000000|
|final|eval_059_random_zipf|FixedShare075|original|0.000000000|-0.784956760|30.754988|0.757753237|21.745343|8.940440|0.069205|0.758543104|
|final|eval_059_random_zipf|UnifiedSlow2048|original|0.000000000|-1.198723204|31.934907|0.786824551|21.627375|10.233866|0.073666|0.787600079|
|final|eval_059_random_zipf|NoPeriodicPrefetch|original|0.000000000|-4.367386524|40.970845|1.009455475|22.397001|18.466058|0.107786|1.010122240|
|final|eval_059_random_zipf|NoNextProtection|original|0.000000000|-4.222103840|40.556549|0.999247884|22.647334|17.806244|0.102971|1.000000000|
|final|eval_059_random_zipf|UnitMissCost|original|0.300022030|0.300022030|27.661001|0.681522408|22.943623|4.679042|0.038337|0.682823766|
|final|eval_059_random_zipf|NoStructurePolicy|original|0.000000000|-4.223314277|40.560001|0.999332930|22.647334|17.806244|0.106423|1.000000000|
|final|eval_059_random_zipf|UniformOperatorMarginal|original|0.000000000|-6.660737286|47.510693|1.170586762|23.045433|24.328160|0.137100|1.171060642|
|final|eval_060_random_zipf|Naive|original|0.000000000|0.000000000|854.722385|1.718450777|853.875498|0.844480|0.002408|1.718462150|
|final|eval_060_random_zipf|Full|original|4.180805097|4.180805097|497.379615|1.000000000|496.214371|1.160551|0.004693|1.000000000|
|final|eval_060_random_zipf|FixedShare075|original|3.464366096|3.464366096|558.615260|1.123116516|557.067249|1.541988|0.006023|1.123115004|
|final|eval_060_random_zipf|UnifiedSlow2048|original|3.744937000|3.744937000|534.634237|1.074901787|533.503456|1.126041|0.004740|1.074902399|
|final|eval_060_random_zipf|NoPeriodicPrefetch|original|4.202062212|4.202062212|495.562722|0.996347069|494.347665|1.210286|0.004771|0.996346878|
|final|eval_060_random_zipf|NoNextProtection|original|4.102669493|4.102669493|504.058040|1.013427219|502.908242|1.144920|0.004878|1.013426974|
|final|eval_060_random_zipf|UnitMissCost|original|1.313439218|1.313439218|742.459795|1.492742712|741.654421|0.801444|0.003930|1.492748895|
|final|eval_060_random_zipf|NoStructurePolicy|original|4.180801936|4.180801936|497.379885|1.000000543|496.214371|1.160551|0.004963|1.000000000|
|final|eval_060_random_zipf|UniformOperatorMarginal|original|5.035302237|5.035302237|424.343832|0.853158873|422.891191|1.446984|0.005656|0.853155551|
|final|eval_061_random_zipf|Naive|original|0.000000000|0.000000000|6.099182|1.492413164|6.089921|0.009184|0.000077|1.492481398|
|final|eval_061_random_zipf|Full|original|3.299442647|3.299442647|4.086792|1.000000000|4.055722|0.030832|0.000238|1.000000000|
|final|eval_061_random_zipf|FixedShare075|original|3.299405200|3.299405200|4.086815|1.000005589|4.055722|0.030832|0.000261|1.000000000|
|final|eval_061_random_zipf|UnifiedSlow2048|original|3.327527101|3.327527101|4.069663|0.995808639|4.033957|0.035424|0.000281|0.995797858|
|final|eval_061_random_zipf|NoPeriodicPrefetch|original|3.299388050|3.299388050|4.086825|1.000008148|4.055722|0.030832|0.000272|1.000000000|
|final|eval_061_random_zipf|NoNextProtection|original|3.299388968|3.299388968|4.086825|1.000008011|4.055722|0.030832|0.000271|1.000000000|
|final|eval_061_random_zipf|UnitMissCost|original|1.330650930|1.330650930|5.287594|1.293825068|5.279491|0.007872|0.000231|1.293844030|
|final|eval_061_random_zipf|NoStructurePolicy|original|3.299387345|3.299387345|4.086826|1.000008253|4.055722|0.030832|0.000272|1.000000000|
|final|eval_061_random_zipf|UniformOperatorMarginal|original|0.000000000|-0.594767234|6.461942|1.581177009|6.424211|0.037392|0.000339|1.581186338|
|final|eval_062_random_zipf|Naive|original|0.000000000|0.000000000|11799.413967|1.123202549|11721.020312|78.381516|0.012139|1.123204643|
|final|eval_062_random_zipf|Full|original|1.096886298|1.096886298|10505.152417|1.000000000|10429.712287|75.409732|0.030398|1.000000000|
|final|eval_062_random_zipf|FixedShare075|original|0.993900201|0.993900201|10626.669976|1.011567425|10549.013064|77.618606|0.038306|1.011566705|
|final|eval_062_random_zipf|UnifiedSlow2048|original|1.096890452|1.096890452|10505.147516|0.999999533|10429.712287|75.409732|0.025496|1.000000000|
|final|eval_062_random_zipf|NoPeriodicPrefetch|original|1.096046018|1.096046018|10506.143898|1.000094380|10430.630365|75.488162|0.025371|1.000094859|
|final|eval_062_random_zipf|NoNextProtection|original|0.817816108|0.817816108|10834.438886|1.031345235|10755.395786|79.016086|0.027014|1.031345648|
|final|eval_062_random_zipf|UnitMissCost|original|1.285443225|1.285443225|10282.666293|0.978821238|10213.137526|69.505379|0.023388|0.978821844|
|final|eval_062_random_zipf|NoStructurePolicy|original|1.096889396|1.096889396|10505.148762|0.999999652|10429.712287|75.409732|0.026742|1.000000000|
|final|eval_062_random_zipf|UniformOperatorMarginal|original|1.096890387|1.096890387|10505.147592|0.999999541|10429.712287|75.409732|0.025573|1.000000000|
|final|eval_063_random_zipf|Naive|original|0.000000000|0.000000000|23.649502|0.968480074|21.465443|2.180142|0.003917|0.968885487|
|final|eval_063_random_zipf|Full|original|0.000000000|-0.325457658|24.419193|1.000000000|20.379242|4.025691|0.014261|1.000000000|
|final|eval_063_random_zipf|FixedShare075|original|0.025091281|0.025091281|23.590163|0.966050034|20.444995|3.135699|0.009468|0.966226553|
|final|eval_063_random_zipf|UnifiedSlow2048|original|0.000000000|-0.015738437|23.686723|0.970004311|20.274272|3.402189|0.010262|0.970150641|
|final|eval_063_random_zipf|NoPeriodicPrefetch|original|0.000000000|-0.387178796|24.565161|1.005977569|20.476023|4.078566|0.010571|1.006132222|
|final|eval_063_random_zipf|NoNextProtection|original|0.000000000|-0.362357686|24.506460|1.003573694|20.491470|4.004541|0.010449|1.003731944|
|final|eval_063_random_zipf|UnitMissCost|original|0.115867458|0.115867458|23.375481|0.957258542|21.123742|2.245707|0.006032|0.957570731|
|final|eval_063_random_zipf|NoStructurePolicy|original|0.000000000|-0.323948514|24.415624|0.999853842|20.379242|4.025691|0.010691|1.000000000|
|final|eval_063_random_zipf|UniformOperatorMarginal|original|0.000000000|-0.688911984|25.278745|1.035199827|20.522910|4.743522|0.012312|1.035300226|
|final|eval_064_random_hotspot|Naive|original|0.000000000|0.000000000|564.436859|2.609464896|547.871314|16.561136|0.004409|2.609608239|
|final|eval_064_random_hotspot|Full|original|6.167796695|6.167796695|216.303680|1.000000000|197.423028|18.867081|0.013571|1.000000000|
|final|eval_064_random_hotspot|FixedShare075|original|6.137539984|6.137539984|218.011480|1.007895382|200.048639|17.949438|0.013403|1.007896652|
|final|eval_064_random_hotspot|UnifiedSlow2048|original|6.167804456|6.167804456|216.303242|0.999997975|197.423028|18.867081|0.013133|1.000000000|
|final|eval_064_random_hotspot|NoPeriodicPrefetch|original|6.142640992|6.142640992|217.723560|1.006564292|198.803480|18.906855|0.013225|1.006566303|
|final|eval_064_random_hotspot|NoNextProtection|original|6.115466349|6.115466349|219.257397|1.013655420|200.066881|19.177697|0.012819|1.013659752|
|final|eval_064_random_hotspot|UnitMissCost|original|5.931729143|5.931729143|229.628203|1.061600999|219.950852|9.669817|0.007533|1.061632780|
|final|eval_064_random_hotspot|NoStructurePolicy|original|6.167813102|6.167813102|216.302754|0.999995719|197.423028|18.867081|0.012645|1.000000000|
|final|eval_064_random_hotspot|UniformOperatorMarginal|original|6.167514501|6.167514501|216.319608|1.000073638|197.423028|18.867081|0.029499|1.000000000|
|final|eval_065_random_hotspot|Naive|original|0.000000000|0.000000000|5.229959|0.831265322|4.121819|1.096458|0.011681|0.832030369|
|final|eval_065_random_hotspot|Full|original|0.000000000|-2.029853445|6.291563|1.000000000|4.138540|2.133199|0.019824|1.000000000|
|final|eval_065_random_hotspot|FixedShare075|original|0.000000000|-1.451671688|5.989177|0.951937756|4.140591|1.830573|0.018013|0.952074694|
|final|eval_065_random_hotspot|UnifiedSlow2048|original|0.000000000|-2.059685422|6.307165|1.002479829|4.167999|2.118831|0.020335|1.002406188|
|final|eval_065_random_hotspot|NoPeriodicPrefetch|original|0.000000000|-2.016891698|6.284784|0.998922535|4.141104|2.124219|0.019461|0.998977051|
|final|eval_065_random_hotspot|NoNextProtection|original|0.000000000|-2.028227027|6.290713|0.999864801|4.138540|2.133199|0.018974|1.000000000|
|final|eval_065_random_hotspot|UnitMissCost|original|0.000000000|-0.185386824|5.326915|0.846675886|4.073503|1.238342|0.015070|0.846949265|
|final|eval_065_random_hotspot|NoStructurePolicy|original|0.000000000|-2.027471533|6.290318|0.999802000|4.138540|2.133199|0.018579|1.000000000|
|final|eval_065_random_hotspot|UniformOperatorMarginal|original|0.000000000|-2.048928128|6.301539|1.001585612|4.184129|2.098626|0.018784|1.001756529|
|final|eval_066_random_hotspot|Naive|original|0.000000000|0.000000000|24.074257|7.690683516|13.220148|10.842084|0.012025|7.697179873|
|final|eval_066_random_hotspot|Full|original|8.699725456|8.699725456|3.130314|1.000000000|1.323026|1.803084|0.004204|1.000000000|
|final|eval_066_random_hotspot|FixedShare075|original|8.762848999|8.762848999|2.978349|0.951453681|1.315272|1.659246|0.003831|0.951507803|
|final|eval_066_random_hotspot|UnifiedSlow2048|original|8.697705041|8.697705041|3.135178|1.001553838|1.316808|1.814088|0.004283|1.001530880|
|final|eval_066_random_hotspot|NoPeriodicPrefetch|original|8.699535461|8.699535461|3.130772|1.000146120|1.323026|1.803084|0.004662|1.000000000|
|final|eval_066_random_hotspot|NoNextProtection|original|8.699803585|8.699803585|3.130126|0.999939913|1.323026|1.803084|0.004016|1.000000000|
|final|eval_066_random_hotspot|UnitMissCost|original|8.907122927|8.907122927|2.631020|0.840497169|1.327036|1.300830|0.003155|0.840618392|
|final|eval_066_random_hotspot|NoStructurePolicy|original|8.699571827|8.699571827|3.130684|1.000118151|1.323026|1.803084|0.004574|1.000000000|
|final|eval_066_random_hotspot|UniformOperatorMarginal|original|8.663381630|8.663381630|3.217809|1.027950886|1.367083|1.846314|0.004412|1.027921924|
|final|eval_067_random_hotspot|Naive|original|0.000000000|0.000000000|21981.165764|1.147765348|21922.956262|58.201228|0.008274|1.147766024|
|final|eval_067_random_hotspot|Full|original|1.287417750|1.287417750|19151.271467|1.000000000|19094.596144|56.656831|0.018491|1.000000000|
|final|eval_067_random_hotspot|FixedShare075|original|1.261373959|1.261373959|19208.518755|1.002989216|19151.699539|56.800659|0.018557|1.002989216|
|final|eval_067_random_hotspot|UnifiedSlow2048|original|1.287416935|1.287416935|19151.273259|1.000000094|19094.596144|56.656831|0.020283|1.000000000|
|final|eval_067_random_hotspot|NoPeriodicPrefetch|original|1.287269019|1.287269019|19151.598395|1.000017071|19094.900783|56.678756|0.018856|1.000017052|
|final|eval_067_random_hotspot|NoNextProtection|original|0.992954123|0.992954123|19798.536846|1.033797515|19740.081794|58.436264|0.018788|1.033797532|
|final|eval_067_random_hotspot|UnitMissCost|original|1.095378059|1.095378059|19573.397094|1.022041650|19517.037013|56.341988|0.018093|1.022041692|
|final|eval_067_random_hotspot|NoStructurePolicy|original|1.287417953|1.287417953|19151.271021|0.999999977|19094.596144|56.656831|0.018046|1.000000000|
|final|eval_067_random_hotspot|UniformOperatorMarginal|original|1.287417552|1.287417552|19151.271901|1.000000023|19094.596144|56.656831|0.018926|1.000000000|
|final|eval_068_random_hotspot|Naive|original|0.000000000|0.000000000|30.849461|2.891262865|12.450115|18.352604|0.046742|2.894702145|
|final|eval_068_random_hotspot|Full|original|6.541303761|6.541303761|10.669892|1.000000000|2.817687|7.823380|0.028825|1.000000000|
|final|eval_068_random_hotspot|FixedShare075|original|7.051529177|7.051529177|9.095874|0.852480420|2.829768|6.239212|0.026894|0.852262256|
|final|eval_068_random_hotspot|UnifiedSlow2048|original|6.568105972|6.568105972|10.587208|0.992250776|2.801120|7.755158|0.030931|0.992031880|
|final|eval_068_random_hotspot|NoPeriodicPrefetch|original|6.532754422|6.532754422|10.696266|1.002471839|2.804459|7.863250|0.028557|1.002503730|
|final|eval_068_random_hotspot|NoNextProtection|original|6.540807418|6.540807418|10.671423|1.000143506|2.817687|7.823380|0.030356|1.000000000|
|final|eval_068_random_hotspot|UnitMissCost|original|7.183654466|7.183654466|8.688274|0.814279526|2.844735|5.817476|0.026063|0.814035945|
|final|eval_068_random_hotspot|NoStructurePolicy|original|6.540881371|6.540881371|10.671195|1.000122124|2.817687|7.823380|0.030128|1.000000000|
|final|eval_068_random_hotspot|UniformOperatorMarginal|original|6.524576412|6.524576412|10.721495|1.004836316|2.815259|7.874768|0.031468|1.004601038|
|final|eval_069_random_hotspot|Naive|original|0.000000000|0.000000000|8.196551|3.574044388|1.247626|6.889680|0.059245|3.583486620|
|final|eval_069_random_hotspot|Full|original|7.202049300|7.202049300|2.293355|1.000000000|0.267379|2.003400|0.022576|1.000000000|
|final|eval_069_random_hotspot|FixedShare075|original|7.361119743|7.361119743|2.162972|0.943147517|0.272579|1.868160|0.022233|0.942733353|
|final|eval_069_random_hotspot|UnifiedSlow2048|original|7.168063553|7.168063553|2.321211|1.012146657|0.272185|2.027760|0.021267|1.012843835|
|final|eval_069_random_hotspot|NoPeriodicPrefetch|original|7.135282851|7.135282851|2.348080|1.023862625|0.269849|2.054640|0.023591|1.023652579|
|final|eval_069_random_hotspot|NoNextProtection|original|7.202667194|7.202667194|2.292848|0.999779162|0.267379|2.003400|0.022069|1.000000000|
|final|eval_069_random_hotspot|UnitMissCost|original|7.470636235|7.470636235|2.073206|0.904005837|0.271726|1.779960|0.021520|0.903516327|
|final|eval_069_random_hotspot|NoStructurePolicy|original|7.200925815|7.200925815|2.294275|1.000401538|0.267379|2.003400|0.023496|1.000000000|
|final|eval_069_random_hotspot|UniformOperatorMarginal|original|7.222342750|7.222342750|2.276721|0.992747031|0.270162|1.984920|0.021639|0.993087174|
|final|eval_070_random_hotspot|Naive|original|0.000000000|0.000000000|2437.288259|2.180005189|2426.342002|10.937060|0.009197|2.180021870|
|final|eval_070_random_hotspot|Full|original|5.412854956|5.412854956|1118.019476|1.000000000|1110.215273|7.791430|0.012773|1.000000000|
|final|eval_070_random_hotspot|FixedShare075|original|5.369541591|5.369541591|1128.576192|1.009442336|1120.604632|7.958760|0.012799|1.009442421|
|final|eval_070_random_hotspot|UnifiedSlow2048|original|5.406794847|5.406794847|1119.496499|1.001321107|1111.645322|7.838410|0.012767|1.001321128|
|final|eval_070_random_hotspot|NoPeriodicPrefetch|original|5.412855440|5.412855440|1118.019358|0.999999895|1110.215273|7.791430|0.012655|1.000000000|
|final|eval_070_random_hotspot|NoNextProtection|original|5.366373395|5.366373395|1129.348372|1.010133004|1121.466852|7.867990|0.013530|1.010132443|
|final|eval_070_random_hotspot|UnitMissCost|original|5.317942358|5.317942358|1141.152412|1.020690996|1135.099506|6.042440|0.010466|1.020693295|
|final|eval_070_random_hotspot|NoStructurePolicy|original|5.412852817|5.412852817|1118.019997|1.000000466|1110.215273|7.791430|0.013294|1.000000000|
|final|eval_070_random_hotspot|UniformOperatorMarginal|original|5.416072025|5.416072025|1117.235383|0.999298677|1109.529923|7.693120|0.012341|0.999299056|
|final|eval_071_random_hotspot|Naive|original|0.000000000|0.000000000|2549.391701|4.130298295|2508.433497|39.755600|1.202603|4.130434514|
|final|eval_071_random_hotspot|Full|original|7.578867364|7.578867364|617.241545|1.000000000|601.689600|15.240432|0.311513|1.000000000|
|final|eval_071_random_hotspot|FixedShare075|original|7.583518408|7.583518408|616.055811|0.998078980|600.716254|15.031280|0.308277|0.998083255|
|final|eval_071_random_hotspot|UnifiedSlow2048|original|7.578942655|7.578942655|617.222350|0.999968902|601.707868|15.219456|0.295026|0.999995610|
|final|eval_071_random_hotspot|NoPeriodicPrefetch|original|7.577413027|7.577413027|617.612312|1.000600685|601.654734|15.652352|0.305226|1.000611178|
|final|eval_071_random_hotspot|NoNextProtection|original|7.578931078|7.578931078|617.225302|0.999973684|601.689600|15.240432|0.295270|1.000000000|
|final|eval_071_random_hotspot|UnitMissCost|original|7.595703390|7.595703390|612.949382|0.993046219|601.327312|11.303024|0.319047|0.993030496|
|final|eval_071_random_hotspot|NoStructurePolicy|original|7.578874495|7.578874495|617.239727|0.999997055|601.689600|15.240432|0.309695|1.000000000|
|final|eval_071_random_hotspot|UniformOperatorMarginal|original|7.581045666|7.581045666|616.686210|0.999100296|601.222873|15.153488|0.309849|0.999102538|
|final|eval_072_random_hotspot|Naive|original|0.000000000|0.000000000|4749.067778|1.967961001|4743.225698|5.838225|0.003855|1.967963980|
|final|eval_072_random_hotspot|Full|original|4.918598490|4.918598490|2413.192018|1.000000000|2407.951885|5.234520|0.005612|1.000000000|
|final|eval_072_random_hotspot|FixedShare075|original|4.859473951|4.859473951|2441.270662|1.011635479|2435.936126|5.328510|0.006026|1.011635334|
|final|eval_072_random_hotspot|UnifiedSlow2048|original|4.869052806|4.869052806|2436.721599|1.009750397|2431.432524|5.283684|0.005391|1.009750512|
|final|eval_072_random_hotspot|NoPeriodicPrefetch|original|4.918589369|4.918589369|2413.196349|1.000001795|2407.951885|5.238858|0.005606|1.000001798|
|final|eval_072_random_hotspot|NoNextProtection|original|4.916725142|4.916725142|2414.081683|1.000368668|2408.839905|5.236689|0.005090|1.000368885|
|final|eval_072_random_hotspot|UnitMissCost|original|4.784740683|4.784740683|2476.761998|1.026342694|2472.841483|3.915768|0.004747|1.026343114|
|final|eval_072_random_hotspot|NoStructurePolicy|original|4.918599547|4.918599547|2413.191516|0.999999792|2407.951885|5.234520|0.005111|1.000000000|
|final|eval_072_random_hotspot|UniformOperatorMarginal|original|4.853282464|4.853282464|2444.211041|1.012853939|2439.041880|5.163666|0.005495|1.012854018|
|final|eval_073_random_hotspot|Naive|original|0.000000000|0.000000000|99.960258|1.074482527|89.182389|10.769520|0.008350|1.074817162|
|final|eval_073_random_hotspot|Full|original|0.693194395|0.693194395|93.031069|1.000000000|72.650928|20.343408|0.036733|1.000000000|
|final|eval_073_random_hotspot|FixedShare075|original|1.184746811|1.184746811|88.117499|0.947183552|72.855367|15.231336|0.030795|0.947226539|
|final|eval_073_random_hotspot|UnifiedSlow2048|original|0.693534393|0.693534393|93.027671|0.999963468|72.650928|20.343408|0.033334|1.000000000|
|final|eval_073_random_hotspot|NoPeriodicPrefetch|original|0.693463595|0.693463595|93.028378|0.999971075|72.650928|20.343408|0.034042|1.000000000|
|final|eval_073_random_hotspot|NoNextProtection|original|0.652362425|0.652362425|93.439227|1.004387324|72.929151|20.475888|0.034188|1.004416424|
|final|eval_073_random_hotspot|UnitMissCost|original|1.670971144|1.670971144|83.257188|0.894939597|73.835089|9.404976|0.017123|0.895108971|
|final|eval_073_random_hotspot|NoStructurePolicy|original|0.693687525|0.693687525|93.026140|0.999947014|72.650928|20.343408|0.031803|1.000000000|
|final|eval_073_random_hotspot|UniformOperatorMarginal|original|0.693593949|0.693593949|93.027075|0.999957069|72.650928|20.343408|0.032739|1.000000000|
|final|eval_074_random_hotspot|Naive|original|0.000000000|0.000000000|1218.590776|2.817958692|1214.938852|3.601610|0.050314|2.818197624|
|final|eval_074_random_hotspot|Full|original|6.451331942|6.451331942|432.437416|1.000000000|428.779738|3.603162|0.054516|1.000000000|
|final|eval_074_random_hotspot|FixedShare075|original|6.524441465|6.524441465|423.528357|0.979398038|419.778815|3.691820|0.057722|0.979388026|
|final|eval_074_random_hotspot|UnifiedSlow2048|original|6.494056651|6.494056651|427.231023|0.987960353|423.276325|3.899206|0.055491|0.987956580|
|final|eval_074_random_hotspot|NoPeriodicPrefetch|original|6.451310891|6.451310891|432.439981|1.000005932|428.779738|3.603162|0.057081|1.000000000|
|final|eval_074_random_hotspot|NoNextProtection|original|6.451304581|6.451304581|432.440750|1.000007710|428.779738|3.603162|0.057850|1.000000000|
|final|eval_074_random_hotspot|UnitMissCost|original|5.811358371|5.811358371|510.424005|1.180341908|508.819515|1.572952|0.031538|1.180417789|
|final|eval_074_random_hotspot|NoStructurePolicy|original|6.451315418|6.451315418|432.439430|1.000004656|428.779738|3.603162|0.056530|1.000000000|
|final|eval_074_random_hotspot|UniformOperatorMarginal|original|6.537596481|6.537596481|421.925299|0.975691009|418.335779|3.538948|0.050572|0.975697066|
|final|eval_075_random_hotspot|Naive|original|0.000000000|0.000000000|15.305947|0.712528703|14.105232|1.200192|0.000523|0.712595506|
|final|eval_075_random_hotspot|Full|original|0.000000000|-4.034522331|21.481165|1.000000000|19.269041|2.209376|0.002748|1.000000000|
|final|eval_075_random_hotspot|FixedShare075|original|0.000000000|-3.737054757|21.025863|0.978804582|18.914801|2.108608|0.002454|0.978815548|
|final|eval_075_random_hotspot|UnifiedSlow2048|original|0.000000000|-4.034424480|21.481016|0.999993028|19.269041|2.209376|0.002598|1.000000000|
|final|eval_075_random_hotspot|NoPeriodicPrefetch|original|0.000000000|-4.034259786|21.480764|0.999981293|19.269041|2.209376|0.002346|1.000000000|
|final|eval_075_random_hotspot|NoNextProtection|original|0.000000000|-3.510912467|20.679731|0.962691294|18.591522|2.085672|0.002537|0.962696335|
|final|eval_075_random_hotspot|UnitMissCost|original|0.341181242|0.341181242|14.783737|0.688218561|13.597428|1.184776|0.001533|0.688235261|
|final|eval_075_random_hotspot|NoStructurePolicy|original|0.000000000|-4.034615641|21.481308|1.000006649|19.269041|2.209376|0.002891|1.000000000|
|final|eval_075_random_hotspot|UniformOperatorMarginal|original|0.000000000|-4.034817151|21.481617|1.000021007|19.269041|2.209376|0.003199|1.000000000|
|final|eval_076_random_hotspot|Naive|original|0.000000000|0.000000000|579.349472|2.080980043|577.742502|1.567560|0.039410|2.081246202|
|final|eval_076_random_hotspot|Full|original|5.194571888|5.194571888|278.402224|1.000000000|276.676965|1.670720|0.054539|1.000000000|
|final|eval_076_random_hotspot|FixedShare075|original|5.184229742|5.184229742|279.001396|1.002152180|277.300288|1.646040|0.055067|1.002150704|
|final|eval_076_random_hotspot|UnifiedSlow2048|original|5.163194125|5.163194125|280.220093|1.006529650|278.482653|1.684640|0.052799|1.006537179|
|final|eval_076_random_hotspot|NoPeriodicPrefetch|original|5.177501460|5.177501460|279.391198|1.003552322|277.667368|1.671920|0.051910|1.003562464|
|final|eval_076_random_hotspot|NoNextProtection|original|5.191939901|5.191939901|278.554708|1.000547711|276.821600|1.678040|0.055068|1.000545918|
|final|eval_076_random_hotspot|UnitMissCost|original|5.167235180|5.167235180|279.985975|1.005688714|279.096607|0.854000|0.035368|1.005758705|
|final|eval_076_random_hotspot|NoStructurePolicy|original|5.194637106|5.194637106|278.398445|0.999986428|276.676965|1.670720|0.050761|1.000000000|
|final|eval_076_random_hotspot|UniformOperatorMarginal|original|5.165028135|5.165028135|280.113840|1.006147996|278.431300|1.632000|0.050539|1.006163570|
|final|eval_077_random_hotspot|Naive|original|0.000000000|0.000000000|620.622384|1.079735521|604.605337|16.013793|0.003254|1.079756248|
|final|eval_077_random_hotspot|Full|original|0.738472705|0.738472705|574.791115|1.000000000|549.136098|25.640970|0.014047|1.000000000|
|final|eval_077_random_hotspot|FixedShare075|original|0.467279000|0.467279000|591.622003|1.029281748|564.601014|27.006333|0.014657|1.029281403|
|final|eval_077_random_hotspot|UnifiedSlow2048|original|0.824879651|0.824879651|569.428506|0.990670335|545.146608|24.268975|0.012923|0.990672062|
|final|eval_077_random_hotspot|NoPeriodicPrefetch|original|0.738467697|0.738467697|574.791426|1.000000541|549.136098|25.640970|0.014358|1.000000000|
|final|eval_077_random_hotspot|NoNextProtection|original|0.582223437|0.582223437|584.488294|1.016870788|558.524592|25.949358|0.014344|1.016870685|
|final|eval_077_random_hotspot|UnitMissCost|original|0.583429681|0.583429681|584.413432|1.016740546|568.036093|16.368605|0.008734|1.016750199|
|final|eval_077_random_hotspot|NoStructurePolicy|original|0.738466032|0.738466032|574.791529|1.000000720|549.136098|25.640970|0.014461|1.000000000|
|final|eval_077_random_hotspot|UniformOperatorMarginal|original|0.551363141|0.551363141|586.403553|1.020202884|559.282395|27.106642|0.014516|1.020202562|
|final|eval_078_random_lognormal|Naive|original|0.000000000|0.000000000|3579.383285|2.246328489|3562.331565|17.046414|0.005306|2.246341853|
|final|eval_078_random_lognormal|Full|original|5.548291334|5.548291334|1593.437159|1.000000000|1579.738789|13.686528|0.011842|1.000000000|
|final|eval_078_random_lognormal|FixedShare075|original|5.472481085|5.472481085|1620.572553|1.017029472|1606.675725|13.886073|0.010755|1.017030281|
|final|eval_078_random_lognormal|UnifiedSlow2048|original|5.548293203|5.548293203|1593.436490|0.999999580|1579.738789|13.686528|0.011173|1.000000000|
|final|eval_078_random_lognormal|NoPeriodicPrefetch|original|5.526549377|5.526549377|1601.219439|1.004883958|1587.469077|13.739238|0.011124|1.004884445|
|final|eval_078_random_lognormal|NoNextProtection|original|5.492157572|5.492157572|1613.529584|1.012609487|1599.804181|13.714389|0.011014|1.012610100|
|final|eval_078_random_lognormal|UnitMissCost|original|4.555723208|4.555723208|1948.715335|1.222963406|1938.785661|9.921528|0.008146|1.222967382|
|final|eval_078_random_lognormal|NoStructurePolicy|original|5.548295776|5.548295776|1593.435569|0.999999002|1579.738789|13.686528|0.010252|1.000000000|
|final|eval_078_random_lognormal|UniformOperatorMarginal|original|5.548293919|5.548293919|1593.436234|0.999999419|1579.738789|13.686528|0.010917|1.000000000|
|final|eval_079_random_lognormal|Naive|original|0.000000000|0.000000000|177.393979|1.770133434|172.396760|4.937541|0.059678|1.770966273|
|final|eval_079_random_lognormal|Full|original|4.350708365|4.350708365|100.215032|1.000000000|89.584130|10.550076|0.080827|1.000000000|
|final|eval_079_random_lognormal|FixedShare075|original|4.535236835|4.535236835|96.941608|0.967335999|87.681031|9.182325|0.078252|0.967335341|
|final|eval_079_random_lognormal|UnifiedSlow2048|original|4.458965354|4.458965354|98.294619|0.980837068|87.562555|10.645767|0.086296|0.980766979|
|final|eval_079_random_lognormal|NoPeriodicPrefetch|original|4.237926602|4.237926602|102.215713|1.019963877|91.674665|10.459542|0.081506|1.019973204|
|final|eval_079_random_lognormal|NoNextProtection|original|4.350571857|4.350571857|100.217454|1.000024164|89.584130|10.550076|0.083248|1.000000000|
|final|eval_079_random_lognormal|UnitMissCost|original|2.194661827|2.194661827|138.462000|1.381649006|134.526373|3.891243|0.044384|1.382321009|
|final|eval_079_random_lognormal|NoStructurePolicy|original|4.350713212|4.350713212|100.214946|0.999999142|89.584130|10.550076|0.080741|1.000000000|
|final|eval_079_random_lognormal|UniformOperatorMarginal|original|3.773208538|3.773208538|110.459532|1.102225175|98.626000|11.741916|0.091615|1.102199950|
|final|eval_080_random_lognormal|Naive|original|0.000000000|0.000000000|344.827959|1.680957730|341.401736|3.422700|0.003523|1.681020629|
|final|eval_080_random_lognormal|Full|original|4.051010433|4.051010433|205.137793|1.000000000|197.540122|7.587900|0.009771|1.000000000|
|final|eval_080_random_lognormal|FixedShare075|original|3.946072042|3.946072042|208.756362|1.017639700|202.612257|6.136200|0.007905|1.017649640|
|final|eval_080_random_lognormal|UnifiedSlow2048|original|4.269291463|4.269291463|197.610853|0.963307882|190.895570|6.706800|0.008483|0.963312414|
|final|eval_080_random_lognormal|NoPeriodicPrefetch|original|4.050993430|4.050993430|205.138379|1.000002858|197.540122|7.588800|0.009458|1.000004388|
|final|eval_080_random_lognormal|NoNextProtection|original|4.051009803|4.051009803|205.137815|1.000000106|197.540122|7.587900|0.009793|1.000000000|
|final|eval_080_random_lognormal|UnitMissCost|original|2.168876103|2.168876103|270.039047|1.316378825|267.255856|2.777400|0.005791|1.316413299|
|final|eval_080_random_lognormal|NoStructurePolicy|original|4.051013730|4.051013730|205.137679|0.999999446|197.540122|7.587900|0.009658|1.000000000|
|final|eval_080_random_lognormal|UniformOperatorMarginal|original|3.888948327|3.888948327|210.726147|1.027241955|202.543537|8.172000|0.010611|1.027239160|
|final|eval_081_random_lognormal|Naive|original|0.000000000|0.000000000|123.702375|1.437271903|123.323890|0.376740|0.001746|1.437346705|
|final|eval_081_random_lognormal|Full|original|3.042374250|3.042374250|86.067483|1.000000000|85.474504|0.587286|0.005694|1.000000000|
|final|eval_081_random_lognormal|FixedShare075|original|3.001673289|3.001673289|86.570964|1.005849835|85.981180|0.584514|0.005270|1.005855145|
|final|eval_081_random_lognormal|UnifiedSlow2048|original|3.042369591|3.042369591|86.067541|1.000000670|85.474504|0.587286|0.005751|1.000000000|
|final|eval_081_random_lognormal|NoPeriodicPrefetch|original|3.041584579|3.041584579|86.077252|1.000113497|85.484020|0.587622|0.005610|1.000114476|
|final|eval_081_random_lognormal|NoNextProtection|original|2.983964225|2.983964225|86.790029|1.008395109|86.214820|0.569688|0.005521|1.008397674|
|final|eval_081_random_lognormal|UnitMissCost|original|1.212288800|1.212288800|108.706075|1.263033040|108.352532|0.349902|0.003641|1.263074292|
|final|eval_081_random_lognormal|NoStructurePolicy|original|3.042365879|3.042365879|86.067587|1.000001203|85.474504|0.587286|0.005797|1.000000000|
|final|eval_081_random_lognormal|UniformOperatorMarginal|original|3.042352321|3.042352321|86.067754|1.000003152|85.474504|0.587286|0.005965|1.000000000|
|final|eval_082_random_lognormal|Naive|original|0.000000000|0.000000000|428.005108|1.632342966|415.353137|12.638506|0.013465|1.632472750|
|final|eval_082_random_lognormal|Full|original|3.873836437|3.873836437|262.202930|1.000000000|249.172244|13.001592|0.029094|1.000000000|
|final|eval_082_random_lognormal|FixedShare075|original|3.769239963|3.769239963|266.679712|1.017073732|253.559141|13.091006|0.029565|1.017073827|
|final|eval_082_random_lognormal|UnifiedSlow2048|original|3.873877591|3.873877591|262.201168|0.999993282|249.172244|13.001592|0.027332|1.000000000|
|final|eval_082_random_lognormal|NoPeriodicPrefetch|original|3.902738615|3.902738615|260.965902|0.995282173|247.993937|12.943310|0.028654|0.995283326|
|final|eval_082_random_lognormal|NoNextProtection|original|3.906081762|3.906081762|260.822813|0.994736457|247.775719|13.020416|0.026678|0.994745087|
|final|eval_082_random_lognormal|UnitMissCost|original|3.217930515|3.217930515|290.276038|1.107066342|281.748122|8.505914|0.022002|1.107105273|
|final|eval_082_random_lognormal|NoStructurePolicy|original|3.873855068|3.873855068|262.202132|0.999996959|249.172244|13.001592|0.028296|1.000000000|
|final|eval_082_random_lognormal|UniformOperatorMarginal|original|3.873865901|3.873865901|262.201669|0.999995190|249.172244|13.001592|0.027832|1.000000000|
|final|eval_083_random_lognormal|Naive|original|0.000000000|0.000000000|72.283631|2.550931526|70.771441|1.491593|0.020597|2.552218936|
|final|eval_083_random_lognormal|Full|original|6.079863415|6.079863415|28.336171|1.000000000|26.962484|1.351323|0.022364|1.000000000|
|final|eval_083_random_lognormal|FixedShare075|original|5.676640049|5.676640049|31.250815|1.102859519|29.974620|1.250063|0.026132|1.102807668|
|final|eval_083_random_lognormal|UnifiedSlow2048|original|6.235353961|6.235353961|27.212228|0.960335427|25.818522|1.370745|0.022961|0.960282990|
|final|eval_083_random_lognormal|NoPeriodicPrefetch|original|6.045945004|6.045945004|28.581345|1.008652354|27.159580|1.399463|0.022302|1.008661379|
|final|eval_083_random_lognormal|NoNextProtection|original|6.059417119|6.059417119|28.483964|1.005215710|27.105025|1.355058|0.023881|1.005166242|
|final|eval_083_random_lognormal|UnitMissCost|original|4.191133635|4.191133635|41.988595|1.481802034|41.103727|0.866852|0.018016|1.482336135|
|final|eval_083_random_lognormal|NoStructurePolicy|original|6.079727720|6.079727720|28.337151|1.000034615|26.962484|1.351323|0.023345|1.000000000|
|final|eval_083_random_lognormal|UniformOperatorMarginal|original|5.861249385|5.861249385|29.916392|1.055766942|28.548969|1.344102|0.023321|1.055777186|
|final|eval_084_random_lognormal|Naive|original|0.000000000|0.000000000|59.992346|1.252725275|25.996859|33.807480|0.188007|1.251748717|
|final|eval_084_random_lognormal|Full|original|2.017403819|2.017403819|47.889467|1.000000000|14.966893|32.809740|0.112834|1.000000000|
|final|eval_084_random_lognormal|FixedShare075|original|2.127482383|2.127482383|47.229080|0.986210180|15.905170|31.205644|0.118266|0.986063916|
|final|eval_084_random_lognormal|UnifiedSlow2048|original|2.177386574|2.177386574|46.929693|0.979958556|14.897423|31.922860|0.109410|0.979982882|
|final|eval_084_random_lognormal|NoPeriodicPrefetch|original|2.031932199|2.031932199|47.802308|0.998179993|14.912285|32.774072|0.115951|0.998110447|
|final|eval_084_random_lognormal|NoNextProtection|original|2.029674691|2.029674691|47.815851|0.998462797|14.915890|32.795280|0.104681|0.998629816|
|final|eval_084_random_lognormal|UnitMissCost|original|2.129388426|2.129388426|47.217645|0.985971405|19.401976|27.695720|0.119949|0.985789343|
|final|eval_084_random_lognormal|NoStructurePolicy|original|2.017528088|2.017528088|47.888722|0.999984432|14.966893|32.809740|0.112088|1.000000000|
|final|eval_084_random_lognormal|UniformOperatorMarginal|original|2.131213738|2.131213738|47.206695|0.985742744|14.914138|32.180248|0.112309|0.985720065|
|final|eval_085_random_lognormal|Naive|original|0.000000000|0.000000000|179.420502|1.228318000|33.243868|145.350784|0.825850|1.226914912|
|final|eval_085_random_lognormal|Full|original|1.858785753|1.858785753|146.070074|1.000000000|23.246184|122.317824|0.506067|1.000000000|
|final|eval_085_random_lognormal|FixedShare075|original|1.837058891|1.837058891|146.459899|1.002668750|25.357712|120.530496|0.571691|1.002227197|
|final|eval_085_random_lognormal|UnifiedSlow2048|original|1.892538578|1.892538578|145.464480|0.995854080|23.464425|121.480768|0.519286|0.995748848|
|final|eval_085_random_lognormal|NoPeriodicPrefetch|original|1.872724690|1.872724690|145.819981|0.998287855|23.218007|122.099744|0.502230|0.998308259|
|final|eval_085_random_lognormal|NoNextProtection|original|1.857569195|1.857569195|146.091902|1.000149432|23.296266|122.302048|0.493588|1.000235677|
|final|eval_085_random_lognormal|UnitMissCost|original|2.283591776|2.283591776|138.448183|0.947820312|25.824785|112.098688|0.524711|0.947510822|
|final|eval_085_random_lognormal|NoStructurePolicy|original|1.858060883|1.858060883|146.083080|1.000089037|23.246184|122.317824|0.519072|1.000000000|
|final|eval_085_random_lognormal|UniformOperatorMarginal|original|1.914170891|1.914170891|145.076352|0.993196944|23.455013|121.103072|0.518266|0.993089483|
|stat|eval_00_uniform_static_staggered|Naive|original|0.000000000|0.000000000|357365.830396|1.027261324|357339.266688|25.874900|0.688808|1.027261581|
|stat|eval_00_uniform_static_staggered|Full|original|0.265378671|0.265378671|347882.103493|1.000000000|347829.019040|52.326900|0.757553|1.000000000|
|stat|eval_00_uniform_static_staggered|FixedShare075|original|0.266121148|0.266121148|347855.569905|0.999923728|347802.570077|52.263200|0.736628|0.999923788|
|stat|eval_00_uniform_static_staggered|UnifiedSlow2048|original|0.285361143|0.285361143|347167.998207|0.997947278|347115.207551|52.105300|0.685356|0.997947481|
|stat|eval_00_uniform_static_staggered|NoPeriodicPrefetch|original|0.273007626|0.273007626|347609.470715|0.999216307|347555.963702|52.779200|0.727813|0.999216391|
|stat|eval_00_uniform_static_staggered|NoNextProtection|original|0.261157184|0.261157184|348032.964999|1.000433657|347979.931163|52.375100|0.658736|1.000433942|
|stat|eval_00_uniform_static_staggered|UnitMissCost|original|0.243343311|0.243343311|348669.571942|1.002263607|348643.915866|25.094400|0.561675|1.002264175|
|stat|eval_00_uniform_static_staggered|NoStructurePolicy|original|0.265377835|0.265377835|347882.133370|1.000000086|347829.019040|52.326900|0.787430|1.000000000|
|stat|eval_00_uniform_static_staggered|UniformOperatorMarginal|original|0.277133925|0.277133925|347462.010873|0.998792428|347409.225153|52.041100|0.744620|0.998792463|
|stat|eval_01_uniform_fast_staggered|Naive|original|0.000000000|0.000000000|147408.869064|1.054195609|147216.130085|190.846200|1.892779|1.054205645|
|stat|eval_01_uniform_fast_staggered|Full|original|0.514094433|0.514094433|139830.661166|1.000000000|139268.782842|558.751800|3.126523|1.000000000|
|stat|eval_01_uniform_fast_staggered|FixedShare075|original|0.515743634|0.515743634|139806.350477|0.999826142|139244.865419|558.531300|2.953758|0.999827374|
|stat|eval_01_uniform_fast_staggered|UnifiedSlow2048|original|0.530608085|0.530608085|139587.235285|0.998259138|139032.965928|551.286900|2.982457|0.998260129|
|stat|eval_01_uniform_fast_staggered|NoPeriodicPrefetch|original|0.517860688|0.517860688|139775.143226|0.999602963|139206.047277|566.126700|2.969249|0.999604079|
|stat|eval_01_uniform_fast_staggered|NoNextProtection|original|0.510147477|0.510147477|139888.842799|1.000416086|139326.412748|559.505400|2.924651|1.000417539|
|stat|eval_01_uniform_fast_staggered|UnitMissCost|original|0.474704973|0.474704973|140411.296742|1.004152420|140223.986401|185.698800|1.611542|1.004163347|
|stat|eval_01_uniform_fast_staggered|NoStructurePolicy|original|0.514112370|0.514112370|139830.396754|0.999998109|139268.782842|558.751800|2.862111|1.000000000|
|stat|eval_01_uniform_fast_staggered|UniformOperatorMarginal|original|0.521471854|0.521471854|139721.911437|0.999222276|139172.648545|546.345000|2.917892|0.999223750|
|stat|eval_02_zipf_slow_shared|Naive|original|0.000000000|0.000000000|1669.253783|1.565838034|1664.462546|4.381110|0.410127|1.566420766|
|stat|eval_02_zipf_slow_shared|Full|original|3.613643440|3.613643440|1066.044985|1.000000000|1056.860576|8.526000|0.658409|1.000000000|
|stat|eval_02_zipf_slow_shared|FixedShare075|original|3.991399947|3.991399947|1002.987837|0.940849449|995.146065|7.230120|0.611652|0.940856781|
|stat|eval_02_zipf_slow_shared|UnifiedSlow2048|original|4.038139485|4.038139485|995.185822|0.933530795|987.346230|7.247370|0.592222|0.933551842|
|stat|eval_02_zipf_slow_shared|NoPeriodicPrefetch|original|3.616169658|3.616169658|1065.623295|0.999604435|1056.463965|8.518860|0.640469|0.999621029|
|stat|eval_02_zipf_slow_shared|NoNextProtection|original|3.613817126|3.613817126|1066.015992|0.999972804|1056.860576|8.526000|0.629416|1.000000000|
|stat|eval_02_zipf_slow_shared|UnitMissCost|original|2.135910053|2.135910053|1312.716189|1.231389114|1308.560559|3.731760|0.423871|1.231752256|
|stat|eval_02_zipf_slow_shared|NoStructurePolicy|original|3.613661757|3.613661757|1066.041927|0.999997132|1056.860576|8.526000|0.655351|1.000000000|
|stat|eval_02_zipf_slow_shared|UniformOperatorMarginal|original|2.566020389|2.566020389|1240.919859|1.164040802|1229.925973|10.252560|0.741325|1.164064351|
|stat|eval_03_zipf_burst_shared|Naive|original|0.000000000|0.000000000|6791.043357|1.437891112|6790.332441|0.674000|0.036916|1.437944760|
|stat|eval_03_zipf_burst_shared|Full|original|3.045370462|3.045370462|4722.919072|1.000000000|4720.452872|2.264320|0.201880|1.000000000|
|stat|eval_03_zipf_burst_shared|FixedShare075|original|2.952923513|2.952923513|4785.700196|1.013292865|4783.437004|2.058330|0.204862|1.013292801|
|stat|eval_03_zipf_burst_shared|UnifiedSlow2048|original|3.138892017|3.138892017|4659.408179|0.986552619|4657.173261|2.048840|0.186077|0.986555390|
|stat|eval_03_zipf_burst_shared|NoPeriodicPrefetch|original|3.065647793|3.065647793|4709.148649|0.997084341|4706.699482|2.233130|0.216037|0.997081218|
|stat|eval_03_zipf_burst_shared|NoNextProtection|original|3.056482729|3.056482729|4715.372684|0.998402177|4712.894589|2.272570|0.205525|0.998401337|
|stat|eval_03_zipf_burst_shared|UnitMissCost|original|1.367961089|1.367961089|5862.055050|1.241193203|5861.305108|0.665290|0.084652|1.241228335|
|stat|eval_03_zipf_burst_shared|NoStructurePolicy|original|3.045366096|3.045366096|4722.922037|1.000000628|4720.452872|2.264320|0.204845|1.000000000|
|stat|eval_03_zipf_burst_shared|UniformOperatorMarginal|original|2.883641394|2.883641394|4832.749983|1.023254879|4830.112937|2.421260|0.215787|1.023252928|
|stat|eval_04_hotspot_fast_staggered|Naive|original|0.000000000|0.000000000|39723.421545|1.528780705|39722.495374|0.889830|0.036341|1.528783015|
|stat|eval_04_hotspot_fast_staggered|Full|original|3.458839474|3.458839474|25983.727696|1.000000000|25982.615075|1.049580|0.063042|1.000000000|
|stat|eval_04_hotspot_fast_staggered|FixedShare075|original|3.407209706|3.407209706|26188.818802|1.007893059|26187.700037|1.057270|0.061495|1.007893138|
|stat|eval_04_hotspot_fast_staggered|UnifiedSlow2048|original|3.488217488|3.488217488|25867.028172|0.995508746|25865.928905|1.040170|0.059097|0.995508887|
|stat|eval_04_hotspot_fast_staggered|NoPeriodicPrefetch|original|3.478931379|3.478931379|25903.915777|0.996928388|25902.805647|1.049800|0.060330|0.996928485|
|stat|eval_04_hotspot_fast_staggered|NoNextProtection|original|3.426693452|3.426693452|26111.422697|1.004914422|26110.308535|1.052130|0.062032|1.004914473|
|stat|eval_04_hotspot_fast_staggered|UnitMissCost|original|2.855859151|2.855859151|28378.971853|1.092182468|28378.278231|0.642060|0.051562|1.092183134|
|stat|eval_04_hotspot_fast_staggered|NoStructurePolicy|original|3.458837938|3.458837938|25983.733798|1.000000235|25982.615075|1.049580|0.069143|1.000000000|
|stat|eval_04_hotspot_fast_staggered|UniformOperatorMarginal|original|3.427229513|3.427229513|26109.293278|1.004832470|26108.177260|1.054320|0.061699|1.004832533|
|stat|eval_05_hotspot_slow_shared|Naive|original|0.000000000|0.000000000|1603119.750418|3.200466508|1603064.814613|54.320400|0.615405|3.200477093|
|stat|eval_05_hotspot_slow_shared|Full|original|6.875455508|6.875455508|500901.898601|1.000000000|500875.142164|24.907560|1.848877|1.000000000|
|stat|eval_05_hotspot_slow_shared|FixedShare075|original|6.667228572|6.667228572|534283.170061|1.066642334|534256.064443|26.667630|0.437989|1.066645396|
|stat|eval_05_hotspot_slow_shared|UnifiedSlow2048|original|6.875464369|6.875464369|500900.478081|0.999997164|500875.142164|24.907560|0.428356|1.000000000|
|stat|eval_05_hotspot_slow_shared|NoPeriodicPrefetch|original|6.871962717|6.871962717|501461.834907|1.001117856|501436.448837|24.954060|0.432010|1.001120689|
|stat|eval_05_hotspot_slow_shared|NoNextProtection|original|6.853472396|6.853472396|504426.054675|1.007035621|504400.569695|25.063980|0.421000|1.007038498|
|stat|eval_05_hotspot_slow_shared|UnitMissCost|original|6.763004825|6.763004825|518929.089690|1.035989464|518909.632744|19.088970|0.367976|1.035992554|
|stat|eval_05_hotspot_slow_shared|NoStructurePolicy|original|6.875464401|6.875464401|500900.472999|0.999997154|500875.142164|24.907560|0.423274|1.000000000|
|stat|eval_05_hotspot_slow_shared|UniformOperatorMarginal|original|6.875464266|6.875464266|500900.494541|0.999997197|500875.142164|24.907560|0.444817|1.000000000|
|stat|eval_06_lognormal_burst_shared|Naive|original|0.000000000|0.000000000|882755.882017|1.978723954|882738.728520|14.381520|2.771977|1.978724749|
|stat|eval_06_lognormal_burst_shared|Full|original|4.946237964|4.946237964|446123.816324|1.000000000|446110.370435|11.865970|1.579919|1.000000000|
|stat|eval_06_lognormal_burst_shared|FixedShare075|original|4.800363657|4.800363657|459000.956624|1.028864499|458987.058439|12.236570|1.661615|1.028864418|
|stat|eval_06_lognormal_burst_shared|UnifiedSlow2048|original|4.960284965|4.960284965|444883.809122|0.997220486|444870.357161|11.826930|1.625032|0.997220375|
|stat|eval_06_lognormal_burst_shared|NoPeriodicPrefetch|original|4.948921337|4.948921337|445886.939988|0.999469035|445872.598328|11.861910|2.479750|0.999467016|
|stat|eval_06_lognormal_burst_shared|NoNextProtection|original|4.939875393|4.939875393|446685.476093|1.001258977|446672.054387|11.885870|1.535836|1.001259081|
|stat|eval_06_lognormal_burst_shared|UnitMissCost|original|3.724553213|3.724553213|553968.756363|1.241737688|553957.240922|9.691930|1.823511|1.241737998|
|stat|eval_06_lognormal_burst_shared|NoStructurePolicy|original|4.946234514|4.946234514|446124.120877|1.000000683|446110.370435|11.865970|1.884472|1.000000000|
|stat|eval_06_lognormal_burst_shared|UniformOperatorMarginal|original|4.922652873|4.922652873|448205.804170|1.004666839|448192.312444|11.881480|1.610246|1.004666787|
|stat|eval_07_lognormal_static_shared|Naive|original|0.000000000|0.000000000|32348.661119|2.050766526|32343.912383|4.575130|0.173606|2.050797179|
|stat|eval_07_lognormal_static_shared|Full|original|5.123774513|5.123774513|15773.936581|1.000000000|15769.485568|4.130590|0.320423|1.000000000|
|stat|eval_07_lognormal_static_shared|FixedShare075|original|5.021401544|5.021401544|16105.099431|1.020994306|16100.585110|4.190950|0.323372|1.020994545|
|stat|eval_07_lognormal_static_shared|UnifiedSlow2048|original|5.123776237|5.123776237|15773.931005|0.999999646|15769.485568|4.130590|0.314847|1.000000000|
|stat|eval_07_lognormal_static_shared|NoPeriodicPrefetch|original|5.122912581|5.122912581|15776.724817|1.000176762|15772.263924|4.129950|0.330942|1.000176099|
|stat|eval_07_lognormal_static_shared|NoNextProtection|original|5.113166878|5.113166878|15808.250861|1.002175378|15803.773230|4.139270|0.338361|1.002174285|
|stat|eval_07_lognormal_static_shared|UnitMissCost|original|3.643403147|3.643403147|20562.739747|1.303589604|20559.505136|2.964060|0.270551|1.303598933|
|stat|eval_07_lognormal_static_shared|NoStructurePolicy|original|5.123778087|5.123778087|15773.925022|0.999999267|15769.485568|4.130590|0.308863|1.000000000|
|stat|eval_07_lognormal_static_shared|UniformOperatorMarginal|original|5.123770880|5.123770880|15773.948335|1.000000745|15769.485568|4.130590|0.332177|1.000000000|
|stat|eval_08_mixed_mixed_shared|Naive|original|0.000000000|0.000000000|4070259.350952|1.190732043|4070122.626222|136.359400|0.365331|1.190732197|
|stat|eval_08_mixed_mixed_shared|Full|original|1.601804907|1.601804907|3418283.210980|1.000000000|3418112.616634|169.846500|0.747846|1.000000000|
|stat|eval_08_mixed_mixed_shared|FixedShare075|original|1.591327247|1.591327247|3422547.890090|1.001247608|3422376.521235|170.638400|0.730455|1.001247614|
|stat|eval_08_mixed_mixed_shared|UnifiedSlow2048|original|1.601805038|1.601805038|3418283.157536|0.999999984|3418112.616634|169.846500|0.694402|1.000000000|
|stat|eval_08_mixed_mixed_shared|NoPeriodicPrefetch|original|1.601513851|1.601513851|3418401.677996|1.000034657|3418231.084855|169.877300|0.715841|1.000034666|
|stat|eval_08_mixed_mixed_shared|NoNextProtection|original|1.488420403|1.488420403|3464433.644519|1.013501056|3464260.781165|172.147300|0.716054|1.013501068|
|stat|eval_08_mixed_mixed_shared|UnitMissCost|original|1.130260255|1.130260255|3610214.113617|1.056148333|3610078.271548|135.184100|0.657969|1.056148371|
|stat|eval_08_mixed_mixed_shared|NoStructurePolicy|original|1.601804646|1.601804646|3418283.316912|1.000000031|3418112.616634|169.846500|0.853778|1.000000000|
|stat|eval_08_mixed_mixed_shared|UniformOperatorMarginal|original|1.601804973|1.601804973|3418283.183893|0.999999992|3418112.616634|169.846500|0.720760|1.000000000|
|stat|eval_09_mixed_mixed_staggered|Naive|recovery|0.000000000|0.000000000|14990.058713|1.981580748|14967.208506|18.227880|4.622327|1.981632252|
|stat|eval_09_mixed_mixed_staggered|Full|recovery|4.953523843|4.953523843|7564.697390|1.000000000|7543.242691|18.925500|2.529198|1.000000000|
|stat|eval_09_mixed_mixed_staggered|FixedShare075|recovery|4.872058047|4.872058047|7686.815095|1.016143105|7665.085532|19.298940|2.430623|1.016161540|
|stat|eval_09_mixed_mixed_staggered|UnifiedSlow2048|recovery|4.905964561|4.905964561|7635.989032|1.009424256|7614.545697|18.950100|2.493235|1.009432163|
|stat|eval_09_mixed_mixed_staggered|NoPeriodicPrefetch|recovery|4.958953773|4.958953773|7556.557892|0.998924016|7535.240186|18.908010|2.409696|0.998939458|
|stat|eval_09_mixed_mixed_staggered|NoNextProtection|recovery|4.954556474|4.954556474|7563.149469|0.999795376|7541.867540|18.915450|2.366479|0.999816825|
|stat|eval_09_mixed_mixed_staggered|UnitMissCost|recovery|3.689407948|3.689407948|9459.614538|1.250494772|9444.644003|12.718020|2.252515|1.250615139|
|stat|eval_09_mixed_mixed_staggered|NoStructurePolicy|recovery|4.952365061|4.952365061|7566.434410|1.000229622|7543.242691|18.925500|4.266218|1.000000000|
|stat|eval_09_mixed_mixed_staggered|UniformOperatorMarginal|recovery|4.892612956|4.892612956|7656.003166|1.012069984|7634.636057|18.969060|2.398049|1.012091364|

## 10. 实际算法与完整复杂度（预先完成的源码审计）

令K为算子数、P为每算子分区数、N=KP。固定有效尺寸、合法索引、正带宽及单位成本浮点模型下，完整回调最坏O(N log(N+1))，常见单victim/top4命中路径O(N)，额外空间O(N)。固定查表初始化18,436个double（147,488字节）另列常数成本。下面保留逐部件审计，特别包括确认动作、观测步长表、结构分析、惰性概率初始化/epoch清零及动作整理，不能仅引用victim排序。

行号对应预先逐行审计的可读源SHA ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65；语义命名源仅五宏机械重命名且已验证等价。源码审计阶段本身未运行调度器；本轮所有九法编译与tiny机制门已经另行通过。

### 源码审计2. 真实活动路径

`release` 每次使概率缓存失效，然后仅调用一次 `propose(..., frequency_mode=2)`；随后因 `HASHJOIN_REUSE_ESTIMATOR!=3` 直接返回（762—779行）。因此：

1. 当前路径使用层级频率分支，不运行方案对照分支。
2. `comparePlans`、`chooseAlternative` 的均值、方差、置信边界与 paired 选择逻辑没有被调用，不能写成 R81 实际贡献。
3. `HASHJOIN_SIZE_BIAS=0`，候选密度的额外 `sqrt(1+size/typical)` 修正没有启用；但字节大小仍决定容量约束、密度和 I/O 成本。
4. `HASHJOIN_ADAPTIVE_RISK_SHARING` 只控制 `refaultReuse` 的风险共享系数；主层级概率的 `g.share` 不受这个宏控制。把该宏改成0不能称为“去掉自适应层级共享”。

回调顺序：

- overflow：`update → release → pruneSpills → record`。
- miss：`update(当前缺失分区) → release(该分区字节数) → pruneSpills → LOAD → record`。
- periodic：激活后先 `update`；若下一条是合法 PROBE、目标在 PROBE 阶段且位于磁盘、大小不超过容量，则检查 cycle。仅在空闲空间已足够，或等大小完整循环假设成立时，才 `release → pruneSpills → LOAD → record`。普通需逐出情形会等待随后 miss，以保留那时能看到的再下一条操作（823—847行）。

### 源码审计3. 可观察信息：没有完整访问轨迹

官方 `SystemState` 提供内存量、K×P 分区大小/驻留状态/阶段、读写带宽、累计 hit/miss、I/O 字节、以及仅下一条 `next_op`（框架39—49行）。真实计分 `miss_penalty` 在引擎内部，未进入 SystemState；源中100微秒是固定代理，不能说“读取了真实惩罚”或“适配任意真实惩罚”。

框架只在 INSERT 溢出、PROBE 缺失、每 B 个 INSERT/PROBE 的周期处调用调度器；SWITCH 不触发周期；单个普通命中不回调。缺失先增加 miss_count 再回调。`getSystemState` 在计时闭包内部复制全体 operators，因此记录的 D 包含 O(N) 状态构造，以及回调本身，但不含随后 executeActions 的整段执行（框架640—688、718—785行）。

R81 的时钟 `q=hit_count+miss_count` 是累计 PROBE 序号，不是墙钟时间，也不是 INSERT/SWITCH 总行序号。`sampleNext` 只采样回调暴露的下一条 PROBE；当前缺失分区只进入 `observe` 和 refault 事件，不自动作为 `sampleNext` 热度样本。相同 `q+1` 用 `next_sample_q_` 去重，miss/periodic 重复暴露同一条下一请求不会重复计数；真正连续重复 key 在不同序号上仍保留。`observe` 同样按序号去重，只在连续可见序号之间更新后继与步长。周期回调在第一次 overflow/miss 激活前直接返回。

因此“热度”是可见下一 PROBE 样本的指数加权估计，并非完整 hit 序列的精确频率；hit_count 只提供累计量，无法补出未暴露命中的 key。风险区间也只从本调度器记录且后续状态确认的动作推导，不能宣称完整系统访问风险或精确未来概率。

### 源码审计4. 双时间尺度与异质性共享的准确公式

下式各量均按相同 PROBE 序号 q 惰性衰减到当前评估时刻。令 c_op,p 为慢分区质量，M_op=Σp c_op,p，F_op 为快算子质量；每个新可见下一 PROBE 给对应 c、M、F 加1。

快算子衰减 `F ← F·2^(-Δq/256)`；慢分区及算子统计衰减 `c,M ← c,M·2^(-Δq/2048)`。这两个数是半衰期。风险的512/128与coverage的256使用 `exp(-Δq/τ)`，是另一些统计量的时间常数，不能混为这两个半衰期。

慢统计同时维护 `S_op=Σp c_op,p²` 与样本权重平方和 `W2_op`；衰减时二者乘慢衰减因子的平方。有效样本量 `n_eff=M_op²/W2_op`。满足 P>1、M_op>8、n_eff>8、有限数等保护后：

```
v = max(0, [P*S_op/M_op² - 1 - (P-1)/n_eff] / [1-1/n_eff])
strength = v*(M_op-8)/(M_op+P)
heterogeneity = strength/(1+strength)
alpha_op = share = 0.75/(1+strength)
```

不足证据时 share=0.75。集中到少数分区、且证据充分时，strength 增大，share 减小，以减少向算子内均匀分布的收缩。这是代码中的启发式异质性估计与经验收缩，本文不主张其为无偏估计、理论最优收缩或首次原创。

设 b=64/N，b_op=64/K，Z_f=Σop F_op+64，则层级分区概率为：

```
operator_marginal(op) = (F_op+b_op)/Z_f
conditional(op,p) = [(1-alpha_op)*c_op,p + alpha_op*M_op/P + b]
                    / (M_op+b_op)
p_hier(op,p) = operator_marginal(op)*conditional(op,p)
```

有限有效状态下分区条件概率按算子归一，整体概率和为1。快速算子边际响应算子间负载变化，慢条件分布保留算子内部证据；share 用慢统计调节分区特异性与共享信息。`flat_probability=(c+b)/(ΣM+64)` 也被算出并缓存，但本模式的实际候选复用值使用 `64*p_hier`，不使用 flat 概率进行方案选择。`64*p_hier`可超过1，是固定尺度的优先级代理，不应解释为0到1的真实回访概率，也没有代码证据证明真实未来64步满足该统计假设。

此频率分支仅对 PROBE 阶段、且当前未判为 scan/cycle 的候选启用（675—681行）。其余候选走可见历史/风险回退，不能把全算法都描述成上述概率模型。

### 源码审计5. 回访风险、可见历史与结构回退

`record` 只记录 PROBE 阶段、非空且预计会改变驻留状态的动作意图。下次回调 `confirm` 检查大小未变化与真实驻留状态，才确认风险区间 begin/end。区间被后续缺失触发时记一次回访 event；主动 LOAD 结束区间不记event（383—413、564—569行）。这避免将未执行或状态不吻合的意图直接当作成功逐出。

分区风险 τ=512，算子聚合风险 τ=128。对曝光量 E、事件数 R、开始数 S 和活动区间数 a，间隔 Δ 的更新是：

```
f=exp(-Δ/τ)
E ← E*f + a*τ*(1-f); R ← R*f; S ← S*f
mean_time=(E+64)/(R+1)
risk_reuse=64/(64+mean_time)
```

若分区尚无有效 start，使用可见历史值；若算子聚合有有效 start，则以 alpha=share 混合分区与算子风险。之后再以 observed_weight 混合风险与可见历史。`demandWeight` 根据周期可见下一 PROBE 的衰减覆盖代理选择0.25或1；达到0.75阈值时直接返回可见历史，风险分支被跳过。这是覆盖代理，不能解释成完整轨迹观测率的测量值。

可见历史复用值为 `min(1,h.count/16)/(1+(age+1)/64)`；h.count 每次可见访问之前乘 `256/(256+序号间隔)` 再加1，并非指数热度。连续同算子、非零相同步长达到条件时使用 `1-step_distance[delta]/P`，步长距离表按模P前进最多P次构建。

scan 判据为 `streak>=6 && stride>0 && observed_count*2>now`；它只改变符合特定当前算子条件的历史值，并使所有候选跳过频率分支。等大小 cycle 识别要求所有 N 个节点的后继至少连续置信3、所有算子处于PROBE、所有分区大小相等且正，以及从当前节点恰好N步回到起点。通过后优先沿最近记录反向寻找一个足够大的驻留 victim，排除当前目标与 next PROBE；找不到仍回到一般候选处理。这是已观察序列下的循环假设，不能写成知道未来的 oracle。

### 源码审计6. 成本密度、下一条保护、有限子集搜索

每个一般候选的密度：

```
density_i = reuse_i * (1/R + 1/W + 100/bytes_i)
```

其中R/W单位为字节/微秒；对应 `reuse_i*(bytes_i/R+bytes_i/W+100)` 的每字节代理代价。它兼顾未来读回、重写与固定缺失惩罚；不是官方完整计分的精确条件期望。当前要加载/写入的目标被排除；下一条 PROBE 目标在一般候选中加 `1e12`，这是强软保护，极端情况下仍可能被逐出，不能称绝对禁止。cycle 快路则直接跳过该目标。

一般候选按密度升序、同密度大分区优先。满足代码门槛时，只保留最前4个候选并枚举它们最多15个非空子集；对能满足释放容量的集合比较：

```
loss(S)=Σi∈S [density_i*bytes_i + 0.25*bytes_i/W]
```

命中可行子集立即返回。不是枚举所有N个候选的2^N子集，也不是全局最优的背包解。没有可行top4集合时，无probe证据走全排序贪心；有证据先测试单victim，再建堆逐个贪心释放。最后 `pruneSpills` 按既有顺序移除仍可满足容量的冗余spill，不重新全局优化。

### 源码审计7. 完整复杂度逐项审计

设 V≤N-1 为本次一般候选数，A 为本次返回动作数，A_prev 为上一回调待确认意图数。所有空间查询和向量索引按 O(1) 计；vector 连续push的总扩容成本按标准摊还保证计入。

| 部件 | 单次上界 | 不能省略的成本/条件 |
|---|---|---|
| update 维度初始化 | O(N+K)，固定尺寸以后无此项 | history/risk/next_mass/successor/confidence/recent 等assign；recent大小N+2；允许维度变化时每次变化均可能重置，不声称所有变化摊还O(1) |
| confirm | O(A_prev) | 遍历全部意图，advance/begin/end每项O(1)，末尾clear也是线性上界 |
| refreshSharing / advanceFast / sampleNext | 各O(1)+可能C_init | 不扫描P；square/mass/weight2使用增量统计；sampleNext只处理单个样本 |
| observe | O(1)通常，O(P)重建时 | successor/recent/history更新O(1)；新合格stride的assign(P)+P次循环；一次update最多两次observe，因此O(P)仍成立 |
| update 合计（初始化后） | O(A_prev+P+C_init)，常见O(A_prev+1) | 最多处理一个当前miss和一个next PROBE；无按隐藏gap逐点迭代的循环 |
| analyzeCycle | O(N)，版本没变或早退时O(1) | 可能扫描K×P状态再遍历N条后继；版本变化不能保证很稀少，不得宣称摊还O(1) |
| ensureProbabilities | cache有效时O(1)；首次构建O(K)+可能O(N)分配/清零 | 外层候选中虽然调用多次，每次release已失效且仅首次有效调用重建；循环K次refreshSharing，不是每个victim都重新O(K)；resize或tags/sign assign是O(N)；epoch溢出fill(N)；operator_scale resize O(K) |
| ensureProbability(id) | O(1)+可能C_init | 每epoch每id只计算一次，懒衰减用一个exp或查表，未遍历时间gap |
| propose cycle快路 | O(N)+analyzeCycle | recent_count≤N+2，可能逐项找不到；不能保证常数时间 |
| propose 一般候选构造 | O(N+K+C_init) | N个状态扫描；K个risk cache按需一次；概率缓存一次重建；每候选ensureProbability/风险O(1)，不存在N×K的重复重建 |
| top4子集 | O(V log4)+O(15×4)=O(V) | partial_sort至多4；15子集是常数，不是2^N |
| 无证据排序 | O(V log(V+1)) | 包括动作输出O(A) |
| 有证据单victim/堆回退 | O(V)或O(V+A log(V+1)) | min_element、make_heap线性；每个pop_heap对数；A≤N |
| release（活动mode2） | 等于一次propose加O(1) | mode3的第二次propose/chooseAlternative不可计为实际执行，也不可当贡献 |
| pruneSpills / record | 各O(A) | 两次扫描/压缩erase尾部；记录意图不会遍历系统全状态 |
| 完整overflow/miss/执行预取的periodic | O(N log(N+1)+P+A_prev+C_init) | 已合入上面所有项；固定尺寸且A_prev≤N、P≤N后O(N log(N+1)+C_init) |
| 不执行release的periodic | O(A_prev+P+N_check+C_init) | 失活时调度器自身O(1)；激活后包含update；N_check为可能触发的cycle检查，最大N |

`ensureProbabilities` 的 O(K) 循环出现在候选循环的函数调用内，但 `probability_cache_valid_` 在首次调用后为true，后续调用是常数返回；`refaultReuse` 的算子prior也由 cached_valid_ 每次propose去重。以上两处是为何完整回调没有隐藏 O(NK) 的关键。`step_distance` 的P相关循环与cycle扫描不应遗漏，但P≤N，不改变上述最坏阶。

动作数证明：propose 每个候选最多一次，且排除当前目标，故spill≤N-1；cycle最多一个spill；最多再追加一个目标LOAD；prune只减不增，record只为这些动作生成意图。因此A≤N，且每次update先confirm并清空旧意图，然后本回调才record，A_prev≤N，不会无限累积。这一界依赖官方每回调执行其动作的协议；若外部调用方重复调用record则不适用。

常态与摊还：固定维度、缓存数组已就位、无结构重建、单victim或top4命中时，需释放空间的回调通常 O(N+K)=O(N)，而非O(1)。cycle路径在很靠近recent头就找到候选且版本不变时可短至O(1)，但最坏O(N)。跨T回调只能安全给出 `O(T*N log(N+1)+C_table)` 的一般上界；若每次只走线性分支则为 `O(T*N+C_table)`。没有证明结构重建次数、全排序/大量heap-pop次数稀少，所以不能把所有输入上的均摊复杂度降为O(N)或O(1)。vector扩容和固定查表初始化的摊还，不消除合法输入可能反复触发的逐项扫描。

固定表内存：r74与r75op各1025个double，fastDecay与probabilityDecay各8193个double，总计18,436个double，147,488字节（不计静态对象标记及对齐）；每张表首次真实调用才初始化。它们按固定常数视为 O(1)，但在实现报告中单列可避免隐瞒初始化耗时。表外所有按分区/算子的向量、候选、意图和返回动作均为O(N)；若允许尺寸先大后小且不释放capacity，实际保留空间应按历史N_max描述。官方固定K/P情形为O(N)。

框架额外成本：每次被计时回调前构造SystemState含O(N)复制，临时快照O(N)空间；executeActions另需O(A)但在D计时外。两者不提高回调最坏阶。代码使用CPU标准库/基本数值运算，未见GPU、线程、训练、文件读取、外部推理或C++17依赖；预先的源码审计没有自行编译；本轮执行证据已另外确认全部九方法C++14 -O2编译成功及Full ELF等价，不将执行agent的编译冒充独立审计的新运行。



## 11. 结论边界与可交付材料

最终Full对本轮同批Naive有上述可复核主分，但消融表并不保证七个设计在每套都增益：负向移除、无影响、raw损失和尾部已完整列出。NoStructure观察到的物理零差异如实记零，不包装为创新贡献。对方截图所需的说明与Naive对照已提供，但本地合成数据不替代组织方用例、没有首次原创/理论最优证据、没有隐藏集或创新加分保证。

这份是固定恢复后、多批来源的完整分析；原attempt仍INCOMPLETE，不能改写成原一次846格成功。所有selected方法/用例只有一次被预定采用的D，原case09八条成功不用于挑选。没有后续算法或参数优化，没有引入BuildBestFit，没有自动替换最终main。

独立复核JSON：../r81_ablation_audit_20261031/ablation_result_review.json。完整846行CSV：../r81_ablation_20261031/REVIEWED_PER_CASE.csv；所有成本坏例CSV：../r81_ablation_20261031/REVIEWED_NEGATIVE_CASES.csv；分族与split：../r81_ablation_20261031/REVIEWED_GROUPS.csv。原runner冻结产物和原stat nullaggregate均未改。本报告同内容副本另存../r81_ablation_20261031/REVIEWED_REPORT.md，完整CSV位于原批目录。原证据保存在../r81_ablation_20261031/，恢复证据在本目录；恢复publication绑定输出与source_mapping，逐格标明原批或恢复批。

逐格原始指标/计数与输出哈希严格核对；聚合跨运行时求和末位差按相对2×10^-15、绝对10^-9容差核对，不改变显示位数。独立审计全过程0次native、0次输入正文扫描。
