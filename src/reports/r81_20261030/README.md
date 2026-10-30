# R81 两时间尺度：完整四窗口归档

[完整报告](report_zh.md) · [438输出静态核验](publication_check.json) · [同轮回归审查](review/REGRESSION_REVIEW.md) · [逐例原始/裁剪诊断](review/regression_raw_clipped_cases.csv)。

两数据集样本各50%均分R81=4.050745、父版R80=4.000974；但final059成本/父版1.270355超过事前1.25门槛，双方裁剪分都0掩盖退步；官方均分+.049772而未裁剪诊断均分-.012767。后者是诊断，不改比赛评分。默认R75不变，不直接晋升。

TRAIN228/DEV30/dyna36/final144四窗口438格全保留，两个候选都保存，512只测TRAIN；256在TRAIN后身份冻结。同轮R75、R79、R80父版/paired都按实际所运行窗口保存，不能拼旧轮D。新18份150k输入（12TRAIN/6已曝光DEV）独立放datasets，旧26与回归输入只引用，不注册eval。

准备时的metadata快照另存preparation_manifest/README，完整源/测试/构建与已有测量为冻结审阅布局；未重跑程序或训练，不含ELF/private trace/R82结果。不宣称全final72/dyna12或隐藏成绩。
