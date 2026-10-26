# 数据格式与团队提交规范

以下是本次初始化采用的文本输入约定，与随仓库提供的数据校验脚本相对应；最终比赛规则以主办方发布内容为准。

## 存放方式

- 分支：`datasets`。
- 路径：`datasets/<成员>/train/*.txt` 与 `datasets/<成员>/eval/*.txt`。
- 初始化成员目录为 `cyanneko`、`member2`、`member3`；后两者待成员加入后重命名。
- 每份工作负载使用 UTF-8 文本，建议 LF 换行；文件名可采用 `场景_seed编号.txt`。
- 可提供同名 `场景_seed编号.meta.json`，记录生成器、种子、场景、用途、来源和参数。
- 原始数据保持不变；训练和评测集合分离，避免重复操作流。
- 每个非空 `eval/` 必须包含 `VERSION`，内容为一行人工版本号（1–64 个英文字母、数字、点、下划线或短横线，首字符为字母或数字）。初始化为 `0.1.0`，不意味着空集合已经可评测；空目录或尚未上传的成员会被跳过，不阻塞其他人的已有版本。
- 至少一份合法非空评测集即可运行；报告只将参与集合的版本和内容纳入 suite_id，并另列跳过成员。完全没有可用数据时不产生有效成绩。已有数据却缺版本或数据非法时仍须报错。
- 修改评测案例时升级 VERSION；成绩另附内容 SHA-256，版本号相同但指纹不同的两次结果不可作为同版本成绩比较。
- 大数据文件上传前确认 GitHub 大小限制；需要时由团队统一采用 Git LFS 或外部存储，不把大文件直接加入普通 Git 历史。

## 输入结构

```text
K P M W R miss_penalty
N B
op_id build_count probe_count
...（共 K 行算子计数）
INSERT op_id key size
SWITCH op_id
PROBE op_id key
...（共 N 行操作）
```

| 字段 | 含义及当前校验范围 |
| --- | --- |
| K | 算子数，1–8 |
| P | 每个算子的分区数，2–64 |
| M | 共享内存上限，64 MiB–4 GiB，单位字节 |
| W、R | 写、读带宽，1–10000，单位字节/微秒 |
| miss_penalty | 每次 Probe Miss 额外代价，1–1000 微秒 |
| N | 操作总行数，1–5000000，包含 SWITCH |
| B | 周期回调间隔，1–10000；计数不含 SWITCH |
| op_id | 算子编号，0 至 K−1，每个算子的计数声明恰好一行 |
| key | 键，0–1000000000；分区为 key % P |
| size | INSERT 元组大小，1–1048576 字节 |

每个算子先 INSERT，再恰好一次 SWITCH，之后 PROBE；各算子的操作可交错，但按文件顺序逐条执行。实际 INSERT、PROBE 数须与声明一致，N 等于这些数量之和加 K。当前校验器要求每个分区累计大小不超过 M，确保可整分区加载。

**团队兼容性约定：K 行算子计数头按 op_id=0,1,…,K−1 升序排列。** 这是为了兼容参考框架 addOperator 使用 push_back 而操作执行按 op_id 索引的实现；不宣称官方题面文字明确要求升序。批量评测器对乱序头提前报错，不会默默重排数据。单独的旧 audit_datasets.py 只检查编号唯一性，不执行这一额外团队约定。

手算小样例可通过 `--allow-small-memory` 放宽 M 的下限；这些样例应明确标为诊断用途，不能当作满足正式范围的数据。

## 结果约定

默认新版协议输出 `Total_IO_Time`、`Total_Decision_Time`、`Hit_Count`、`Miss_Count`、`Total_Score` 五项。原始代价为：

```text
Total_Score = Total_IO_Time + miss_penalty * Miss_Count + Total_Decision_Time
```

Total_Decision_Time 为执行框架测量的三个调度回调累计耗时，单位微秒；不能用整个进程的 wall_seconds 替代。默认缺失此项即失败。显式 `--protocol legacy` 才使用旧四项且不含决策时间的公式。

此处代价越低越好，不等于主办方归一化后的比赛总分。动作核算脚本的版本限制见 [README.md](README.md)。

数据校验通过只说明满足脚本检查项，不保证数据代表性、训练评测无泄漏或新版官方引擎行为一致。
