# dyna全12统一评测的独立审阅记录

2026-10-30。用户授权全dyna_dataset 12例一次描述性比较；root负责统一运行，本agent只读审核，不另启动solver、下载或训练。统一计划/runner静态审阅已完成，未发现启动阻断项；这不表示全12实际运行已经完成或全部合法。

## 已审流式成本核算器

`../cost_replay_streaming.py`，SHA `889ba2b344971aa0422c7214cadc9b40c4a29847f96c3f99395724bb2638e8b1`；精确核算基础`cost_replay_precise.py` SHA `9c83b075ab092a3711ec4aeee7a3eeec242bb8cacfced864f5f067b6eb8c9b01`。

- SPILL按被驱逐算子当前`phase[o]`计入BUILD/PROBE字节，不能按触发回调的算子阶段统一分类；现代码逐对象处理正确。
- BUILD中首次SPILL与后续盘追加均累计`build_by_op[o]`，各算子单独SWITCH时核查该算子盘分区最终大小恒等；没有假设全部算子同步SWITCH。
- LOAD检查目标算子已经PROBE，overflow只许SPILL并保护当前INSERT目标；逐动作容量、重复动作、Miss最后LOAD及目标确实驻留均检查。
- global periodic计数只由INSERT/PROBE增加，SWITCH不增加；混合阶段正常继续检查periodic。每算子INSERT/PROBE计数分别匹配输入头，各算子最终都必须SWITCH。
- 输入、TRACE顺序消耗，末尾禁止额外回调或非空输入；对象账本为O(KP)，但这不意味着官方solver本身的请求存储也是有界内存。
- 输出核查真实输入penalty参与`Total_Score`；固定100算法代理不应代替评分输入。double逐项累计与整数字节精确成本的差使用原roundoff界，未放宽动作或阶段检查。
- 现有STREAMING_REPLAY_VERIFICATION_V1报告11个保留轨迹与原核算器结果完全一致，含一个mixed-phase协议边界；额外callback和错误IO总值注入均拒绝。这里只读报告/源码，没有重跑；等价核查不等于覆盖全部动态输入。

截至此处未发现阻断混合阶段记账的代码问题。待统一计划与runner冻结后继续核查下面各项，当前不替其签署完成。

## 统一计划/runner核查范围

- 数据树/collection SHA及12例全清单，按train6/dev3/holdout3分报，训练来源与holdout首次暴露记录明确。全12均值仅为此次描述性汇总，不能混入主final72或改称主榜成绩。
- pure/ai及3个热度修正候选都冻结源码、100-only、CPU C++14；AI仍为e721f4a030fd519df8946230ab44660b1d69508a43a23ba8e65cae017527b2fa，导出一致性不是新学习收益。
- 每例官方Naive归一化，逐重复评分后再取重复均值；明确逐例clamp与全12算术均值。若另报集合封顶50的官方集分，应单列，不能与逐例平均混称。
- TRACE完整审计运行与无审计输出的正式重复计时分离；程序wall、引擎decision time、模拟IO time各自标清，审计器运行时间不算solver推理时间。不承诺宿主独占。
- 失败/超时不得丢样后平均；保存失败尝试、同输入同源码和重复次数。若调整超时或程序代码，另冻并解释，不在看结果后无记录重跑。

## 新runner与summary的实际复核

审阅绑定见[机器记录](DYNA_FULL12_STATIC_REVIEW_V1.json)：plan SHA `1225cc3b8e0c5b7e1cbfd410995cf2033cfce1be2d0886ff49ef29da1aebdffe`；runner SHA `5fb1a7279d164e62200996411665f85d383a4f2025199168d91c9b55bade9d6b`；summary SHA `7191aec8bad459978d0943049013822d85a4e6912ef906e13f237d0b46280963`；合同 SHA `076f90994353e3f4c9cc364a3b27e8d24c4a489db742f47652e2988796ddff85`。

- 实际逐件核对30件validation_artifacts的当前SHA、全部6个方法源码SHA及非Naive的100μs代理声明；三风险候选把核心内嵌在单个cpp中，没有遗漏的本地include实现。12例adoption中的raw SHA、split、seed逐项匹配full12 lock；6/3/3和案例顺序一致。
- 构建器固定官方声明SHA、保留engine片段；定时binary不插TRACE，审计binary仅包装同一调度器调用/输出。执行freeze绑定计划、源码、构建器、核算器、汇总器、编译环境与实际binary SHA。恢复时匹配freeze/环境/binary，逐case再核对原输入和源码。
- 每个case先完成6审计再跑3轮净计时；每轮按固定seed/repeat洗牌。每个方法的runs保留repeat 0/1/2顺序，不因洗牌改变Naive配对索引。跨case机器负载仍可能变化，随机顺序不是宿主独占保证。
- 定时Hit/Miss及I/O与审计一致后才接纳；评分使用该输入审核记录中的真实penalty。audit的插桩wall/decision time不混入净计时。900/300秒是本地诊断保护，并保存净计时是否超过60秒，未冒称通过官方60秒。
- 首版失败记录缺少专门wall/returncode JSON的问题已修正：run的finally写`.execution.json`；timeout可保持returncode=null并显式timed_out，不捏造未获得的进程状态。非零退出/异常保存stdout/stderr并停，不生成不完整总成绩。完整case才写canonical；partial目录阻止自动重跑，当前保守协议可沿用。
- summary先按同repeat的Naive计算每例clamp，再均值；物理成本另由BUILD写、PROBE写、PROBE读和实际Miss分项计算。它同时给未clamp比例、最坏退化、逐例改善/退化、三次耗时。全12直接平均12例；split分别6/3/3，不将三个split均值等权。明确不是官方50分，也不与主72合并。
- 本次只读代码/小元数据并做AST语法及哈希核查，没有运行dyna、重放大输入或训练。实际运行失败仍须按统一runner停下诊断，静态通过不替代72个动作审计。

没有剩余启动阻断项。root已启动统一runner；本agent后续仅低频读取status与完整case小JSON，监督AI对paired/Naive的成本/计时异常。全12完成后另写AI描述性复核，不对未完成样本汇总总成绩，不调参或重跑solver。
