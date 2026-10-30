# R65 三例探索性验证：保留收益与退化

状态：experimental_not_promoted。仅三个预先声明输入、候选/R63/全新Naive各一次，共九格，全部退出0；不是全方法或全库排名，未升级默认。

|输入|R63/Naive成本|R65/Naive成本|R65正式D（μs）|R65/Naive D|
|---|---:|---:|---:|---:|
|mxv1_00_hot_stream_eval.txt|3.879803|0.611416|13314.91|1.684517|
|mxv1_01_heterogeneous_rates_sizes_eval.txt|1.683429|0.831144|8263.79|8.225705|
|historical_validation_grow_after_overlap_0629_9fdf4243a6af.txt|1.388082|1.433597|730.27|1.423723|

growth案例仍为Naive的1.433597倍，且比直接前身R63恶化3.2790%。保留这个反例；热流和异构案例的改善不能据此推广为全局优势。

所有比值为本方法/同输入新鲜Naive，成本越小越好。IO与miss罚是模拟成本；D为未修改官方内部chrono回调计时（微秒），不是进程CPU。GNU user+system、GNU elapsed与父进程wall另列；0.00秒是显示精度，不代表零耗时。只有一次测量，不对D的稳定改善或显著性下结论。

本次仅含cyanneko两例、liunianwww一例，Vanius数据可用但未选入这组三例；不得虚构三成员分或称785例成绩。results.json单列两位实际参与成员的样本sum及等权平均，明确partial；该辅助标量不用于全局排名。24例池身份、完整父集合与本组三例分别保留。

results.json包含完整九格指标、输入/二进制/框架/参数身份及原结果SHA；summary.csv是执行方原逐格表。raw/保留原始stdout字节，stderr仅删去本机命令/路径行，原SHA和公开SHA分别记录。发布前逐格复核stdout指标、Hit+Miss、成本公式、基准倍率、输入及二进制SHA，没有重跑求解器。

diagnostic.json保留候选原R49核算PASS、补充有序重放PASS和首个H改变同状态受害者的证据。诊断插桩D未进入正式表；原R63/BF在前一机制包的分组IO断言FAIL仍保留，不能被候选PASS覆盖。

[冻结源码与接口检查](../../experiments/r65_turnover_risk/README.md)；[前序机制与数值核算边界](../r65_mechanism_20261030/README.md)。
