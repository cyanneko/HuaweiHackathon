# 当前评分标准：所有案例逐例均分

2026-10-30 用户明确更新；本规则覆盖旧“成员内sum再成员等权”和封顶分主排名。评分版本为 `case-mean-v1`，`evaluate.py` 报告 `schema_version=4`。后续统计、汇报和选型均以本页的平均分为标准。

每个案例 i、第 r 次重复，先用同批官方 Naive 成本 B 和候选完整成本 C 计算：

```text
s(i,r) = clamp(10 * (1 - C(i,r)/B(i,r)), 0, 10)
score_final = (1/N) * sum_i [(1/R) * sum_r s(i,r)]
```

C、B 均包含 I/O、miss penalty 和实际调度器决策耗时；沿用官方零成本规则，C=0 或 B=0 时该例记0。未优于基线同样记0，仍占案例分母。先算每次重复的比例与截断，再取均值，不能先平均成本再算分。

N 是本次选定非空评测集合的全部案例数，R 是统一重复数。每例权重相同；成员/家族分组仅用于分析，不因目录划分改变总均分。合并成员均分时按案例数加权。例如A有1例得5分，B有6例各得9分，总均分是 `(5+6*9)/7=8.428571`，不是成员均分的简单平均。

## 8例正式测试与目标

用户提供正式测试共8组。按当前Level 1规则：

```text
正式8例的Level1 = min(50, 8 * 正式8例均分)
目标均分 = 50 / 8 = 6.25
```

6.25对应Level 1封顶，但平均分本身仍可达到10，不在6.25截断。50例本地均分不是正式8例均分；不能用本地成绩乘8承诺隐藏成绩。总成本下降比例也不等于此均分，尤其逐例负收益被截为0时。持续展示逐例成本倍率、严重退化、I/O、miss与决策耗时。

## JSON与旧报告

- 新runner：`normalization.average_score` 为0–10的全案例均分，`normalization.datasets[].average_score` 为分组均分；终端也以均分展示。
- 只读汇总器：`score_final` 是同一均分，`member_weights` 为各成员案例数/N；`summary_schema_version=2`。
- `target_average_score=6.25` 仅记录上述正式8例目标。
- `level1_estimate`、`legacy_capped_member_average`、未封顶sum等仅为兼容诊断字段，不用于排名。旧schema3的 `normalization.average_score` 是成员封顶分平均，不能直接当新均分读。
- 评分规则更新不改输入、metadata或eval/VERSION；当前综合集仍2.0.0。比较还须绑定suite_id、scoring_version、程序/基线身份、编译环境和重复数。

从已有schema3或schema4原始报告重算，无需重新执行求解器：

```sh
python -B evaluation/scripts/summarize_member_scores.py results/original-report.json --out results/case-mean-summary.json
```

汇总器只读原始逐例逐重复贡献，另写新文件；保留输入报告哈希和旧封顶值，不改旧证据。它不接受只有总分而没有逐例记录的摘要，也不认证程序动作是否合法。

## 失败、缺失与范围

空/尚未上传的集合可明确跳过，实际参与案例数写入报告。显式子集标partial。已有案例不得因为低分、失败、超时、缺重复而被丢掉后求均分；完整案例×重复矩阵必须齐全。

当前本地runner遇到执行失败、输入错误、缺重复或无有效官方基线时，输出unavailable/null并使整轮无有效排名；不会拿成功部分给“完整均分”。官方OOM/超时按该例0分的规则不改变，若另算官方式失败含零诊断，必须保留预定N且单列失败，不能伪装成本地完整有效评测。

所有案例等权是本轮统一目标，不代表已知官方各随机分布比例。相同N/J下旧未封顶成员sum平均与新逐例均分仅差常数N/J，固定集合的排名相同；封顶值和raw成本比则不具备这种等价性。
