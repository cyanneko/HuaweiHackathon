# R58 数据构造与证据边界

本文从生成前研究设计派生，原设计身份见 [原冻结记录](provenance/source_freeze.original.json)。仅描述数据，不发布实验调度器或继承其计时结果。

四家族×两个variant×train/eval＝16例，8/8。种子公式为2058280000+1000×family_index+10×variant+split_index，train0/eval1。M=64MiB、P=8，K为1或2；tuple不超过1MiB、分区不超过M，头按算子编号升序，每算子只经历一次SWITCH。完整参数、N和种子以 [冻结spec](case_specs_proposal.json) 为准。

| 家族 | 构造 | 预测边界 |
| --- | --- | --- |
| positive_cycles | 七个8MiB小分区及一个60MiB大分区；小分区后访问大分区，B1 | 静态预测存在可用空闲容量的预取机会，不能由此保证Score收益 |
| low_opportunity_mix | 两算子共享内存；小/大循环与另一个算子的scan→hotspot交错，B31或997 | 固定总配额；两半的偏好权重不保证实际份额，耗尽后的强制分配与真实位置写meta |
| temporal_alignment_mix | 最终大小同positive；拆分少量INSERT使build计数120，B8；中途两次large hit改变周期对齐 | 分段前后机会不同，仅预测；观测q另存结果 |
| no_op_controls | variant0保持B8对齐；variant1仅七个小分区、另一个零大小驻留分区 | 静态无机会控制；没有生成人工零大小在盘案例 |

后两种mix共8/16，提供跨算子或时间组合。meta保存真实计数、模式段全局一基位置、PID份额、原始操作流和modulo-P语义哈希。q_prediction、prediction_kind是生成前预测，q_observed=null不是实测零。模式、种子和完整未来流仅供离线审核，不提供给在线策略。

原独立输入审核的范围为16例头/phase/tuple/partition容量/计数、raw与modulo-P语义SHA及分段/PID真实计数；原16语义互异。公开路径适配的复现、全64例审核与跨旧/新/成员去重仍待执行。train/eval共享家族构造，独立种子与不同N不构成泛化独立性。

若研究periodic预取，只有下一行确切PROBE、目标合法且已进入PROBE、目标在盘且完整大小可装入当前空闲容量时才可能LOAD。无额外SPILL、不越过SWITCH或看更远操作。本文不实现该策略，不以理论机会数作性能结论；所有生成和审核与solver计时分别记录。
