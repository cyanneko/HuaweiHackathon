# R70 独立实验数据 1.0.0

24 train、8 dev、8 holdout，共40个真实输入、441120次操作。输入字节与生产方冻结SHA一致；`collection.json`记录逐例身份，`config.json`与`manifests/`记录种子、配方和split，`bounds/`保留18个静态train下界与6个mixed不适用说明。全部为合成数据。

本目录位于`experiments/`，默认评测器不将其作为成员数据集发现；旧三成员VERSION、785/576/30/dev24与final_dataset均不变。本实验版本为1.0.0，不能写作cyanneko eval版本。holdout已在model_v2冻结后使用一次，现已曝光，后续不得再称新盲测。

生成器与审核器的冻结源码在对应source/cyanneko R70证据包，原生产说明见`producer_README.md`。数据可直接下载使用；生成/训练脚本保留原研究布局的相对路径，重跑前按证据包manifest恢复布局和绑定运行环境。
