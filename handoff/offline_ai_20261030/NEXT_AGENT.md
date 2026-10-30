# 接手后要做什么、必须知道什么

先完成归档/模型/数据身份核验，再按用户最新指令推进实验。此次发布没有自动恢复暂停实验，也没有晋升新的神经网络。

## 优先事项

1. 阅读 LATEST_STATUS：Root 的 R79 数学候选及 final_dataset 抽样主线与旧 AI 数据独立。先吸收其已完成结论和真实基线，避免沿用已被新证据否定的收益假设。
2. 运行归档核验、按 DATA_CATALOG 恢复必要数据、运行 portable 权重加载核验。确认 7 个 GPU state_dict 与对应 JSON 一致，tiny 特征版本正确；训练/评测输出必须另开目录。
3. 若继续 AI，先明确目标是替代哪个在线策略，并冻结完整 case 划分、选点、输入/源码 SHA、continuation 和候选池。R70 的旧 zero 与真正 R75 是不同基线；不能把一个的标签/状态偷偷接到另一个。
4. 优先利用真正 R75 状态和完整后缀教师，研究能否从因果特征识别明确的单次偏离机会。先与简单规则及同 pool zero 对照，再决定是否训练。共享热度的因果解释、65 维 probe 和 headroom 本身不证明网络可学或闭环有益。
5. 冻结 train/calibration/dev，保持整 case 分离和谱系记录。新增样本至少覆盖 100k 规模再作规模收益结论；现有 4 锚仅是小样本诊断。reserved dev、已看 holdout、dyna 和 final 的评测部分均不得用于梯度训练。
6. 训练预算/模型/损失/种子事先固定。记录每阶段真实耗时和完整失败，不只筛选成功 case。旧宽网和 46 增样三臂均已失败，除非有明确机制变化，不原样重跑。
7. 只有完整闭环在独立 dev 相对简单对照改善平均与尾部后，再做 CPU/C++14 单文件迁移。核对特征、动作、tie-break、私有状态提交、逐步轨迹，并实测含观察/提案/推理全部成本的 D。GPU kernel 时间不是部署 D。

## 容易踩的实现问题

- 旧 R66 物理模型的 P 为空契约不能直接承载 R75 的非空 prefetch/periodic 动作。使用 corner 的全动作状态/适配契约，不能伪造 miss 或丢弃 P。
- R75 的 proposal 与 pending intents 会修改私有状态。只提案一次；保留当前真实观察，清掉本回调未执行的 intents，按实际动作 record；下一次真实回调确认结果。不要重置真正 R75 私有历史。
- auxiliary R65 observer 与真正 R75 observer 不同；仅辅助 observer 可按已冻结契约在非空 P 后重置，并初始化真实 q。
- 动作顺序、LOAD-last、phase/partition ID、容量和 callback 命中均属于标签身份。强制分支必须检查 overrides==1，不得用 baseline 结果冒充未触发的分支。
- `private_post` 指的是 policy/commit 之后、engine 执行动作之前，不是 post-engine 状态。
- 精确物理 hash 不单独锁定带宽等全部 header；同时锁 input/header/config/canonical IDs。
- student teacher driver 使用显式文件导入；同名 `run_pilot` 曾被 sys.path 选错，勿改回普通同名 import。
- `portfolio_labels.py` / `test_portfolio.py` 是历史未完成脚手架，不是正式 teacher 入口；`next_model_draft.json` 是草案，不是模型。
- 元数据重定位产生新 SHA。不能沿用原文件 SHA，也不能为了运行静默跳过依赖/输入 gate。portable 派生入口与历史原实验分别标记。

## 每次新结果应交付的证据

固定输入/源码/模型/特征/候选池身份，逐 case 物理成本及实际 D，完整分支数与失败数，train/dev 边界，平均/P90/worst 与同一对照，动作/状态核验覆盖，清晰的是否晋升结论。模拟成本、同状态标签、完整闭环、正式计时分别报告。

现有独立 agent 可按代码/数据/统计三个不共享写目录的任务并行。用户明确不要使用 Astra；控制 agent 数量和费用，计时期间停止并发计算。Git 发布仍保持单写者，不强推、不 reset、不切换他人的共享工作树。
