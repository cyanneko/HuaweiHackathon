# 三人数据集

本分支集中管理三位成员的数据；`cyanneko` 为已确认成员，`member2`、`member3` 为待重命名占位。

每人目录包含 `train/` 和 `eval/`。`cyanneko` 已上传 R48 的 16 份历史开发输入及原始元数据，训练目录与开发回归评测目录各 8 份，评测集版本为 `0.2.0`。划分与来源见 [cyanneko/README.md](cyanneko/README.md)。

全部 16 份输入均已参与历史开发实验，`eval` 是开发/回归集合，不是独立未见测试集。`member2`、`member3` 仍为空，版本仍为 `0.1.0`；它们会被评测器跳过，不会阻塞 cyanneko 已有的 `0.2.0` 版数据。

修改评测案例后请升级自己的 VERSION，例如从 `0.1.0` 改为 `0.1.1`。评测器还会计算内容指纹，防止只改文件却忘记改版本号。训练数据的变化不会影响评测指纹。

不要把同一操作流放进训练集和评测集；提交前按 [数据规范](../evaluation/DATA_SPEC.md) 检查输入。至少一个合法非空评测集即可使用 [公共评测入口](../evaluation/README.md) 运行；报告记录实际参与版本和跳过成员。


## liunianwww 新增数据

新增 `liunianwww/train` 600例及 `liunianwww/eval` 528例，评测版本 `0.1.0`；原有 cyanneko 16例保持原字节与版本。
新增输入已通过范围、阶段、计数、容量、升序头与元数据校验，训练/评测操作流隔离。来源、历史使用和诊断标签见 [liunianwww/README.txt](liunianwww/README.txt)。

合并后的 eval 共536例。公共工具的默认成员列表仍为旧名单，评测时需显式包含新成员：

```sh
python evaluation/evaluate.py --datasets-root datasets --members cyanneko liunianwww member2 member3 --repeats 3 --out results/merged.json --command ./build/solver "{input}"
```

所有这些输入都属于开发/回归数据；不要将已公开、调参或评分的集合称为未来未见盲测。
