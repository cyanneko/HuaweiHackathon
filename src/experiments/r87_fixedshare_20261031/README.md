# R87 算子Fixed-share实验候选

原字节MySpillScheduler类，无main；完整TU/测试/编译说明见[报告包](../../reports/r87_20261031/README.md)。C++14/O2、纯CPU/标准库。先以旧预测更新后验再计新标签，alpha1/256，两专家混合；慢分区条件不变。不是神经网络，不保证logloss收益转为spill成本收益，未晋升，默认R75不变。
