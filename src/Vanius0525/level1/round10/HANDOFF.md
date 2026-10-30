# Round10：结合 R80 的受控纯算法改进

2026-10-30。用户指定R80_next_hier_fast100.cpp@388183be301a09157730d3a4b1e966e7d036bf9e，要求综合优化频率与分区大小、简单检查BUILD/PROBE混合，持续监督source/cyanneko与datasets。AI仍暂停，默认每方法每题单遍；不重跑已完成72/dyna。

本阶段已完整完成：prepare session34744正常exit0，EXECUTION_FREEZE_V1 SHA7480004c3602f23e55d6856de09af261c3cb8924df706d4ee0d79a6e4215d556；runner session3737已exit0，16小协议+360单遍性能，106.016秒。launch/status/runner.stdout/stderr/exit在build/round10_r80_v1；不得重跑。独立pure复核360原输出/执行记录、全部输入源/TU/二进制身份、16协议与聚合门槛通过，180个旧参考物理记录与历史精确同。本目录由root独占；两子agent约3分钟监测source/cyanneko和datasets。AI暂停。

固定上游R80原件，write1仅将top4子集当前写系数.25改1，value_rank仅将排序密度改对象总价值（subset不重复乘size）。三个主候选各跑旧5协议一次完整动作核查，mixed_build0仅旧混合小例一次，共16审核；随后原60train×6方法（含Naive/paired/joint同窗口参考）=360单遍未插桩运行，不重复同方法同输入。先验门槛及范围见PLAN_V1.md；small audit不宣称60完整动作审核。

源R80 SHA0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d。原60manifest显示phase_overlap=0，N总11,480,357；不冒称主60覆盖混合阶段。既有mixed协议K2/P4/M64MiB/B5，op0先Probe、op1仍Build，已有真实overflow。BUILD无PROBE Miss罚且不能LOAD；R80本来reuse=0，所以mixed_build0尝试的是当前写机会成本假设，不是删除不存在的罚值。

R74旧大小保护曾在六例大样本胜原VanBest但弱于operator/coverage，并有synthetic09罚1000重评分物理比1.994013反例；其sqrt大小权重不是本次只改排序的value_rank，不能互相充当结论。source_monitor只读审核了本合同，提醒write1非全规划当前写系数改变。

## 本轮结论及下一步

原paired均分3.744278、joint3.735174、R80 3.742522、write1 3.731574、value_rank3.028581；三个新主候选均失败预定门槛，不晋升/不进dev。不重跑72/dyna。R80对joint逐例物理比均值0.989133、最坏1.321467；单遍均分仅高0.007348，不能称稳定全面胜出。write1对R80均比1.002302，value_rank1.577965/最坏23.565159（train600，Miss211→12176）；value_rank总物理费用之比为1.018162，与逐例比均值不同，必须同时注明分母与权重。mixed旧小例4版本全部TRACE相同、464Miss，无新收益证据。详见REPORT_V1.md。

用户问此前R80“两数据集”结果，已核实是final24+dyna6，R80共享4.090298/3.911797对原paired3.846528/3.641676；此前报告无joint，不能混用全72/12均分比较。含dyna报告链接在REPORT。

source/cyanneko最新a39d693新增R81快算子/慢条件两尺度负结果，R80源未改；datasets fab57b7新增R81训练/已曝光开发归档，原三主集未变。R81报告还提及未公布R82的single-fit与即时写费校准，待监测给确切源码/结果，不自动视作本轮write1重复，也不扩同批网格。下一纯方向先检查R80的Zipf字节退化或固定观测下共享程度，不据eval调参。阶段成果正在精确发布；当前无训练/solver，只余两个活跃监测agent。

## 已验证的训练反例

pure两项只读诊断完成：六个首差均需求Miss；519三版首差从128MB对象改驱逐627MB对象，但全流最大损失实际集中于另一1.386GB对象，pool/flat/global分别多7/6/8对需求读写。592 pool主要损失是171MB对象多24对读写。519预取全0；592仅paired/flat各一次约5MB预取。此两例不支持“全因预取或少释放空间”的统一解释，也不证明最大累计对象是首差动作直接造成。原始结果在round9/pure新诊断文件，正式freeze由pure交付；不据这两例改预先冻结R80参数。

## Open Ideas / 值得深挖的问题

暂无经核实的新独立研究贡献。频率预测改善不必等于整分区周转改善，需要将字节与Miss分别报告。

- 2026-10-30：R80先检查active再吸收periodic观测，可能丢失首次压力前的合法热度。触发：source_monitor逐行对比R80与paired，mixed早期PROBE后晚到BUILD压力可能受影响。最小验证先检查已有mixed输入是否存在该窗口，再固定早期吸收的唯一差异；当前主60全BUILD后PROBE可能没有机会，不凭理论缺口追加大矩阵。未实测收益/未声称新颖性。
