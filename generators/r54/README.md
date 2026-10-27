# R54 v1.1 组合数据生成器

Python 标准库实现，不依赖固定工作区路径、GPU 或第三方包。使用一个尚不存在的新目录：

首次接手可先看 [Agent 指南中的数据流程](../../docs/AGENT_GUIDE.md#数据与新增数据的流程)，区分复现这一批数据与新增独立数据。

```sh
python generators/r54/generate.py --out NEWDIR
```

输出 `NEWDIR/train/`、`NEWDIR/eval/` 各 16 份 `.txt` 和同名 `.meta.json`，并保存 `plan.json`、`manifest.json`。已存在的输出目录会被拒绝，避免覆盖原数据。固定配置和种子用于复现这一批数据，重复生成不构成新的独立测试集。

## 场景构成

| 类别 | 数量 | 说明 |
| --- | ---: | --- |
| `cross_operator` | 8 | 不同算子具有不同 Probe 访问模式 |
| `temporal` | 8 | 算子内部的 Probe 访问模式分段切换 |
| `combined` | 8 | 同时具有算子间异质、时间分段与推进速率变化 |
| `control` | 8 | 极端容量或单模式对照 |

新增 32 例中有 24 例属于组合场景，占本批次 75%；train/eval 各 16 例。每例约 24,123–50,463 条操作，共 1,124,488 条操作。原始输入合计 12,422,581 字节，v1.1 原始元数据合计 1,179,178 字节。

v1.1 修正了对照组的目标内存压力标签，使其对应实际显式构造；32 份输入操作流与研究侧 v1 保持原始字节相同。本仓库只发布 v1.1 元数据，不混入旧标签。

每个算子只经历一次 BUILD→PROBE。所谓时间切换是 Probe 访问模式切换，不是重新进入 BUILD。元数据包含固定种子、模式分配和实际比例、算子分段、分区大小与实际压力；分段 Probe 索引采用算子内零基、左闭右开区间，全局操作位置采用排除头部的一基编号。

## 验证与来源

```sh
python -m unittest discover -s generators/r54 -v
```

三个测试覆盖配置比例、压力标签和全部 32 个配置双次生成的可复现性与真实段落/索引检查。严格字节复现应保持 Python 版本和平台换行设置一致；本发布使用 Git 属性保留原始脚本和元数据字节。输入由 ASCII 字节直接写出，元数据由文本写出。

`provenance/` 保存原始发布的计划、生成清单、`audit_v2.json` 和冻结清单。冻结清单包含研究侧额外文件的来源哈希，不表示这些研究脚本或日志都随仓库发布。依赖研究工作区路径的 `verify_release.py` 未作为独立工具上传。

发布的合法性与分段统计审核不等于求解器性能验证。本批数据是合成开发/回归数据，不作盲测、官方隐藏分布代表性或泛化保证；本次没有训练或求解器跑分。

## 与协作仓库的数据目录

实际已发布数据仅在 [datasets 分支](https://github.com/cyanneko/HuaweiHackathon/tree/datasets/datasets/cyanneko)。保留 R48 的 16 份后，合计 48 份，train/eval 各 24，个人 eval 版本为 `0.3.0`；main 与 source 分支只有工具、说明或方法源码。

生成器输出是单个成员的 train/eval 包，不是多成员 datasets 根目录，也不会自动填写 VERSION。将自有数据纳入公共评测前，应按 [数据规范](../../evaluation/DATA_SPEC.md) 建立成员目录、填写版本号并校验；不要把这一批相同操作流复制到多个成员目录充当新数据。

公开输入校验使用 `evaluation/scripts/audit_datasets.py`。本次对全部 48 份输入的可移植公共校验记录位于 datasets 分支的 `datasets/cyanneko/provenance/`。
