# stat_dataset 1.0.0 发布与曝光状态

本目录保存已完成的40例、168M操作数据集：30 train、10 eval。只上传40个gzip压缩输入及冻结metadata、audit、source/tools/tests、配方与报告，不复制约3.299GB的raw输入。压缩输入约1.257GB，每个文件均低于100MiB。

188项生产白名单及其自清单publication_manifest.json全部保留原字节。manifest.json SHA256为d6a3584ab2385e45c7aeeb30a1c2c4d5fdda013dd0606ff994dc264463558149；原白名单SHA256为c9a194e0529c1abc7b0e067d2b00848bc8e833e69f36df180213365713914cdd。依manifest校验压缩件与解压后输入；原生成、完整合法性与gzip往返审核已有证据，发布者只核对复制文件SHA，没有重新生成、解压审计或执行策略。

**当前eval10已观察成绩。** 原README.md的“尚未策略评测”记录生成审核完成时的状态；随后用户单独授权R81/Naive各3轮，共60有效运行，已完成独立审计。因此不得再称eval10盲测或未曝光，也不将eval转为train。分数证据独立归档，不回写生产原件；后续BUILD/消融等实验同样单列身份和批次。

这是独立数据成果，不进入用户指定旧dyna1.0全12＋final2.1全72主榜，不改变最终R81选择或原成员VERSION/suite。publisher_state.json记录发布时曝光状态，原白名单继续只描述生产原件。

报告入口：[独立stat三重复](https://github.com/cyanneko/HuaweiHackathon/blob/230f5d927388979e286a0d8abdc8883876048315/docs/R81_STAT_RESULTS_20261031.md) · [BUILD对照](https://github.com/cyanneko/HuaweiHackathon/blob/230f5d927388979e286a0d8abdc8883876048315/docs/R81_BUILD_COMPARISON_20261031.md) · [创新消融](https://github.com/cyanneko/HuaweiHackathon/blob/230f5d927388979e286a0d8abdc8883876048315/docs/R81_ABLATION_20261031.md)。

冻结生产目录见[e78279e3](https://github.com/cyanneko/HuaweiHackathon/tree/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset)，原README等188项生产文件和自清单保字节；本发布说明与publisher_state为另附派生状态，不进入生产白名单。
