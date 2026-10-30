# Round7：来源分离、概率估值与驻留成本

阅读顺序：本文件 → RESULTS_RESUME.md（完成后的本轮结论）→ HANDOFF.md → AI_TRACK_REVIEW.md。原始报告全部保留；FINAL_REVIEW.json是最终完整性核查。

## 方法与实验顺序

1. 80条既有train的字节账本表明PROBE读写占约99%，所以本轮不改BUILD，先处理周转。current Miss目标不再与next样本混为热度。
2. periodic64只用周期next；mixed64合并周期与Miss后next，按合法全局PROBE序号去重，并保存两个来源标记。总均匀先验强度64；普通Hit身份仍不可见。mixed64_core加入软驻留核心。
3. 严格固定池版保留Best的top4生成及fallback，仅以新概率比较同一实时状态的覆盖子集。不同策略仍会走到不同状态，不能称完整轨迹相同。
4. linear64取消min(1,64*p)截断，保留热点概率差别；64只是固定收益尺度，并非精确长期成本。core0/50/90按估计冷尾请求的大小分位数选周转预算，核心2倍软保护、1.1倍成员滞后，绝不硬锁。该核心机制目前没有稳定额外收益。
5. decay64在linear64上按合法H+M时钟老化概率计数：半衰期2048 PROBE，至少256步才统一折减；原始来源计数不衰减。两个版本是decay64.cpp及decay64_fixed_pool.cpp。没有扫描这些常数。
6. 训练诊断后只做一次dev100提名，3重复，门槛沿用Round6，结果见DEV_RESULTS.json。eval50未调用，Best和AI冻结入口不覆盖。

## 证据版本，避免误读

- 原RESULTS.json、PERIODIC64_RESULTS.json、MIXED64_RESULTS.json、MIXED64_CORE_RESULTS.json及PERIODIC64_FIXED_POOL_RESULTS.json的部分均值/胜例数错误：3条0/0被算作比值0。每流字节账本未受影响。统一修正以CORRECTED_RESULTS_V2.json为准，0/0按1；正数/0直接报错，不能用epsilon隐藏。
- FIXED_POOL_RESULTS_V2：三个严格固定池版各80条完整审核，续接仅补原来缺少的100次。
- OBSERVATION_PROFILE：80条Best轨迹，来源直方图与独立重放均核验。TV为分布差绝对值之和的一半，越小越接近；这里只比全流经验分布，不证明未知真概率无偏。
- MATRIX_PLAN/V2/V3：旧矩阵原件。lognormal-independent打乱size误消耗热度RNG，只影响4条，不能拿它做严格配对结论。
- MATRIX_PLAN_V4、MATRIX_RESULTS_V4：最终修正矩阵，三关系概率、实际PROBE频次、大小集合逐组相同；48例×9方案，396条双SHA复用、36条补审核。V4才是本轮矩阵结论依据。
- PILOT_RESULTS_V2/V3：80条旧train上的单因素及衰减回归；新矩阵不是独立测试集，80条也不是新样本。
- SAFETY_V2/V3：七个新候选各20000抽象状态，预热来源历史后检查动作，ASan+UBSan。SAMPLING_CHECKS单独检查来源去重、真实重复请求、当前Miss排除和衰减。

## 两条路线

纯算法当前发布基准仍是../MySpillSchedulerBest.cpp；含AI当前发布基准是../round4/ai_prefetch_budget2048.cpp。根目录MySpillSchedulerAI.cpp更旧。新候选是否通过dev门槛见DEV_RESULTS，不等于已晋升正式提交版本。

AI本轮保留独立路线，但未重训旧树。先验证合法特征能识别新配置的互补，并与最佳固定新配置、简单确定性门控及旧AI基准比较；不能将换了纯估计器后的收益算作学习收益。详细条件和子agent审查见AI_TRACK_REVIEW.md。

## 复现入口与限制

在源码工作树根目录，使用已有Round6冻结数据缓存；大输入和二进制都位于忽略的build目录。

```sh
python src/Vanius0525/level1/round7/make_candidates.py
python src/Vanius0525/level1/round7/fixed_pool.py
python src/Vanius0525/level1/round7/profile_observations.py
python src/Vanius0525/level1/round7/make_v2.py
python src/Vanius0525/level1/round7/make_decay.py
python src/Vanius0525/level1/round7/generate_matrix.py
python src/Vanius0525/level1/round7/generate_matrix_v4.py
python src/Vanius0525/level1/round7/run_v4.py matrix
python src/Vanius0525/level1/round7/validate_v2.py
python src/Vanius0525/level1/round7/validate_v3.py
python src/Vanius0525/level1/round7/check_sampling.py
```

这些命令不是要求新会话重复实验：先看HANDOFF及已有完整缓存。首次完整复现还需原run.py主80流、run_v2.py pilot、run_v3.py pilot；run_v4可复用V2/V3矩阵证据，缺失则执行相应病例。原输入仍需Round6固定缓存，源码仓库不携带数据。所有实验用experiment.lock串行；不创建小时服务。

本轮未做最大500万操作的新性能复测。矩阵只有两个seed，K/B/带宽跨seed共变，不能分离这些因果效应；没有混合BUILD/PROBE竞争。giant_cold标签pressure为替换大对象前的预算，实际压力及大小-热度相关性见MATRIX_CORRELATION_AUDIT。全局样本衰减、有限样本先验和核心门槛都是启发式，无最优性或正式满分保证。
