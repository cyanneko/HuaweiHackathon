# R81 runner 独立静态审查

审查时点：尚未 prepare / native；数据生成审计由另一 agent 进行。本次只读源码并运行5项纯 Python protocol tests，无 scheduler/native。

被审 `tmp/r81_eval/experiment.py` SHA256 `4665840540e6caed7d19318f920aa1dae4c7070ebd5f55b6e478262e99f1d62c`。

## 需在 DEV 前补齐

`prepare('dev')` 当前只验证 advance 指向训练 summary 的 SHA；方法身份从当前 producer 构造，没有核对 TRAIN selection 的同名 source/TU/ELF。训练后若出现同名重编译候选，现有代码会允许该未被训练筛选的身份进入 DEV。

建议：读取 `train/selection.json`，验证选中项属于预定 NEW，当前所有 DEV 方法 source/TU/binary SHA 与 TRAIN 相应方法相同；并验证当前 data_manifest SHA 等于 TRAIN selection.dependencies 中绑定值。这样 DEV 配方和模型身份都承接训练冻结点。可另校验 advance.selected 与冻结摘要重新 choose 的结果一致。

`prepare` 也建议恢复旧 core 的“selection.json 不存在”断言，防止无意重新 prepare 覆写选择。以上已发 Root，未修改 Root 文件。

## 已通过的静态检查

- 执行 phase 保持 train/dev；`dict(selection,mode='final')` 只调用原评分分支。同轮每case Naive 的含D Total_Score 作分母，clip 后再等权case均分，没有使用历史Naive成本。
- 主筛选使用 new_train average_score；严格优于parent、old26下降不超过.05、全TRAIN最坏成本比不超过1.25。至多一个，平局先较低全TRAIN D再名称。未沿用 R80 的硬D倍数门槛。
- old26/new_train 独立分组；无法定义Naive或parent分母时不晋级。每组case数与有定义分母数核对，不使用缩小分母。
- 冻结core拒绝重复/未知cell；缺失或invalid cell导致complete=false且不聚合、不advance。单格失败保留，后续格继续；截止造成缺额保留。每格保存result和原日志，控制器不默默retry。
- TRAIN每case方法次序固定轮换，逐case输入SHA校验；每格60秒、整体240秒，最后小于60秒的截止标记为controller中断。DEV整体120秒由selection声明。
- 新train/dev显式按split分开，检查其lineage及input SHA无交集；old26来自已冻结TRAIN selection。建议防御性再检查DEV与old26的lineage/input交集；当前新seed独立性由数据agent合同审计承担，本审查未重新扫描输入。
- 方法源/TU/ELF逐SHA、flags和instrumented检查；剥离提交类后的框架skeleton核对原config。输入/meta逐SHA；冻结依赖在run前复验。
- 实际复核冻结core SHA `ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0`，与 R80 lazy final selection 已绑定值一致；R81没有改旧core源码。

## 轻量测试结果及边界

`python -m unittest discover -s tmp/r81_eval -p test_protocol.py -v`：5/5 PASS，0.009秒。覆盖score与ratio排序不同、缺失/invalid、old分数guard、零Naive/缺分组、nearest-rank和D计入成本。

它们尚未覆盖DEV身份冻结门槛；不把五项PASS解释成整个prepare协议已完整通过。此次没有读取成绩、重新hash大输入、启动策略或修改框架。待Root补齐门槛后可对新SHA做差异复核；当前结论为“评分核心通过，DEV身份门需补齐”。

## 修订后复核：PASS_WITH_SCOPE

上文保留首次审查事实。Root已在prepare之前补齐门槛，新runner SHA `57972915af06f39ed310c290f4e7a693009b3f2c21742062a83805fbebceb6b4`，test_protocol SHA `b535ad404485b5744899cb7a26fd09a2441c8c323fda441906f3e6ea920d73fd`。

- `verify_dev_identity` 对实际DEV所用全部方法与训练selection作全字段相等检查，并核data manifest仍是TRAIN冻结SHA；selected限定在NEW。
- DEV prepare重算choose与advance逐字段相符，核campaign→selection SHA、全部valid cells；prepare入口拒绝覆盖既有selection。
- 新manifest含旧26引用时明确过滤，旧引用逐项与冻结TRAIN input/meta身份相符，18条新样本必须FULL_INPUT_AUDIT_PASS。
- 独立运行修订后6项纯Python tests全部通过，包含训练后替换binary和data的拒绝测试。没有native执行。
- 轻读manifest核26旧TRAIN+12新TRAIN+6DEV；新旧全部TRAIN与DEV的input SHA和lineage集合均无交集。未重扫输入内容；沿用数据agent全输入审计证据。

机器审查记录：`RUNNER_STATIC_REVIEW.json` SHA `c55a41da5ced5df4f82fe8a4220830f8e8db276c9ee46dd0990d4d993a6a069c`。当前未见阻断prepare/训练执行的具体问题；这是源代码与协议审查，不是尚未发生的实验结果验证。
