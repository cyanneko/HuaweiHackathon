# R61 小树：条件性负结果与可复现材料

状态validated_negative、未推广、未接SDK。结论限定为原32训练案例的452个状态、全家族分组CV及旧0.4全部32eval的一次配对评测：树的CV宏平均归一化后悔0.166667，高于固定SF的0.100000；只有17个状态的两分支物理代价不同。它说明本轮标签/样本/模型未优于SF，不说明树或融合方法绝对无用。

原model.json、tree.hpp、model_freeze.json、labels.json、snapshots.json、tree_fit.py以及标签生成器/离线物理模拟依赖均按原字节保留；training_config列32个输入SHA、seed20612901、前/中/后段[5,5,6]采样、32物理行后缀、BF延续、16线上特征、六组深度/叶数配置及选择规则。后缀和miss_penalty仅用于离线物理标签，不能作为线上观测。历史字段里的“new-family holdout”不是完全未知基本家族保证，新8例是已知基本模式的新组合。

默认`python -B reproduce.py`仅校验归档SHA。显式`--mode fit-from-recorded-labels --out NEWDIR`可从冻结标签重做拟合/导出；`--mode regenerate-labels --datasets-root DATASETS_DIR --out NEWDIR`按冻结输入身份重建离线标签。输出目录须新建，最长60秒；这两项本轮都没有执行，不把提供复现入口称为本轮重训验证。label_source里的旧nn_training.py只因提供被原标签器调用的State/readcase而归档，线上不依赖它，也没有启动NN训练。

scheduler_snapshot.cpp是原正式构建中BF/SF、原树头及原policy的连续类体，加标准头后归档，无engine/main。原BF经类名替换为R53BestFit；SF为冻结R56SingleFitPhase。须放到原官方类型之后，仅替换MySpillScheduler实例。原头与snapshot不要同时include。本轮未重编译、未重跑求解器。

[原0.4逐例/家族/D和64份正式输出](../../reports/precontest_20261029/comparison_tables.md)保持不变；独立8例重试摘要在公共赛前报告。初次8例执行尝试另标execution_incomplete，净化摘要见initial_holdout_attempt.json；后来10秒窗口完成32运行。执行尝试失败与已完成方法的验证负结果分开，不改旧核心证据。
