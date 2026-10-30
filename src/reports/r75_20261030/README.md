# R75：算子权重增强与密集观察保护

[完整报告](report_zh.md) · [静态发布核验](publication_check.json) · [优先实验调度器](../../experiments/r75_dense_switch_20261030/MySpillScheduler.cpp)。主32格与针对B1回归3格分开，不将新开发数据称未见holdout。

八大例本轮Naive完整配对，case-mean-v1：R74为3.475946，保护版3.529315；原六例3.829316→3.899252。保护版对同轮R74平均含D成本比0.986125，7胜1负，最差1.000878。两候选主八例IO/hit/miss完全相同，约0.00001分差仅为单次D，不证明稳定胜负。B1针对开发例总成本比0.817941，单独列出不并入八例分。

保留所有负消融、phase_entry、独立review、修订和旧R74血缘。formal32含32原始格及程序身份；regression3包含Root独立3格。原zip184成员与冻结原件逐字节核对，因含本机执行命令而不直接发布；公开raw单独清理，原件与公开SHA分列，已执行命令字段省略。发布者重解析35份stdout、复算4方法八例/原六例/新两例均分、成本倍率及三条针对结果，未重跑程序、生成器或训练，未作新的逐动作审核。

10份新增实际压缩输入与生成/审核材料仅在datasets分支experiments/r75_development_20261030（8中型＋2配对规模，不是10个独立seed），不重复旧R72/R73。归档目录为审阅布局，按manifest source_record恢复相对路径并绑定运行环境后复现；标准库CPU/C++14/O2、只交调度器，默认不自动更换。旧R73/R74源码和数据保持原样，后续研究不混入此冻结版本。

[新增开发数据固定提交](https://github.com/cyanneko/HuaweiHackathon/tree/0bedef702d8810e634adf1947046e38677109d9e/experiments/r75_development_20261030)。formal32/targeted_regression只保留测试管理器的未执行接入准备，不计任何实测格；真正3条针对运行位于regression3。主32原zip不包含该未执行目录。发布者另外核对两条大例与各自中型配对除N外配置逐项相同。
