# MXV1 固定组合与边界生成器

配方recipe.frozen.json SHA28e8eb5e13dbde42f2c1ba75980d850ea8982519c909be866ed88e778da5a84f。旧58bb稿仅draft，Root指出冷热计数歧义后改为热/冷事件各自累计ordinal，跨phase/prelude不重置。生成只读固定配方/旧输入身份，不读solver、模型或成绩，不失败换seed。

`python -B generators/mixed_extremes_v1/test_generate.py`检查5个小调度边界；`python -B generators/mixed_extremes_v1/generate.py --out NEWDIR --max-seconds 60`生成8train+8eval，输出必须是新目录。只产本增量，不自动合并旧80或创建VERSION。源代码/测试/recipe/旧身份/公共审计器在source_freeze中预先绑定，README不在该源码冻结范围。

八类场景和精确字节/seed/时序在配方中，train/eval不同参数与组合。总1,179,648 PROBE、最长262144；16输入/meta21,279,105字节。首次生成+写入+官方严格审计5.625秒、重复5.313秒，32文件原字节一致；无solver/编译。三种流签名各16唯一，与旧80去重；成员后续新增的liunianwww1128例又从固定Git blob重新规范化流补查，也无碰撞，不更改其他成员输入。

覆盖限制：hotset_phase_reverse_train总build=M、压力1.0，可全部驻留，是无压力热点反转对照；加两个fully_resident共3条无压力控制。eval对应压力1.3125。没有据此删改冻结输入或补种子；它不是“所有train都有容量压力”的数据。原Root审查与复现记录在provenance。

数据是已知基础家族的新固定组合/参数，非未知官方分布保证。数据只在datasets分支；追加后cyanneko0.6.0为48/48，全团队当时有两非空成员、共576eval。0.6完整性能尚未测；R63旧0.5记录不能迁移。公用auditor仍是原文件，未改官方限制或评分器。
