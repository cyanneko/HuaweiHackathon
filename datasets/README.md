# 团队数据集

先读 [Agent 指南的数据流程](../docs/AGENT_GUIDE.md#数据与新增数据的流程)，按当前 manifest/VERSION 维护数据与发布记录。

本分支按成员维护数据；当前 `cyanneko` 有数据，`member2`、`member3` 为待重命名的空占位，新增成员可按规范加入。

每人目录包含 `train/` 和 `eval/`。`cyanneko` 当前保留R48/R54/R58/R61共80份输入及原始元数据，train/eval各40，评测集版本为 `0.5.0`。划分与来源见 [cyanneko/README.md](cyanneko/README.md)。

R48 为历史开发输入，R54 为可复现合成开发数据；`eval` 不作独立盲测声明。`member2`、`member3` 仍为空，版本仍为 `0.1.0`；它们会被跳过，不阻塞已有版本。实际数据仅在本 datasets 分支，main/source 分支只提供公共工具或方法。

修改评测案例后请升级自己的 VERSION，例如从 `0.1.0` 改为 `0.1.1`。评测器还会计算内容指纹，防止只改文件却忘记改版本号。训练数据的变化不会影响评测指纹。

不要把同一操作流放进训练集和评测集；提交前按 [数据规范](../evaluation/DATA_SPEC.md) 检查输入。至少一个合法非空评测集即可使用 [公共评测入口](../evaluation/README.md) 运行；报告记录实际参与版本和跳过成员。

默认发现所有成员的非空 eval；有官方基线时逐集计算归一化分数，再对各集等权平均。R48、R54 合在 cyanneko 的一个有版本集合中，不作为两个成员集合重复计入分母。


## liunianwww 新增数据

新增 `liunianwww/train` 600例及 `liunianwww/eval` 528例，评测版本 `0.1.0`。现有cyanneko全部80例、元数据及0.5.0版本原字节保留，未覆盖或删除。
合并后train共640例，eval共568例；默认自动发现两个非空成员。新增数据来源、历史开发暴露、操作流隔离与均衡诊断标签见 [liunianwww/README.txt](liunianwww/README.txt)。

```sh
python evaluation/evaluate.py --datasets-root datasets --repeats 3 --out results/merged.json --command ./build/solver "{input}"
```

这些集合属于开发/回归数据，不作未来未见盲测或官方分布声明。实际Score倍率与D倍率应连同成员、VERSION及suite_id报告；总成本之比与逐例等权平均不能混称。
