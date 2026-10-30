第20题：8专家小树与三成员评测（2026-10-30）

当前本地完整785例平均Score目标的最佳交付：../MySpillScheduler_tree.cpp。
节点阈值与叶子专家内嵌C++14；不依赖外部模型或推理库。
推荐入口：python design/tools/run.py --policy tree --input <正式输入文件>
原规则用--policy rule；原网络用--policy neural；官方Naive用--policy baseline。

测量记录：published_checkpoint.json；中文说明：../topic20_portfolio_iteration_report.pdf。
三人分别结果：../member_eval_20261030/members_standalone_r5_members.json
完整SDK逐次数据：members_standalone_r5_runs.jsonl；每例3次，算术均值。
当前名称：tree_exactcredit_exact142_r1_s1
源码SHA256：9b9238d7e9d7a1e65e4f37789c8c770673cc38beadc5db76c65ddae6e545b253
全785例平均Score：66823205678.740646 us；比Naive下降29.484633%。

三成员：Vanius0525 0.1.0/209；cyanneko 0.6.0/48；liunianwww 0.1.0/528。
数据固定提交：e119c2326e198922243306eac062785420ed8156
suite_id：a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1
成员未封顶sum等权主分、原cap50和raw平均Score分别保留，不混写；坏例不删。
840份train用于新标签与直接fitness；eval未作为新标签或fitness输入。
eval已被反复观察，用于开发比较，并非独立未见盲测。

方法与来源：iteration_notes.txt、../neural_selector/catalog.json、research_sources.json。
8专家编号0..7；评测mode不是分类标签。只有选中的专家实际执行。
overflow、miss每次分类；periodic仅下一INSERT将溢出时分类；普通hit无回调。
cheap路由按路径懒计算；getSystemState及专家仍可能O(Q)，以完整计时为准。
forced-cover只保证固定需求/保护条件的必要集合覆盖时立即写出量最小。

复现环境：Python 3.10+、g++支持C++14，拟合另需NumPy；CPU串行测量。
正式输入不在源码分支，请先获取datasets分支的两个独立固定worktree：
git worktree add --detach design/dataset_integration_20261029/worktree 0be508208700edae7a7b4443b122c633cc87b0e0
git worktree add --detach design/member_eval_20261030/worktree e119c2326e198922243306eac062785420ed8156
旧worktree用于公共评测模块及旧568例；新worktree用于840 train与785 eval。
先用git fetch origin datasets获取提交；不要把datasets分支合到source分支。

重拟合父模型（写新前缀，避免覆盖冻结模型）：
python design/portfolio_iter_20261029/train_tree_v2.py --input design/portfolio_iter_20261029/round3_labels.portable.jsonl.gz --features cheap --objectives relative --depths 4 --output-prefix replay
训练压缩包把file改为datasets/<member>/train/<name>；features/costs/权重字段保持一致。
portable_labels_audit.json记录原文件/压缩包哈希、行数和数值语义一致性。
collect_on_policy.py可重采样，CPU标签重测会波动；不要同时运行solver计时与拟合。

本地实验工具：build_candidates.py导出/编译；evaluate.py串行eval；audit_candidates.py独立动作与特征核对；
search_candidates.py生成train特征邻域变异；train_fitness.py串行完整train评分。
variants.json固定本地mode映射；训练输入编号/成员名/真实p均非在线特征。
当前程序源码快照：standalone_exact_credit_sources.zip；只绑定members_standalone_r5，不同历史程序不混用身份。
当前原字节测量包：standalone_exact_credit_measurements.zip。旧r3/4/5/6各自的source/measurements包独立保存。
重算本轮成员分前可解包：python -m zipfile -e design/portfolio_iter_20261029/standalone_exact_credit_measurements.zip design/portfolio_iter_20261029
使用源快照重新编译得到的新CPU时间是复测值，不冒充历史原值。

旧568例过程：progress.json；其best_model.json保留旧套件最佳，不覆盖为新套件。
本轮最终选择模型：current_model.json。所有设计、PDF与证据均在design下。
冻结模型JSON保留生成时candidate_has_measured_fitness=false和父模型640/568来源字段；后续840训练fitness及785实测以published_checkpoint和对应结果为准，不改写冻结原件。
Selected on observed 785-case development/regression raw mean; independent deployment verified. Retain 8-expert depth5 tree, admission2, next-deficit0; conservative exact_next_credit_shift=1. Local forced-cover prefix IO certificate does not guarantee full Score or unknown-distribution optimality.
