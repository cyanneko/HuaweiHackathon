# R81 150k TRAIN/DEV研究数据

18份合法新输入，每份150000操作，共2700000操作、54,751,717原始输入字节。TRAIN12是6新seed各none/hot一对，DEV6为另外6个独立seed，与TRAIN不重叠；不是18条独立TRAIN谱系。旧26份TRAIN用inputs.json固定Git引用恢复，不重复复制。

DEV已在候选身份冻结后用于开发验证，当前为已曝光开发回归，不是盲测，不进入拟合。generation/producer_README.md及来源manifest是生成时快照，其“尚未产生DEV分数”等文字只对应当时状态。所有新输入原字节保留，inputs.json给可直接消费的公开路径、原/公开元数据SHA及当前使用状态。

无eval目录、不注册比赛测试、不修改旧VERSION/suite/发现规则。数据生成无失败、无换seed；原压力/罚值Latin轮换不是全因子设计，DEV中的rare与shared/staggered相互混杂；none/hot同时改变INSERT/PROBE和分区大小，不是纯访问频率因果对照。

发布者只核36份input/meta SHA、头部计数及旧26份Git原件SHA，完整逐操作合法审核继承已绑定的生成审计，并未独立重做。无新的策略/训练/生成运行。完整R81四窗口回归已完成；final059超过事前尾部门槛，仍不替换默认，结果见source/cyanneko的R81报告。publication_preparation_check.json是准备时的历史状态，不表示当前回归尚未执行。

公开保留generation_traces中的18组原始算子/分区概率窗口CSV及生成stdout/stderr；它们是离线生成证据，不是策略动作trace，也不能作为在线可用特征。实际输入54,751,717字节与这些配套材料的归档总字节分开统计。
