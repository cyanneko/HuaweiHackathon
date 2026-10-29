第20题：合并后的568例完整开发评测（2026-10-29）

发布顺序与版本
  datasets分支0be508208700edae7a7b4443b122c633cc87b0e0已合入新增1128例。
  保留最新cyanneko 0.5.0的80个输入及原meta；新增liunianwww train600、eval528（0.1.0）。
  总train640、eval568；新输入中34例近均匀诊断有明确标签，不宣称代表官方倾斜/隐藏分布。
  测量前source/liunianwww代码149a91a7dda8ad5c03c360af1d3658bd3cc1d93b已推送。
  此后使用datasets分支当前公共runner自动发现全部非空成员；partial=false。
  未重训模型、改权重或据此重选策略；现有模型32→16→8、664参数、1线程CPU。

结果
  568例，每配置3次，候选与官方Naive配对，共6816次运行，全部complete。
  总Score先对每例重复求算术均值，再求和；降幅=100*(1-候选总Score/配对Naive总Score)。
  神经网络总Score54856425496401.625，Naive74107525304316.70：下降25.977254%。
  旧版总Score55159208219546.414，Naive74107525306112.78：下降25.568681%。
  神经网络相对旧版总Score低0.548925%。两批配对Naive的CPU有测量波动，不混用分母。
  NN逐例Score倍率mean/P50/P90/worst：0.789634/0.963651/1.040246/2.615132。
  NN逐例D倍率mean/P50/P90/worst：1.966149/1.573045/3.576098/14.373056。
  NN总D比为0.801740；总比与逐例等权均值含义不同，不应混称。
  本地开发/回归数据；旧调参样例和已测过的冻结测试不能称未来未见盲测。

文件
  merged_summary.json：总成本、成员、分布/队列及程序身份、数据指纹、指标定义。
  merged_cases.json：两方案全部568例的3次候选/基线原始指标与逐例汇总（无绝对路径）。
  merged_groups.json：成员、家族及分布分组，保留退化和零分母样例。
  datasets_import_audit.json：数据检查与原有172个成员文件的保持原字节证据。
  merged_action_audit.json：既有536例和补充32例独立动作/容量核查，与SDK IO/hit/miss相符。
  ../topic20_merged_dataset_report.pdf：中文报告。
  原始公共runner报告仍保留本地，其本机路径不发布；公开表保留所有逐次测量值。

复现
  从source工作树创建独立datasets快照（若已存在则复用并核对，不强行覆盖）：
    git fetch origin datasets
    git worktree add --detach design/dataset_integration_20261029/worktree origin/datasets
  在有Python3与g++的相同环境分别编译：
    python design/tools/run.py --policy neural
    python design/tools/run.py --policy recommended
    python design/tools/run.py --policy baseline
  使用数据工作树中的evaluation/evaluate.py，--datasets-root指向其datasets目录，不传--members。
  --repeats 3；--baseline-command-file保存baseline完整命令JSON；--baseline-kind official-naive。
  候选命令分别使用neural/recommended完整程序，输入参数为{input}；所有选项放在--command之前。
  本次实测使用同一个官方兼容引擎的mode -1/8/9分别选择上述类，类型、状态与计时不改。
  报告分别保存本目录merged_neural.json、merged_previous.json，再运行：
    python design/dataset_integration_20261029/summarize_merged.py
  汇总只读已测报告和冻结元数据，不重跑求解器。不同环境CPU数值会波动，比较须绑定同suite_id与身份。
