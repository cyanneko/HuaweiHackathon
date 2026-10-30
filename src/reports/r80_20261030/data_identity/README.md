# R80 TRAIN panel：26有效 / 28预定

未完成全部预定数据：原16个TRAIN完整保留，新12个预定输入中10个生成且完整审计通过，2个rare_hot被冻结生成器因单partition超过M拒绝。没有scheduler运行，没有final成绩读取/筛选、换seed、改变pressure、重分区或修改生成器。CPU已释放；生成与流式审计3.838秒，预算30秒。data_manifest.json状态为PARTIAL，不能当作完整28例交付。

|seed|机制|pressure|penalty|none最大part/M|hot最大part/M|配对|
|---|---|---:|---:|---:|---:|---|
|202610309801|fast_shared|3|1|0.011394|0.207638|完整|
|202610309802|fast_staggered|12|1|0.044850|生成拒绝|缺hot|
|202610309803|burst_staggered|3|100|0.015345|0.325332|完整|
|202610309804|slow_shared|12|100|0.068258|0.732043|完整|
|202610309805|slow_shared|3|1000|0.012978|0.119156|完整|
|202610309806|fast_shared|12|1000|0.044499|生成拒绝|缺hot|

共同参数保持R78/R79：100k、K8/P64、M64MiB、B127、build fraction .4、read80/write100、partition-speed .0025、window/partition-window1000。penalty1/100/1000仅写入框架输入和metadata作真实成本计账；本工作未新增策略特征/API或向策略公开penalty。机制×pressure×penalty为预声明分层覆盖，不是全因子设计，不能隔离纯penalty效应。

失败：202610309802 fast_staggered/p12/pen1/hot，202610309806 fast_shared/p12/pen1000/hot。stderr原文均为“partition capacity exceeded; original case rejected, no repartitioning/replacement seed”。保留partial input与零字节metadata，未列入有效cases；不存在可用的最终max_partition或完整input合同。这是输入容量拒绝，不能解释为某策略失败。

完整配对只有4组；2个孤立none保留在单例有效列表，但不能冒充完整none/hot对照。热点同时改变INSERT/PROBE路由与分区大小，不能纯访问因果归因。六个新seed是六个谱系，不是十二个独立seed。原R79四seed none/hot谱系以及原R78四seed压力配对定义原样保留，原16也不是16个独立随机seed。

实际新有效penalty分布：1有3例，100有4例，1000有3例；失败导致覆盖不平衡。若后续评估26有效例，必须显式写明缺2和分组分母，不补造完整28结果。若要补齐，应另行冻结新谱系/方案并保留此次拒绝记录，不覆盖本冻结批次。

产物：config.json/selection.json/commands.json在生成前冻结；prepare_data.py和原R72 generator源码/二进制SHA见合同。data_manifest.json包含原16引用+新10有效输入路径、input/metaSHA、全部参数、probe/penalty/actual pressure/maxpart及错误；review.json记录身份与缺额。新10输入合计20481912字节、1,000,000操作；不是策略运行成本。

Manifest SHA: `b3bfdac9f0a62bc2190cc1d47f228fb5c7e819a5627866be4ef9f75cb5583943`。
