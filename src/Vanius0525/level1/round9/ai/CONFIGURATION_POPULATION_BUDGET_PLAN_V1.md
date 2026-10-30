# 配置选择人口与预算核查计划 V1

2026-10-30，root授权的只读元数据可执行性核查，不是实验。已发布27b8faf阶段及原NEXT_CONFIGURATION_RESEARCH_DESIGN_V1、所有完成freeze保持不改；当前不最终选24seed、不读取原始trace、不运行collector/teacher/solver/训练，不访问主dev/eval输入或成绩，不使用dyna成绩。

只读固定V21_DATASET_LOCK，以及其SHA绑定的本地manifest/recipe/selection。联合容器必须先以lock.train过滤，后续仅保留train432的身份、seed、family、三种指纹、N/INSERT/PROBE/K、文件字节、phase_overlap和added标志。初始查看联合锁JSON结构时误打印了cases首条eval的路径/seed/family/三种hash；未读该输入或成绩，未用于统计/选样。本审计明确记录这一metadata-only接触，不声称从未加载包含eval的联合元数据。

在train内按seed、raw SHA、operation-stream SHA、partition-stream SHA构建连通分组；排除任何与原pilot60相连的分组，核对残余分组是否单例。该检查只覆盖已有指纹所定义的亲缘，不把不同seed自动当统计独立或历史未曝光证明。

同时报告两个候选人口：全部train扣除pilot亲缘后的集合；其中属于2.1 added_training_paths的子集。不选择其中一个作新执行集，不以大小/成绩挑24seed。每族报告例数/组数、N/PROBE的min/median/max/总和、长度档位、原始文件字节。

保持首选每族8seed、总24作为预算约束，仅计算边界：对各族取给定表达式的8个最大/最小值，求可达数量上限/下限，不输出或指定这些边界对应的24例名单。不同表达式的极值可能对应不同集合，不混称一份已选计划。

合法决策点q0未知，不能用离线最后SWITCH代替q_base。仅用保守不等式q0≥4096；全PROBE后没有剩余BUILD/SWITCH，故每条实际配置后缀最多max(PROBE−4096,0)条请求。四分支最多4倍该量；另保守计一次完整N的共同collector，合计W=N+4max(PROBE−4096,0)。不提前折扣paired控制复用。真实后缀、无决策流、回调/动作密度、CPU、峰值RAM与TRACE体积仍未知；不据历史不同任务耗时承诺本任务秒数。

本阶段只产生人口/工作量JSON、复现脚本和说明文档。配置成本互补仍待root对主60的固定配置验证；人口足够或预算可承受都不是可学习性证据。
