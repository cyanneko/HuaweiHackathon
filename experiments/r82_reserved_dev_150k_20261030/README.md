# R82 保留DEV 1.0.0

12份合法新DEV，各150000操作，共180万操作、36,559,012原始输入字节，6条seed各none/hot成对，不是12条独立seed。因为两个候选TRAIN均未晋级，本批没有运行任何策略、没有DEV成绩，仍属reserved，禁止当TRAIN或已验证成绩。

inputs.json提供公开input/meta路径和SHA、原38TRAIN固定引用；旧数据不复制。附生成参数、审核及概率窗口CSV和生成stdout/stderr；这些仅供离线生成审阅，不是线上特征。没有eval目录、不注册比赛测试，不改旧VERSION/suite/发现器。

发布者核24份input/meta SHA与头部计数，完整逐操作合法性继承绑定生成审计，未独立重做；未新增生成、策略、编译或训练。R82结果见独立source报告，默认R75不变，原DEV划分保留。冻结脚本执行前需恢复source_record映射与环境。
