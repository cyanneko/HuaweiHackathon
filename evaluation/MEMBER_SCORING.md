# 当前主评分：先逐成员数据集求分，再等权平均

日期：2026-10-29。原始评测器、逐例函数和raw报告保持不变；下面的未封顶汇总由已有逐例贡献计算，不重新运行求解器。

原逐例贡献为`p(m,i,r)=clip(10*(1-C_candidate/C_naive),0,10)`。沿用现有runner边界：VAL或BASE不为正时该例原贡献为0；新增摘要直接使用并核对原`single_score`，不暗改零值规则。

```text
score_dataset(m) = mean_repeats(sum_cases(p(m,i,r)))
score_final = mean_nonempty_members(score_dataset(m))
```

逐成员求和时不施加50的总分封顶。每个非空成员在最终平均中权重相同，各集内部仍累加全部逐例贡献；案例数会影响该集未封顶总分的范围。当前固定快照有cyanneko0.6.0/48例与liunianwww0.1.0/528例，成员系数各为50%。空member2/member3跳过并列出，不占权重。

例：A有1例、贡献5分，其数据集分为5；B有3例、每例5分，其数据集分为15。最终主分为`(5+15)/2=10`。两集单例均分和全部4例均分均为5，作为辅助字段单列，不用于替代主分排名。

原评分器`normalization.average_score`仍按每集每重复封顶50、重复取均值、再按成员等权平均，作为raw字段并列保留。报告当前主汇总用上面的未封顶dataset sum；不将其混写成原raw分，也不换成每成员mean_case。单例均分、全576例等权均分、成本倍率/D/家族尾部均另列用于解释结果；主排名采用同一固定完整集合的score_final。原始成本、严重退化和失败仍完整保留，逐例零截断不能掩盖尾部。

已有数据却运行失败、缺案例、缺重复或缺有效Naive时，不丢掉该成员后计算有效全库分。局部批次只报告覆盖与未完成，不进入完整集合排名。显式partial子集可保留其范围内汇总，但必须标partial，不能作为全576例成绩。所有成绩绑定成员VERSION、SHA、suite、重复与基线身份，不能比较不同数据分布的未封顶总和来推断官方成绩。

## 只读重算

```sh
python -B evaluation/scripts/summarize_member_scores.py results/original-report.json --out results/member-uncapped-summary.json
```

输入为完整新版原评测器JSON，含可用`normalization.cases`。输出须是新文件；工具不修改输入、不编译、不启动候选或基线。原封顶raw平均分保存在`raw_capped_average_score`，主分为`score_final`；每成员`score_dataset_uncapped`与权重同时列出。失败原报告输出unavailable/score_final=null。完整案例/重复格不齐时直接拒绝有效汇总。

矩阵执行器可直接导入`summarize_contributions(datasets, rows, repeats=..., partial=False, skipped_members=...)`；rows使用原贡献字段`member,case,repeat,single_score`，case为成员eval目录内相对路径。datasets保留成员版本、指纹、case_count及原files身份。该API只做数学归约，不能用它把未审程序自报指标认证为合法动作。

7项纯Python汇总测试覆盖不等案例数、未封顶超过50、重复平均、空成员无权重、缺失/重复格拒绝、失败报告与raw封顶值保留；不执行solver。
