# cyanneko · R48＋R54 开发数据，eval 0.3.0

本分支共有 48 份输入和 48 份同名原始元数据，train/eval 各 24 份。输入合计 15,839,087 字节，元数据合计 1,227,520 字节。R48 原有 16 份文件未改字节，新增 R54 v1.1 的 32 份；`eval/VERSION` 从 `0.2.0` 升为 `0.3.0`。

**数据用于开发/回归，不作独立盲测、官方隐藏分布代表性或泛化保证。** R48 全部曾参与历史开发实验；R54 是公开配置与固定种子产生的合成数据，train/eval 的划分与不同种子不意味着独立泛化分布。本次发布没有训练或求解器跑分。

## 划分与覆盖

| 来源 | train | eval | 说明 |
| --- | ---: | ---: | --- |
| R48 | 8 | 8 | 保留既有文件和元数据 |
| R54 v1.1 | 16 | 16 | 新增组合场景及极端/单模式对照 |
| 合计 | 24 | 24 | 同属 cyanneko 的一个有 VERSION 的集合 |

R48 train 为 `coverage_00,03,05,07,09,12,13,15`，eval 为 `coverage_01,02,04,06,08,10,11,14`。其中 `coverage_06..11` 为均衡分布诊断，其余为偏斜分布案例。

R54 文件名为 `r54_<category>_<variant>_<split>`。`cross_operator`、`temporal`、`combined`、`control` 各 8 例；前三类共 24/32，即 **R54 新批次的 75%** 属于组合场景。每例 24,123–50,463 条操作，共 1,124,488 条操作。v1.1 修正 control 元数据的目标压力标签，输入 raw 与研究侧 v1 相同；本仓库没有发布旧版标签。

R54 新增输入为 12,422,581 字节，元数据为 1,179,178 字节。每个算子只经历一次 BUILD→PROBE；Probe 模式的分段变化不表示回到 BUILD。具体模式比例、分段索引和统计保留在原始元数据中。

## 来源、哈希与校验

[manifest.json](manifest.json) 记录全部 48 例的仓库路径、来源相对路径、输入与元数据 SHA-256、操作流 SHA-256、划分、用途和发布来源。`evaluation_sha256` 对应个人 `0.3.0` 集合，不是多个成员的合并 suite_id。旧版本清单可从 Git 历史追溯。

- R54 原始文件逐一匹配已批准的发布冻结清单，复制时保留原始字节，Git 属性关闭换行转换。
- 全部 48 份输入经过公共校验器，0 错误、0 跳过；算子头按编号升序，完整输入及操作流哈希各有 48 个不同值，train/eval 及 R48/R54 之间无重复。
- R54 研究侧独立审核额外核对真实分段/索引、模式计数、scan/stride/burst 公式与热点比例；原记录随 [生成器 provenance](../../generators/r54/provenance/audit_v2.json) 保存。公共格式校验不能替代这些额外检查。
- 复制后的生成器通过 3 项测试，覆盖计划、压力标签和全部 32 配置双次生成的一致性。

本发布的可移植公共校验记录为 [public_audit_0.3.0.json](provenance/public_audit_0.3.0.json)，汇总为 [validation_0.3.0.json](provenance/validation_0.3.0.json)。这些验证不构成求解器性能结论，也不证明训练评测独立。

## 使用与复现

实际数据文件只在 datasets 分支。main/source 分支的评测器可通过 `--datasets-root` 指向本分支的独立工作目录。

在本分支仓库根目录检查输入：

```sh
python evaluation/scripts/audit_datasets.py --root datasets/cyanneko --out results/cyanneko-data-audit.json
```

可使用 [公共批量评测](../../evaluation/README.md)，默认评测所有成员已有的非空集合；空成员跳过，不计入分母。R48 和 R54 是同一 cyanneko 集合的内容，不会因分属两轮而重复算成两集。各集归一化分数独立计算，最终等权平均；无官方基线则不生成归一化分。

复现 R54：

```sh
python generators/r54/generate.py --out NEWDIR
```

输出仅含 R54 的 16/16，不包含 R48，也不会自动填写 VERSION。详见 [生成器说明](../../generators/r54/README.md)。请勿把固定种子的相同流复制到其他成员目录充当新测试集。
