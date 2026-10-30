# R78 100k TRAIN singlefit diagnostic

24/24 格完成；8 个新 TRAIN 输入，每个 100000 操作，4 机制各自配对 pressure 3/12，每对同 seed。未读取或运行 dev。native 循环至 CPU 释放 6.137 秒，含结束校验和汇总的 runner 时间 6.482 秒，预算 60 秒。CPU RELEASED，active_processes=0。

比较冻结原版 R75（source SHA `cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458`）与 producer 的 build0 / overflow 两个已有 C++14/O2、未插桩二进制；无源码修改、重编译、重跑或替换输入。框架前后缀校验仅将 CRLF 规范成 LF 比较，身份校验仍用原始字节 SHA。

主指标为 `physical cost = Total_IO_Time + actual penalty × Miss_Count`，本批实际 penalty 均为 100；下表为该成本除以同例同轮 R75 成本，越小越好。按 case 等权，分位数线性插值 q×(n−1)。无同轮 Naive，因此没有归一 score。保留负改善。

|范围|方法|mean|P50|P90|worst|胜/负/平|
|---|---|---:|---:|---:|---:|---|
|all8|build0|0.997434925|0.999729079|1.001568034|1.001905110|4/4/0|
|all8|overflow|1.000294366|1.000805612|1.005499214|1.015009043|3/5/0|
|pressure3|build0|0.994306207|0.992189014|0.999195412|1.001905110|3/1/0|
|pressure3|overflow|0.999954241|0.996933116|1.010804365|1.015009043|2/2/0|
|pressure12|build0|1.000563642|1.000995307|1.001408353|1.001423574|1/3/0|
|pressure12|overflow|1.000634492|1.000995307|1.001408353|1.001423574|1/3/0|

逐例倍率（完整物理成本、IO、hit/miss、含 D 总成本与累计 D 见 per_case.csv）：

|机制/压力|build0/R75|overflow/R75|
|---|---:|---:|
|fast_shared / 3|0.990941690|0.990941690|
|fast_shared / 12|1.001423574|1.001423574|
|fast_staggered / 3|0.991505246|1.015009043|
|fast_staggered / 12|0.998840382|0.999123780|
|burst_staggered / 3|1.001905110|1.000993450|
|burst_staggered / 12|1.000617775|1.000617775|
|slow_shared / 3|0.992872782|0.992872782|
|slow_shared / 12|1.001372838|1.001372838|

两个对照最佳均为 fast_shared_p3，成本下降 0.905831%。build0 最差 burst_staggered_p3，上升 0.190511%；overflow 最差 fast_staggered_p3，上升 1.500904%。all8 build0 平均下降 0.256508%，overflow 平均上升 0.029437%。高压力组两者平均分别上升 0.056364% / 0.063449%，均 1 胜 3 负。

累计 decision time 每例均值为 R75 73892.979 μs、build0 76331.710 μs、overflow 71980.505 μs。D、含 D Total_Score 和 wall 只作非正式记录，不用于本轮主指标，也不能据此宣称正式运行效率胜负。

独立 verify_results.py 不导入 runner，不运行策略；重新解析 24 份原始 stdout，核验 stdout/stderr 共 48 个 SHA、完整笛卡尔积、输入/二进制身份引用、hit+miss、真实 penalty、含 D 总账（输出舍入容差 0.015001 μs）、全部逐例倍率、all8/p3/p12 均值分位数及胜负平。全部 PASS，详见 independent_checks.json。runner 已在前后校验冻结输入、metadata、source/TU/binary 等 SHA，changed_artifacts=[]。

本批是新种子的 100k TRAIN 诊断，不是原 8000 输入的同 seed 延长，也不是独立测试集；因此与旧 stage0 的变化不能单独归因于规模。结果仅支持 build0 在该训练小批上的微弱均值改善，尚不足以解释一般局部 teacher 优势或支持替换 R75。允许所有 overflow 触发并未带来总体收益。没有新 teacher 标签或同状态动作对照，不能将完整轨迹变化归因为某个局部动作。冻结 R75 不变，不 promote。

数据 manifest SHA: `703b48a3522a09872728b018140613a28a74481ced3084fdd9cc9235720aacdb`。
selection SHA: `a77395b2b89a6a7b255aed633bd7948c38901fbe023c23334c0fe4c31a6d9c2e`。
report SHA: `4f4eef916b71dc1af392e9cb5bf5a4abed0853a219b225b8607f1d79ce94bad3`。
