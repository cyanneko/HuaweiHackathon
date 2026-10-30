# R83 完整新覆盖面板

[完整报告](report_zh.md) · [144格静态核验](publication_check.json) · [独立复核](review/RESULT_REVIEW.md) · [逐例表](review/per_case.csv)。

TRAIN12×8+DEV6×8全部通过，没有因TRAIN选择器跳过DEV方法。R80双方案DEV5.088625，共享4.898059，收益主要在本小面板IID轨道；R81/singlefit仍有裁剪掩盖raw退化，R82旧TRAIN38失败保留。默认R75不变；完整原数据回归为独立R84，不能混用范围。

源码/TU/ELF指纹、协议、全部日志/分组/配对/谱系/选择诊断与审计齐备。输入只在datasets研究目录，12TRAIN只有6独立seed，DEV6另seed已曝光；不称OOD/盲测，不注册成员eval。原件/公开SHA分列，无新增native/编译/训练，不发布ELF；冻结脚本需恢复source_record布局与绑定依赖。
