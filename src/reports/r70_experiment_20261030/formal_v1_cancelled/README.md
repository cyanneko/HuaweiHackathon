# R70 在线评测入口

本轮现已由 Root 预先固定 model_v1，执行以 [README_96.md](README_96.md) 和 `model_v1.precommit.json` 为准：dev48 有效且身份不变即自动 holdout48。以下分段选择步骤保留为前期准备记录，不再要求中途人工确认。

本目录准备 dev8 选定候选、再对 holdout8 做一次评测的独立入口。对照为 Naive、R65、VanBest、LiuFinal、对应无 NN 启发式、32→16→1 tinyNN。当前只有元数据和接入约定，等待 Root 给出后两份冻结源码及模型身份。

## 已冻结内容

- `selection.template.json`：四个既有程序的源码、完整翻译单元和程序 SHA，以及两个待绑定导出。四个未改源码的方法复用已编译程序，运行前重新核对其实际二进制 SHA。
- `dev_cases.json`：八个开发案例的输入和审核元数据身份、Probe 数及计分参数；原始字节将在获准运行时复核。
- `holdout_seal.json`：只封存 holdout 清单 SHA、配置身份和解封条件。本准备脚本不打开 holdout 输入正文，也不产生 holdout 性能或拟合标签。
- `entry_contract.json`：已验证的执行辅助工具、指标解析器、官方框架及本轮目录和门控约定。

全部输出位于本目录，final_dataset v2 的冻结榜和原始结果保持独立。

## 最短接入步骤

1. Root 交付无 NN 启发式和 tinyNN 的单文件 `MySpillScheduler` 源码及 SHA；tinyNN 同时绑定权重、32 维特征定义和预处理 SHA。源码只使用合法当前状态、自身历史和 next_op；线上不读取未来、输入总 N、文件身份或隐藏 miss_penalty。
2. 将两个待绑定记录写入新的 `selection.bound.json`，保留模板。用已有冻结官方框架只替换调度器及工厂，按同一 `g++ -std=c++14 -O2` 编译这两个新文件；四个既有源码不重复编译。构建放在 Root 允许的窗口，保留完整源→框架→二进制链。
3. 输入复制到运行时实际 Linux HOME 下的持久目录，验证原字节和元数据 SHA。跨两次独立 WSL 调用检查哨兵、输入及程序身份，避免短生命周期 `/tmp` 丢失。dev 只读取 `dev_cases.json` 的八例。
4. 最薄执行层可复用 `entry_contract.json` 指向的 sealed `linux_batch_worker.py`，生成本目录专用 job manifest；也可仅复用原 `runner.py` 的 `checked_run` 和五指标解析器。不得调用旧 final50 `main`、旧门控、旧输出路由或其硬编码 700 格逻辑。
5. dev job manifest 为 6×8×1=48 格，按 case-major 串行执行，Naive 对每例每重复只测一次并配给各候选。每 job 绑定 `input_sha256/binary_sha256/framework_sha256/params_sha256`；新 scope、split、方法清单、运行配置和模型身份进入 params SHA/cache key。使用短 batch/cell 标识，本目录 `dev/raw` 保存原始结果。
6. Root 给出模型 SHA、Worker 与训练释放状态、正式 D 时间窗后，才启动 dev formal。所有结果保留五项指标、原始 stdout/stderr、程序退出和超时状态。输入非法、缺格或候选失败不能静默丢弃后声称完整分。
7. Root 基于 dev8 冻结最终选择，写 `dev_choice.freeze.json`，其中绑定 dev 报告 SHA、选定源码/模型/特征/预处理 SHA 和拟采用的六个对照身份。此后模型和评分规则不再根据 holdout 改动。
8. 新的 holdout release 必须匹配该选择记录和 `holdout_seal.json`。到这一步才展开八份 holdout 输入身份、审核元数据和必要计分参数，产生 48 格专用 job manifest。只进行一次正式 campaign，输出到 `holdout/raw`；失败与未完成状态原样保留，不以反复试跑作选型。

## 汇总口径

每例沿用 `clip(10*(1-C_candidate/C_naive),0,10)`，原实现的非正成本边界不变。单 split 的八例贡献求未封顶 sum，重复时先对 sum 取均值；同时单列 sum/8 的逐例均分。理论未封顶上限为 80。dev 和 holdout 分开报告，数据集合与 source/model 身份分别冻结。

并列成本/Naive 的 mean、P50、P90、worst，逐例 IO、miss 与每例累计 D，展示全部退化。D 单位为微秒，是完整案例内正式回调耗时之和，不是单次决策耗时。离线 IO+miss 解质量不混入在线含 D 排名。

当前未运行 WSL、编译、求解器、训练或 formal D。本入口不承诺尚未产生的模型效果。
