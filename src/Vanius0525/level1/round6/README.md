# final_dataset 2.0.0：固定测试与隔离迭代

**当前已完成首轮及仅dev的margin校准，没有新候选晋升。** 完整结果与负证据见[RESULTS.md](RESULTS.md)，最终检查见[COMPLETED_REVIEW.json](COMPLETED_REVIEW.json)。测试账本仍仅有一次初始基准；训练/评测已结束，小时只读续接服务继续运行。

用户最新要求以新综合数据取代三成员分别/等权标准。固定来源为 datasets 分支 `33ab5af221069fe8b8832fd77e85563e9997633a` 的 `final_dataset`，VERSION=2.0.0：train500、eval50。来源README明确为合成数据，不是生产流量或官方隐藏测试。本包50例不能等同于此前用户告知的正式8组。

## 当前标准

50条eval每条等权，主指标为每例按题面截断后的0–10分再求平均；另报未封顶总分、Level1封顶50分、物理成本倍率、CPU、退化/失败/超时。**不再按三位成员分别平均，也不把合并总成本比当主指标。** 50例的封顶总分可能很容易同为50，因此饱和值不能区分候选。

当前纯算法基准是 `MySpillSchedulerBest.cpp`；当前已验证AI参照为 `round4/ai_prefetch_budget2048.cpp`。选择来自切换数据标准之前的完整面板，不按新测试结果挑初始模型。源码SHA、数据commit、manifest指纹和划分见[DATASET_LOCK.json](DATASET_LOCK.json)。旧Best和原冻结AI均保留。

## 防泄漏约定

1. eval50始终只测试，不用于拟合、产生训练标签、调阈值、选择seed、挑选配置或按反例修规则。
2. 从发布的train500内预先划分train400/dev100。dev100全部来自新生成训练流，按预先固定家族配额和语义指纹排序，不从历史复用训练或eval抽样。
3. 区间教师试验只使用train400中按输入规模和固定哈希选出的80流，每流至多2状态；dev100用于选型。选择与标签计划在任何新测试求解器运行前写入[TRAINING_PLAN.json](TRAINING_PLAN.json)和[OPTIMIZATION_FREEZE.json](OPTIMIZATION_FREEZE.json)。后续所有变动必须另记来源，不能悄悄更改预注册计划。
4. 初始纯/AI冻结基准只测一轮（每例3次成对交错计时＋独立动作审核）。之后仅允许一波由dev选定的候选测试：每条路线dev均分至少改善0.02，且dev最坏物理成本倍率不超过其基准的1.05倍；否则保留基准且不新增test访问。
5. 每次测试先写`TEST_ACCESS_LEDGER.jsonl`，固定输入/源码身份。查看结果后公开test即已曝光，后续可作固定工程基准，但不能把反复针对它优化后的结果称为独立泛化。不能无限重复查询相同test再声称没有泄漏；若根据test异常提出新设计，必须在新的独立留出集验证，并记录该设计已受到test启发。
6. 本轮不自动覆盖Best；晋升还需完整合法性、属性/边界及规模验证。验证不完整时不能声称完成交付或推送。

## 数据准备与审核

发布全套输入约942MB，其中eval约176.5MB，复用旧train仅约11.5MB。通过固定生成器/recipe可以本地重建新数据，逐字节SHA与发布manifest匹配；为了避免重建测试的长等待，也定向获取了50个eval Git blob。未整体下载旧版或当前全套大输入，未将数据放入源码索引。

`prepare.py`检查eval原始字节、完整输入合法性、原始操作流及忽略成本头的`key%P`分区语义流，并与发布train500和现有模型实际拟合过的288条输入比较。发布manifest层检查不冒充全部train已经独立重建；完整train在初始基准结束后才重建并逐文件SHA核验。

大数据、日志、二进制及当前会话绑定均在忽略的`build/round6/`和`results/`；源码仓库仅保存清单、摘要和证据。数据准备失败保留已有文件，不换seed或覆盖不匹配输入。测量失败保留partial journal，停止恢复，不跳过失败案例制造有效总成绩。

## 后台流程

`campaign.py`：既有准备完成→冻结纯/AI新集基准→重建train→80流区间教师训练→dev100六候选面板→按dev规则提名→至多一波test→人工核查完整性。所有CPU实验使用同一experiment锁。`BASELINE_RESULTS.json`等只在完整阶段完成后产生。

首轮无提名，因此未做challenger测试。`calibrate_margin.py`另记post-baseline的train诊断：同树只改0/0.005两种路由，在dev100仍不胜ai_best，未访问eval；不把该实验追溯成原始预注册。已停止这棵树的扩容/进一步margin扫描。

`hourly.py`：每小时只读检查进度并向当前授权会话续接，不启动回归、不读取逐例test结果、不自动训练、不恢复旧round4/5矩阵。实际状态见忽略目录`build/round6/hourly/status.json`，停止开关为其STOP。本地电脑/服务/额度不可用时不保证唤醒，不绕过额度。

断点与实际已完成事项见[HANDOFF.md](HANDOFF.md)。

## 复现入口

在本轮提交的源码状态、已有授权的Git远端和所需Python环境下，从level1目录运行：

```sh
python round6/prepare.py
python round6/campaign.py
python round6/diagnose_labels.py
python round6/calibrate_margin.py
python round6/validate_candidates.py
python round6/review_stage.py
```

`prepare.py`会补齐固定commit的小型manifest/recipe/生成器，输入仍在忽略目录；如需加速train准备，可在campaign运行后另开终端执行`python round6/cache_training.py`，它等待初始测试计时结束才取回缺失train，不下载旧版。完整当前输入约942MB，数据不能加入源码索引。训练需要既有numpy/scikit-learn，提交推理不需要它们。

已有完整且身份匹配的campaign报告会复用；partial不会被覆盖。margin实验是一次开发实验，其已有报告不可重复覆盖；已有完整结果时读取摘要即可，不要重复上述实验步骤。sanitizer脚本会核验并复用完整匹配证据。当前训练环境为numpy2.4.4/scikit-learn1.8.0；不同版本可能改变拟合细节，不能绕过源码/证据指纹检查。
