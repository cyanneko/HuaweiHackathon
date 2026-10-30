# R84 含Van完整12/72回归

[完整报告](report_zh.md) · [发布静态核验](publication_check.json) · [独立复核](review/RESULT_REVIEW.md) · [全部逐例CSV](review/per_case.csv) · [七方法类](../../experiments/r84_full_comparison_20261030/README.md)。

正式v2：dyna12×7=84、final72×7=504，共588格/1176份日志全部通过，CPU串行一次，无策略重跑或默认晋升。v1在metadata路径预检失败、尚无selection/campaign/native，完整失败材料保留。

两套各50%：R81 4.084522、R80共享4.008007、R80双方案4.003133、R79 3.799665、Van 3.766640、R75 3.606490。R81 final raw均分比R80共享更低，28胜44负，059例成本1.270431倍，不能因裁剪均分最高就安全替换默认。

输入只复用固定datasets提交，保留原split和曝光状态，不含final train/inde/成员套件。归档完整协议、参数、源码/TU/ELF指纹、绑定环境、门禁、原始stdout/stderr、全部逐例/分组/尾部及失败。只提供源文件与构建说明，不提供ELF；命令路径清理且冻结脚本需恢复source_record布局，不声称一键复现。原始与公开SHA见manifest，发布者无新native/编译/训练。
