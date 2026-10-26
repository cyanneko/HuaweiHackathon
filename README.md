# 华为 Hackathon · 第20题 Hash Join 调度

团队协作仓库，研究内存受限下 Hash Join 算子的 Spill-to-Disk 动态调度。

## 分支约定

| 分支 | 用途 | 当前状态 |
| --- | --- | --- |
| `main` | 公共说明、评测工具、数据规范；后续集成方案 | 已创建 |
| `datasets` | 三名成员的训练集与评测集 | 已创建 |
| `source/cyanneko` | cyanneko 的算法源码 | 已创建 |
| `source/<成员2>` | 第二位成员的算法源码 | 成员加入后创建 |
| `source/<成员3>` | 第三位成员的算法源码 | 成员加入后创建 |

最终共五个长期分支；初始化阶段只创建前三个。

## 目录

公共目录在三个现有分支均可见：

```text
evaluation/
  README.md                  # 使用方式与版本边界
  DATA_SPEC.md               # 数据格式与团队提交规范
  evaluate.py                # 批量评测三人测试集，成绩绑定数据版本
  scripts/
    audit_datasets.py        # 输入数据校验
    legacy_checker.py        # 旧版本地动作核算器
```

`datasets` 分支另有：

```text
datasets/
  cyanneko/
    train/
    eval/
      VERSION
  member2/
    train/
    eval/
      VERSION
  member3/
    train/
    eval/
      VERSION
```

`source/cyanneko` 分支另有 `src/`，用于个人源码。初始化不上传原有实验、模型或训练数据。

## 协作方式

- 数据提交到 `datasets` 分支下自己的目录；`member2`、`member3` 为待重命名占位。
- 算法提交到各自 `source/<GitHub用户名>` 分支。
- 公共工具与规范在 `main` 更新，再同步到其他分支。
- 训练集与评测集分开维护，避免同一操作流同时出现在两者中。
- 数据和算法分支不需要整体合并到 `main`；只合并明确需要的公共内容或集成方案。

新增成员示例：

```sh
git switch main
git pull --ff-only
git switch -c source/GITHUB_USERNAME
git push -u origin source/GITHUB_USERNAME
```

从源码分支临时读取数据，可使用 `git restore --source=origin/datasets -- datasets`；不要把取出的数据顺手提交进源码分支。

## 批量评测与成绩版本

在拥有三人数据的工作目录中运行（所有评测选项放在 `--command` 前）：

```sh
python evaluation/evaluate.py --datasets-root datasets --out results/run-001.json --command ./build/solver "{input}"
```

如果程序从标准输入读取，去掉 `"{input}"`。输入参数路径支持空格。

成绩 JSON 与终端摘要包含三人的 `VERSION`、SHA-256 和整套数据的 `suite_id`。比较成绩时应核对 `suite_id` 及评测脚本版本，不能只看人工版本号。脚本先复制数据快照再执行，原始数据后续修改不会混入本次结果。

三人集合目前为空，须填入数据才能完成正式批量运行。任一集合为空、缺少版本、程序失败或超时，都不会产生有效总成绩。完整用法见 [evaluation/README.md](evaluation/README.md)。
