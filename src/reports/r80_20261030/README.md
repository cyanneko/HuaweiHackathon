# R80：final24与dyna6完整归档

[最新完整报告](report_with_dyna_zh.md) · [final24-only原报告](report_zh.md) · [动态30格](dyna/final/summary.json) · [两dataset等权静态核验](dyna_publication_check.json) · [补充复核](supplement_review/)。

同批含D均分：R79/Van/paired_fast/hier_fast在final24为3.704079/3.846528/3.991113/4.090298，在dyna6为3.938158/3.641676/3.960575/3.911797。各dataset先按案例等权，二者各50%得到3.821119/3.744102/3.975844/4.001048。动态子集hier低于R79和paired，不能只展示静态收益。单次重复及仅0.0252的合并差不支持稳定优胜或自动晋升，默认R75不变。

原三个窗口354格及新动态30格分开保留，384/384有效；动态6例各5M、原4train2dev且早已曝光，只作回归、禁止AI拟合。动态360s控制器实际226.028s，官方60s单例，两者不同。原12份dyna总体不改、未冒称跑全12或24份动态输入。两dataset均分各占50%，不是30点等权，也不是balanced_dataset的结果。

保留全部6候选、旧2xD门槛和用户在final前撤销门槛的记录；原paired只是由物理行为一致的按需实现优化，不标算法失败。10新合法TRAIN/6谱系和失败诊断在datasets独立归档，旧16/final/dyna输入都不复制。无ELF/private trace/不完整input，不承诺无需环境映射的一键重放。原SHA/公开SHA分列，原final24-only公开清单另存primary_manifest.json。
