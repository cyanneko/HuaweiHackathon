# AI 研究候选交接包

支持入口是根目录的 `portable_ai.py`。它按自身位置加载 `workspace/` 下原路径镜像中的 `model.py`、权重和已保存因果特征，不导入离线求解器，不读取未来输入，也不默认训练。依赖 Python、PyTorch；无需安装新的推理运行时。历史 GPU 环境为 torch 2.14.1+cu126，本次核对使用既有环境的纯 CPU。

## 已有结果与限制

包内有七个 GPU 模型的 JSON、PT、训练报告，以及 R70 tiny model_v2 的真实 JSON 权重、C++ 导出和验证材料。七个 GPU 候选在已查看 dev8 的 Python 闭环中都比同候选池零残差规则的平均成本差；四模型成本均值比约 1.14190、1.09944、1.08092、1.08750，A/B/C 约 1.08092、1.09775、1.10432。没有为这些失败候选完成新的 C++ 模型迁移。

Tiny model_v2 已完成 C++14/O2 的 128 向量精确分数检查、dev8 完整动作/特征/历史及 IO/hit/miss 对齐和正式测试。它仍是负结果：正式 dev 相对同 pool Heuristic 为 1 胜 7 负，已看过的旧 holdout 为 2 胜 6 负。旧 dev/holdout 都不能再作为盲测。正式报告中的 D 来自历史测量；本包的纯 CPU 权重核对不构成新的 D 或质量结果。

角落 stage0 与 100k 的材料只有一次强制偏离后继续原 R75 的局部 Q_R75 headroom、接口和特征证据。没有训练过 corner65 神经网络，没有 NN 胜过 R75 的结果。R79 算法/数学支线不属于旧训练标签。

## 可运行入口

从本目录运行，输出默认写到标准输出：

```text
python -B portable_ai.py verify
python -B portable_ai.py infer --model tmp/r70_nn_pipeline/model_v2/model.json --features features.json
```

`features.json` 是 `[[x0, ..., x31], ...]`。`infer` 加载真实权重执行纯 CPU 前向；tiny 还返回与已导出 C++ 累加顺序一致的 FP32 参考分数。`verify` 检查八个模型能加载和前向、七组 JSON/PT 参数逐 tensor 完全相同，以及 tiny 的 128 个保存向量误差为零。它不进行策略回放、求解或训练。

旧 28 个 labels_v3 已经存在于固定 Git 源版本，不再次打包。`AI_REQUIRED_INPUTS.json`逐个记录源 commit、源路径、恢复路径和原 SHA。父包的 `restore_assets.py` 应把这些 blob 恢复到 `workspace/tmp/r70_nn_pipeline/labels_v3`，并通过 SHA 检查。新归档的标签只有同一批 46 学生状态的 fixed/portfolio 两份标签和一份 corner16 标签；corner 标签仅供研究证据查阅，本入口从不将它混入训练。corner 的辅助 history、private-state 字段及所有 full witness/trace 路径已从公开副本移除，物理 snapshot 和保存的 x/target 保留，历史 snapshot SHA 仅用于指向原证据。

恢复旧标签后，以下是**显式启动的新研究实验示例**，本次交接没有执行：

```text
python -B portable_ai.py train --labels old --architecture small --epochs 32 --lr 0.01 --out NEW_EXPERIMENT
python -B portable_ai.py train --labels student-fixed --architecture large --zero-columns 13 28 30 31 --epochs 200 --out NEW_EXPERIMENT
python -B portable_ai.py train --labels student-portfolio --architecture large --zero-columns 13 28 30 31 --epochs 200 --out NEW_EXPERIMENT
```

旧训练标签严格取 `AI_REQUIRED_INPUTS.json` 中显式列出的 24 个 train 文件，逐文件核对原 blob SHA，并约束每行 case_id/split；不使用目录 glob。新增 paired 标签严格按 `saved_label_manifest.json` 显式路径和 public SHA 校验。`verify` 固定要求 8 个指定模型和 7 个 PT，同时检查 3 个新标签的 public SHA；旧 28 个文件恢复后也逐个校验原 SHA，再报告 370/416/416 的 train 行数。corner 只作证据，不能进入此训练入口。

训练只消费已存 train 特征、完整候选成本和 target，按 informative case 等权，复用原 `model.py` 的 Huber 与 gap 加权 pair loss。它输出新模型而不覆盖旧权重。它是可运行的后续实验入口，不保证逐步重现历史初始化、GPU 数值或训练时间，不提供泛化或闭环质量结论。不要没有新假设就重复已完成的失败 sweep。

## 代码、数据与哈希如何合并

将本组件 `workspace/` 的内容合并到父包同名镜像目录。`provenance/legacy_dependencies.json` 列出历史 pipeline/teacher 需要父离线组件提供的文件和历史原始 SHA。支持的 `portable_ai.py` 入口不依赖这些离线文件。

原始输入在 `DATA_CATALOG.json` 列固定提交、路径和 SHA，由 `restore_assets.py` 从已有 canonical datasets 恢复。入口依赖根目录固定文件名 `AI_REQUIRED_INPUTS.json` 和 `saved_label_manifest.json`；合并时将这两个文件与 `portable_ai.py` 放在同一根目录。saved-feature verify/infer/train 均不需要原始输入。未收录 full witness、trace 文件、原始输入副本、native 二进制、R75 private 历史或大诊断运行目录。

保留的 `train.py`、`three_arm.py`、`pipeline.py`、`closed_loop.py`、导出脚本等是历史核心研究源码。机器路径已脱敏，嵌入的历史 gate SHA 保留其原来含义。**这些 legacy 脚本不承诺可直接运行完整闭环**：仍需恢复对应原始输入、补齐离线依赖、为机器路径字段建立明确重定位、恢复/重建未公开的 teacher/witness 元数据，并区分 published hash 与 original hash。只有完成这些工作并重新验证 gate 后才可运行；不能静默跳过 gate。

父组件合并时，不需要为了支持 portable_ai 更新 historical `dependencies.json` 或训练报告中的原 SHA。`provenance/ai_component_manifest.json` 对每个复制文件记录 original SHA、public SHA 和变换；公开副本发生路径/隐私变换后，历史 SHA 不再是该文件当前字节的校验值。若未来选择恢复 legacy hash gate，应另建明确标记的 published dependency manifest，逐项校验公开文件，并保留原 manifest 的历史 SHA。不要把历史报告哈希直接改成发布哈希后声称仍是冻结实验。

`provenance/ai_weights_validation.json`（合并后恢复核验见 `provenance/integration_validation.json`） 记录本次纯 CPU 小核对；它只证明权重与保存特征入口可用。所有原件保持不动。

最终合并布局和实际发布字节以 `ARCHIVE_MANIFEST.json` 为准。
