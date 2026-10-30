# balanced_dataset 1.0.0：静态与动态各半的统一回归标准

后续方法比较默认使用本集：**24个完整案例，静态12＋动态12，每例等权，两侧各占50%**。这是已曝光数据的回归标准，不是独立盲测。原 `final_dataset` 72例与 `dyna_dataset` 12例保留，作为来源及扩展诊断，不改输入、种子、原划分或原版本。

| 分组 | 来源 | 选入 | 生成机制 | 评分权重 |
| --- | --- | ---: | --- | ---: |
| static | final_dataset 2.1.0 的72个eval | 12：Zipf5、热点5、对数正态2 | 固定非均匀概率、逐次独立Probe | 50% |
| dynamic | dyna_dataset 1.0.0 | 全12：slow/fast/burst各4 | 算子活跃度动态变化；普通分区条件概率近均匀且缓变 | 50% |

输入冻结于来源提交 `cf14092b6bc8a3bf8cfb65466c44acc81e2cf38a`。完整来源、SHA-256、原split及导出路径见 [manifest.json](manifest.json)；[设计审查](DESIGN_REVIEW.md)说明合理性及局限。

公共评测器预期 `suite_id`：

```text
a594b0d0e305b108ff10bd90677d7d0824001c369b3f05156cc8ab8243ed5887
```

## 抽样规则与规模

[selection_policy.json](selection_policy.json)在选样前冻结，未读取算法成绩：静态按原28/28/16比例分配12名额，最大余数并列时大族优先，得到5/5/2。每族按操作数排序，划成对应名额数量的连续秩分层，每层按固定salt、源路径、原SHA的哈希顺序择一。所有72候选、哈希排序与被选路径保存在 [selection.json](selection.json)。不因得分、压力或选出的参数不理想而重抽。

此处“相同规模”指**相同案例数**。静态每例78,260–1,048,576操作，共3,506,883；动态每例5,000,000，共60,000,000。总计63,506,883操作、原始输入1,243,788,102字节。没有截断动态序列或复制静态操作来伪造长度匹配。两侧操作数、运行时间或原始成本求和不等权；主评分按案例平均保证各半。

## 获取独立的可运行测试目录

本发布另存清单、固定选择与导出工具；复用仓库已有原件，不重复向Git上传约1.24GB输入。在包含来源文件的datasets检出中运行：

```sh
python -B balanced_dataset/tools/suite.py materialize --out /tmp/hashjoin-balanced-v1
```

工具从 `final_dataset/eval/*.txt` 和 `dyna_dataset/archives/*.txt.gz` 读取，完整复制/解压后逐个验证原始SHA与长度。也可以复用已有缓存：

```sh
python -B balanced_dataset/tools/suite.py materialize \
  --final-root /path/to/final_dataset \
  --dyna-root /path/to/dyna_dataset \
  --out /tmp/hashjoin-balanced-v1
```

缓存可以是保留来源布局的目录，也可以直接包含原文件名的平铺目录。动态支持完整原始 `.txt` 或原发布 `.txt.gz`；工具不自动联网。输出目录必须尚不存在；失败保留中间文件，不覆盖、不删除、不换样本。完成标记为 `READY.json`。

输出布局：

```text
hashjoin-balanced-v1/
  static/eval/       # 12个原字节txt、来源sidecar及VERSION
  dynamic/eval/      # 12个原字节txt、来源sidecar及VERSION
  manifest.json
  READY.json
```

在线调度器只读取框架允许的状态；sidecar中的分布、来源、原split不能提供给调度器。

## 审核与运行

原字节核验后，可调用公共评测器的输入解析/快照函数，独立审核全部操作并核对集合指纹；此命令不运行solver：

```sh
python -B balanced_dataset/tools/verify.py \
  --root /tmp/hashjoin-balanced-v1 \
  --snapshot /tmp/hashjoin-balanced-audit-v1 \
  --out /tmp/hashjoin-balanced-validation-v1.json
```

快照和报告路径必须尚不存在。本次发布的验证结果见 [validation.json](validation.json)；导出/选择/评分集成检查见 [tools/test_suite.py](tools/test_suite.py)。

用已接入官方框架的候选与Naive进行后续评测，所有选项放在 `--command` 前：

```sh
python -B evaluation/evaluate.py \
  --datasets-root /tmp/hashjoin-balanced-v1 \
  --timeout 60 --repeats 3 \
  --baseline-command-file /path/to/naive-command.json \
  --baseline-kind official-naive \
  --out /path/to/new-balanced-results.json \
  --command /path/to/solver "{input}"
```

`naive-command.json`是形如 `["/path/to/official-naive", "{input}"]` 的命令数组。程序须按官方C++14/O2框架构建。查看报告中的版本、输入SHA、suite_id及 `case-mean-v1`；少案例、缺重复、失败不得静默丢弃后报告完整成绩。正式60秒约束不因动态案例更长而放宽。

主分：

```text
s(i,r) = clamp(10 * (1 - candidate_cost(i,r) / naive_cost(i,r)), 0, 10)
score = mean_24_cases(mean_repeats(s))
      = 0.5 * static_mean + 0.5 * dynamic_mean
```

沿用官方零成本特殊规则。先逐重复归一化，再平均，不能先合并原始成本。必须同时报告两侧均分、逐例成本倍率、最坏退化、I/O、Miss和决策耗时。原split及异常类型进一步分组只作诊断，不改主权重；不能先把dyna的train/dev/holdout三组均值等权再充当12例均分。

## 使用边界

- 动态侧含原train6/dev3/holdout3，原标签完整保留。已有训练/开发和全12例比较曝光不能撤销；不能把导出到 `eval/` 解释为获得新的保留集。未来不从本集生成训练标签或拟合参数，探索用独立训练/开发流。
- 静态与动态在长度、压力、K/P、条件倾斜、带宽、罚值和阶段交错上也不同。本集覆盖两个场景，**不能隔离“跨分区相关性”这一因果变量**。
- 两类各半是本次约定的测试权重，不是官方隐藏分布比例。5/5/2只是72→12的整数近似，不能声称精确保留原三家族比例；尤其对数正态只有2例，不能作强分布结论。
- 完整72静态集继续可作扩展回归；其分数与本24例不同版本，不能把换集造成的均分变化算作算法进步。修改本集案例/权重须升版本、冻结新清单并重新审核。
- 本次只构建与审核数据，没有训练模型或测候选性能；不会自动改写正在运行的旧实验数据快照。
