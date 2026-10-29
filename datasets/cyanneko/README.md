# cyanneko · eval0.6.0，train/eval各48

共96输入＋96原meta；原80对逐字保留，MXV1新增8训练＋8评测，配方固定后生成，无结果筛选或换seed。新增16对共21,279,105字节，首次生成/写入/严格审计5.625秒，第二次5.313秒，32个输入/meta文件逐字复现。Root独立核对16例共1,179,648 PROBE。

[manifest](manifest.json)绑定个人指纹`b22cd2f478cb798b84484ffe3432d54e1f25721314c65935c1a7d1fe5a0a3f50`；当前固定集合另有liunianwww0.1.0/528eval，共576eval，成员版本/指纹和suite见[集合快照](provenance/collection_0.6_snapshot.json)。空member2/member3跳过。后续仍自动发现所有实际非空成员，不能把48当团队总例数。

八组覆盖热点/冷流混合、大小/算子速率异构、跨64的全局重用距离、热点相位反转、大小热度反转、next诱饵、恰好M和多一整分区的活跃集、全驻留。train/eval使用不同组合/参数/种子，但共享已知基础家族；不是未知官方分布或盲测保证。最长eval262144 PROBE。

限制：mxv1_03_hotset_phase_reverse_train总build压力恰1.0，可全部驻留，应和两个fully_resident案例一起作为无压力对照；其eval压力1.3125。保留已冻结输入，不删除或改样本。冷频率按冷热事件各自累计ordinal生成，跨相位不重置，hot_stream全部对象确实被访问。

[生成器](../../generators/mixed_extremes_v1/README.md)、[实际审计](provenance/mxv1_generation_validation.json)、[Root复核](provenance/mxv1_root_review.json)与[用途/限制](provenance/mxv1_usage.json)分别记录。新16与旧80、liunianwww1128例的raw/操作流/modulo-P语义流均无碰撞；其他成员文件不改。

0.6全部实际集合尚无完整成绩。R63仅绑定旧冻结0.5/cyanneko40例，不能迁移到本版本或新成员集合；[历史结果与负结果档案](../../docs/EXPERIMENT_STATUS_20261029.md)保留原条件。数据合法、可复现不代表方法有效。
