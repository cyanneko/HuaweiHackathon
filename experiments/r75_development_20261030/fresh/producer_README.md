# R75 新随机开发验证

这 8 例是新 seed 的合成开发验证输入，不是官方测试集，也不是未查看过的 R72 holdout。每例 200008 个操作，总计 1600064 个操作。

生成前冻结 `config.json` 和 `source_freeze.json`，seed 为 202610307501–202610307508。配置理由逐例保存在 config。全部使用原 R72 generator.cpp 与 build/generator，partition-speed=.0025，未改变概率模型、未预定每算子/分区次数、未根据策略结果选择数据、未替换 seed。生成源码、二进制、独立审计源码/二进制及驱动 SHA 在前后均核验一致。8 例首次生成均成功；仅第 1 例持久热点、第 2 例持久冷点。

覆盖 slow/fast/burst、shared/staggered、K=2/4/8、P=16/32/64、目标压力1.5/3/6/12、周期 B=1/17/127/1000/10000、M=64MiB/256MiB/1GiB。高带宽小分区与低带宽大分区分别用于覆盖罚项较敏感和 IO 更显著的工作区间；这是参数选择理由，不是策略表现结论。

独立使用 R72 audit.cpp 已冻结二进制逐行审核输入的计数、阶段、键/元组大小、每分区容量和操作窗口，再用 run_audit.py 的 compare/check_configuration 核对 metadata、分区窗口及概率过程参数。概率轨迹检查归一、包络和聚合一致性，不宣称独立重放全部概率。逐例证据见 audit/；输入、metadata、两类窗口 SHA 见 manifest.json。

所有案例合法；实际压力1.49849–12.25172，最大单分区/M在各例间为0.02633–0.33993。未运行任何调度策略，未创建压缩包，未修改旧冻结文件或 Git。生成和审计总耗时约4.51秒，CPU已释放。

评估入口 `cases.json` 使用绝对 Linux 输入路径，每项有 id/path/sha256/group/family，group 固定为 fresh_validation。
