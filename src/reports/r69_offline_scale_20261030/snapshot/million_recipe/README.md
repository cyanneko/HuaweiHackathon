# R69 百万操作固定输入配方（仅准备）

**状态：prepared_not_generated。** 本目录只准备配置、调用脚本和计划清单；没有生成输入、运行 audit、solver、训练或编译。实际生成由 Root 在协调窗口内执行，Worker 只负责后续 solver。

两例均为已曝光的 **offline benchmark / dev**；新 seed 属于同一生成器族，不是 blind holdout，不声称未知官方分布或分布独立，也不用于 NN 训练。未进行全历史 seed/流指纹查重。

| case | scenario | seed | pressure 请求值 | builds/operator | probes/operator | N |
|---|---|---:|---:|---:|---:|---:|
| scale_uniform_n1002052_p3p0 | uniform | 910300301 | 3.0 | 512 | 250000 | 1002052 |
| scale_skewed_n1002052_p3p0 | skewed | 910300302 | 3.0 | 512 | 250000 | 1002052 |

共同参数：K=4，P=16（共 64 分区），M=67108864 bytes，B=1000，W=1000，R=100，penalty=100。每例 `N=4×(512+250000+1)=1002052`，两例合计 2004104 操作；`+1` 是每 operator 的 SWITCH。pressure 实际值在生成后从输入审计，不能用请求值代替。

`run.py` 是 `tmp/r66_random_scale_20261030/run.py` 的逐字节副本，SHA-256 为 `0170def71ddcda1d703a22583243a0ab5766cf905d91daa5d55ba6c6cd336129`。没有新增生成算法或修改原脚本、原 config。原 generator 和 validator 的当前 SHA-256 已核对并写入 config，运行时仍会检查；源变化立即拒绝，不自动更新 hash。

## 单案例调用

从工作区 `${WORKSPACE}` 执行。以下命令只生成并审计 uniform 一例，供 Root 在已协调窗口内使用：

```powershell
python tmp/r69_scale_inputs/run.py --case scale_uniform_n1002052_p3p0 --execute
```

生成 skewed 时将 case 改为 `scale_skewed_n1002052_p3p0`。省略 `--execute` 只预览配置和核对源 hash，不导入生成器；`--split dev --execute` 会显式选择两例，因此单案例执行优先使用 `--case`。没有默认执行或 `--all`。

**无 overwrite：** 任一目标 input、原 `.meta.json` 或 `.verified.json` 已存在时立即拒绝。若一次生成失败留下文件，先保留检查，不自动覆盖或删除。不得用改 seed/recipe 的方式悄悄重试。

## 输出和边界

- 生成位置：`data/dev/<case_id>.txt`，保留原 generator 的 `.meta.json`，另写 `.verified.json`。本次准备未创建 data 目录。
- 复用现有 `audit_datasets.audit_case(..., enforce_limits=True)`，核对官方范围、阶段、计数、每 operator 一次 SWITCH、tuple/key 边界和累计 partition bytes≤M，并检查 N 等于冻结 recipe。
- `.verified.json` 记录请求/实际 pressure、N、K×P partition bytes、实际 probe counts/skew、原 input SHA-256、原 operation stream SHA-256、按 `key%P` 规范化操作流 SHA-256，以及配置/包装脚本/源文件 hash。
- `manifests/dev.planned.json` 只含冻结参数、预计规模和 config hash。`dev.generated.json` 只有实际生成且校验通过后才创建；没有预造 input hash 或合法性结果。
- 原生成器在内存中构造操作字符串，百万输入的生成时间和内存尚未实测。uniform 的 BUILD/PROBE 均随机均匀；skewed 的 BUILD 倾向 pid0，PROBE 使用现有固定 hotset 分布。三个阶段依次为所有 BUILD、SWITCH、交错 PROBE，不包含新增热点漂移或生成族。
- 输入 audit 不能替代调度 witness 的官方合法性验证，也不产生策略效果或速度结论。

本次只检查静态配置、预计 N、脚本副本和源 hash；没有执行包装脚本、generate 或 audit。
