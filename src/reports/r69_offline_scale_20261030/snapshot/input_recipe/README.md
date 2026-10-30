# R66 普通随机/倾斜规模补集（准备态）

只准备了固定配置、生成包装脚本和分离的计划清单；**尚未生成任何输入数据**，未运行 solver、训练、编译或部署评测。实际生成等待 Master 协调非正式窗口。本目录不修改已有生成器、R66 core、tiny_train 或 GitHub 项目。

## 冻结规模

全部 K=4、P=16、M=64MiB=67,108,864 bytes、B=1000、W=1000、R=100、penalty=100。builds/probes 均为每 operator 数量，N=K×(builds+probes+1)。

| split / 场景 | pressure | builds/op | probes/op | N/输入 | seed |
|---|---:|---:|---:|---:|---:|
| train uniform | 1.2 / 3.0 | 256 | 1,500 | 7,028 | 910300101 / 102 |
| train hotset | 1.2 / 3.0 | 256 | 1,500 | 7,028 | 910300103 / 104 |
| train skewed | 1.2 / 3.0 | 256 | 1,500 | 7,028 | 910300105 / 106 |
| dev uniform | 1.5 | 512 | 65,000 | 262,052 | 910300201 |
| dev hotset | 3.0 | 512 | 65,000 | 262,052 | 910300202 |
| holdout uniform | 3.0 | 512 | 250,000 | 1,002,052 | 910300203 |
| holdout hotset | 1.5 | 512 | 250,000 | 1,002,052 | 910300204 |

6 train 共42,168操作，2 dev 共524,104操作，2 holdout 共2,004,104操作，合计2,570,376操作。dev/holdout 的 pressure 配对在生成前固定；不是完整 factorial matrix，也不能单独识别 pressure/length/scenario 因果作用。

这是新 seed、同一生成族的补充数据，不是未知官方数据，不声称分布独立。train 可供后续已授权的离线教师；**所有 dev/holdout 长N输入只用于部署评测，不跑 Python beam，不参与拟合**。

## 现有生成器边界

调用原样 `hashjoin_lab/tools/generate.py::generate`，本包装器没有新增生成算法。

- uniform：BUILD partition 和 PROBE partition 都按随机均匀选择；不是只让 PROBE 均匀。tuple bytes 围绕 `M×requested_pressure/(K×builds)` 乘0.55–1.45均匀系数取整。
- hotset：BUILD 仍随机均匀；90% PROBE 从前 P/8=2 个 partition 中均匀抽样，10%从全部16个抽样。理论热区总占比为91.25%，实际以统计为准。
- skewed：每个 BUILD 有75%分支选pid0，其余25%均匀；PROBE 与 hotset 相同。pid0的理论选择率为76.5625%，容量回退/tuple裁剪可能改变实际字节倾斜。
- 每 partition 最大累积字节由生成器 cap=⌊0.8M⌋限制；tuple≤1MiB。requested pressure 是目标，actual pressure 必须从写出的输入复核，不能视为完全相等。
- 这三个场景均先完成所有BUILD，再执行各operator SWITCH，之后交错PROBE；没有 mixed 的BUILD/PROBE重叠、热点漂移或 scan 模式。全局交错和大key由固定seed随机产生。
- 生成器先在内存构造各operator完整字符串stream；百万操作并非流式生成，不保证生成耗时/峰值内存。验证器是O(KP)内存的流式检查。包装器不加载 checker.py 的完整 operations 列表。
- 预期N均≤5,000,000，M采用官方最小64MiB；没有用微小M制造非法压力。最大平均tuple为196,608 bytes，低于1MiB；实际input仍必须通过validator。

## 选择与执行

先预览单例或一个split（不生成，不导入生成器）：

```powershell
python tmp/r66_random_scale_20261030/run.py --case train_uniform_p1p2
python tmp/r66_random_scale_20261030/run.py --split holdout
```

**等 Master 协调生成窗口后**，在同一命令末尾添加 `--execute`。例如仅生成一个训练例：

```powershell
python tmp/r66_random_scale_20261030/run.py --case train_uniform_p1p2 --execute
```

也支持 `--split train|dev|holdout --execute`，一次只选一个split；没有默认执行、`all`、无选择运行或自动训练功能。不覆盖已有input/metadata；如果split部分生成，后续逐个 `--case` 调用。失败留下的原input只供人工检查，未通过校验不会进入generated清单。

## 输出与审计契约

- `config.json` 冻结10个case及参数、原generator/validator的SHA256。源文件变更立即拒绝；不自动刷新hash。
- `manifests/train.planned.json`、`dev.planned.json`、`holdout.planned.json` 相互独立，只有预期规模和参数，不含捏造的input hash。
- 实际生成到 `data/<split>/<case_id>.txt`；原生成器的 `.meta.json` 保留不变，包装器另写 `.verified.json`。
- 复用 `audit_datasets.audit_case(..., enforce_limits=True)` 检查官方K/P/M/N/B/带宽/penalty范围、key/tuple范围、阶段、每op计数、恰一SWITCH、累计partition bytes≤M。它是输入合法性校验，不是scheduler轨迹合法性/性能验证。
- `.verified.json` 含请求/实际pressure、N、完整K×P partition bytes和probe counts、每op top1/top2/fixed-pid0,1 probe份额、HHI、归一化熵，并保留完整validator结果。
- 原input SHA256精确覆盖文件字节；原validator的operation_stream_sha256保留原key。另有 `modulo_operation_sha256`：逐行 `INSERT op key%P bytes` / `PROBE op key%P` / `SWITCH op`，ASCII+LF，保留物理全局顺序，排除headers。该规范化hash用于发现仅key别名不同的等价partition流；不把它当作全部语义的input hash。
- 每split的 `.generated.json` 只有实际生成且校验通过的case，包含input/hash/verified路径。config、包装脚本、源生成器和validator版本写入metadata。
- seed在这10项中唯一；未做整个历史工作区seed查重，因此“fresh”只指本固定新增seed，不额外声称已证明与所有历史lineage无交叉。实际生成后还应按input与modulo fingerprint对拟采用的训练/评测全集查重。

本轮只对源文件做只读盘点，并静态检查配置/脚本语法与预计规模；没有运行生成包装器或创建data目录。
