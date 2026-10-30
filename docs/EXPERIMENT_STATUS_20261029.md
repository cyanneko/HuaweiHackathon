# 负结果、失败实现与未完成执行的归档约定

按最新要求，未胜出的方法也保留源码、模型、训练/标签配置、输入身份和结果；不以只上传成功者代替实验记录。状态区分：validated_negative为指定条件下已完成但未胜出的验证；implementation_failure必须有已识别实现错误；execution_incomplete是某次未完成执行；experimental_not_promoted是尚未推广候选。状态不混用，失败尝试不自动否定整个方法。

[完整方法索引](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/experiments)归档R61树、R62 soft/pair8和R63 Ghost。R61限定452状态、全家族CV与旧0.4/32，树未优于SF不代表树绝对无用；R62两位完成旧0.4/32单次但有严重尾部，pair8最坏43.695590倍。二者没有已识别实现错误，不误标implementation_failure。R61初次8例尝试单列execution_incomplete，后续重试完成。R63保持0.5/40实验未推广状态。

R61保存原模型、导出头、452标签与对应快照、trainer、标签来源模拟器、精确配置/32输入SHA，以及默认只做哈希校验的复现入口。未在本轮执行拟合、重建标签、旧solver或编译；不能把提供入口称为本轮重现成功。R62原源码依赖、固定公式和两个正式类体快照也保存。所有候选不注册新ID、不改默认SDK或官方Naive。

本页发布时的矩阵冻结旧快照为cyanneko0.6.0/48eval与liunianwww0.1.0/528eval，共576eval。2026-10-30核对的新快照另有Vanius0525 0.1.0/209eval，共785eval，固定提交与指纹见[更新清单](GITHUB_UPDATES_20261030.md)。旧结果保留原版本、成员与suite，不能自动迁移为576例或785例成绩。MXV1热点反转train压力1.0是无压力对照，详见生成器说明。
