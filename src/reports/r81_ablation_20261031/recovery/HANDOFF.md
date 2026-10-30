# 多批来源消融分析交接

CPU RELEASED。预算恢复补充9/9有效、零编译，实际console总115.180456913秒（completion文件记录115.079602389秒），少于180秒，最终进程组全部释放。

原846格attempt仍永久为INCOMPLETE：845有效、stat最后UniformOperatorMarginal被450秒阶段预算截断，有效timeout3.636722541秒，不是60秒方法超限。原completion SHA仍为ff3d6dffb0b4618fb4ba780388e9e4542670271014ab8994ecd502fd85faf482，原目录没有publication。

按恢复前固定协议，最后stat用例的九种方法整批新测，新Naive与新D全部来自该批。原最后用例8个成功行及1个超时行完整保留但全部排除，不择优。最终有效分析矩阵=837原行+9恢复行=846；实际两个campaign总尝试855格。旧dyna12/final72不重跑、不更改分数。

| 方法 | dyna12均分 | final72均分 | 两套50/50 | 独立合并stat10均分 | Full主榜减消融 |
|---|---:|---:|---:|---:|---:|
| Naive | 0 | 0 | 0 | 0 | 4.084507912 |
| Full | 4.455849488 | 3.713166337 | 4.084507912 | 3.439812321 | 0 |
| FixedShare075 | 4.458017537 | 3.639784785 | 4.048901161 | 3.408577701 | 0.035606751 |
| UnifiedSlow2048 | 4.306732593 | 3.709111805 | 4.007922199 | 3.494851339 | 0.076585713 |
| NoPeriodicPrefetch | 4.455155689 | 3.710343805 | 4.082749747 | 3.445588140 | 0.001758165 |
| NoNextProtection | 4.434520653 | 3.683534013 | 4.059027333 | 3.421778951 | 0.025480579 |
| UnitMissCost | 4.133023835 | 3.207240512 | 3.670132173 | 2.602840797 | 0.414375739 |
| NoStructurePolicy | 4.455852364 | 3.713121148 | 4.084486756 | 3.439700271 | 0.000021156 |
| UniformOperatorMarginal | 1.725921918 | 3.651430345 | 2.688676132 | 3.309180302 | 1.395831780 |

均分是每例0–10分后取均值，主榜两套各50%，不按84例等权，不混stat。C采用原生stdout Total_Score，物理与D分开保留，未截断值/全部负例在CSV与summary。

最大条件贡献是算子热度差异和读写/代理罚值异质代价评分。其消融后相对Full物理成本比，各套case均值再50/50分别约1.356849778及1.086455561。统一时标1.011091822，固定共享1.006043401，去next保护1.003549588，去periodic预取1.000639890。

负面边界：固定.75共享在dyna略优于Full；统一慢时标、去periodic预取在stat反而更优。NoStructure在主两套全部物理指标与Full一致，微小分差来自单次D，不支持物理收益声明。单因子移除是条件贡献，不能相加；保留观测维护的D不是完整可省模块计算量。NoPrefetch改变未来miss/可见信息，NoStructure同时关闭scan/cycle，UnitMissCost保留cold-start带宽门与容量密度。输入为已暴露本地synthetic，不能保证隐藏测试或创新30分。

证据入口：publication.json（SHA53a9793e38a6de472ae0c22e5a57d59e93c6763b840915adee04b958150fd851）、attempt_completion.json、verification.json（846原stdout/stderr重新解析与hash、188同输入Full/Naive物理控制）、source_mapping.json（846格精确批次映射）、merged_stat/summary.json、provisional/combined_dataset_equal.json、provisional/per_case.csv、provisional/REPORT.md。provisional目录文件已由publication绑定，冻结内容不再改。

最终只读交接检查通过：publication及报告hash一致、选定846/控制188、837旧+9新、原INCOMPLETE文件hash未变、children0。独立审计agent负责最终中文REVIEWED_REPORT；本实验无调参、选优晋级或共享Git修改。
