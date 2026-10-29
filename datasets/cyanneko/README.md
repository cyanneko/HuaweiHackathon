# cyanneko · eval0.5.0，train/eval各40

已发布数据共80txt＋80原meta：R48 8/8、R54 16/16、R58 8/8、R61 8/8。旧64对逐字保留，新16对也保留原生成字节。输入共16,928,341字节，meta共2,782,588字节。

R61 Root recipe在训练前冻结；8原留出在模型freeze后开放作本轮检验，已成为观察过的开发数据，后续用于调参时必须按dev处理。它们是已知基础模式的新组合/参数，不能称官方盲测或全新家族。生成时meta里的split/use保留来源快照；当前映射为train8和eval8，详见[usage记录](provenance/usage_0.5.0.json)。

[manifest](manifest.json)记录80例原字节SHA、来源和个人eval指纹`e0e014b8ceb20050a8249cf7f30863642de262870777f435142feaba7afba77d`。只有cyanneko非空时suite_id为`baaf5b24e8a9697bc6cacb7e4f47c1e6d53b80e5f177fea0479ec06816702c63`；空成员跳过，不等待三人到齐，新增非空成员需重新发现并记录实际版本。

审核覆盖由原64不变字节的0.4实际记录与新增16的公共CLI/Root独立审核组成，见[0.5审核](provenance/public_audit_0.5.0.json)；没有冒称本次重新执行全80 CLI。新16三种流SHA互异，且与原64无重复。[生成器](../../generators/r61_mix/README.md)只复现新增8/8；不生成旧64或VERSION。

**数据初次发布时0.5.0完整40eval评分尚未执行；R63现已另行完成一次完整配对测量。** R60/R61公共成绩绑定冻结0.4.0的32eval；R61的新8例是独立冻结模型检验，不能将它和旧32测量拼成0.5完整重评或迁移cap50。新版本需按全部实际非空集合重新评分，官方Naive基线保持不变。

当前R63完整40例、17家族、D及开发消融见[进展报告](../../docs/NON_NEURAL_PROGRESS_20261029.md)。80次正式运行与36次开发运行分开；它只是一轮本地合成开发评测，不能预测未知官方分布或证明普遍改进。本次只更新说明，输入、meta、VERSION与数据manifest保持不变。
