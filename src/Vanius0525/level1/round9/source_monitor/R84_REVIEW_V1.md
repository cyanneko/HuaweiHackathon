# R84 完整归档的独立静态复核

2026-10-30。已重新解析 **588 份 stdout，核对 1176 份 stdout/stderr 指纹**，结果、完整网格和评分重算全部通过。此次没有运行、编译或训练任何调度器，没有下载或重新扫描大输入。

固定发布提交 `caafb937039e74a27e7e6e18269f01825fce2411`；主要实验原件提交 `b7482004d5313c6654629324cb465ef36d6554b1`。入口：[上游发布说明](https://github.com/cyanneko/HuaweiHackathon/blob/caafb937039e74a27e7e6e18269f01825fce2411/docs/R84_RESULTS_20261030.md)、[完整报告](https://github.com/cyanneko/HuaweiHackathon/blob/b7482004d5313c6654629324cb465ef36d6554b1/src/reports/r84_20261030/report_zh.md)。

## 先核方法与数据身份

R84 的 `Van_latest` 是 **原 paired100**，不是联合修正版。实际 `Van_latest.cpp` 为 18804 字节，SHA256 `3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15`，逐字节等于 `source/Vanius0525` 提交 `d92ceb0262b556eb57aae61127d062174ffe6016` 的 `src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp`。联合修正版不在七方法集合中，不能把此轮结果描述为 R80 与 joint 的同场成绩。

数据固定为 `datasets@d144cdd1c3b78f9a73702b4facb382e6a3e31212`：

- dyna 1.0.0 全 12 例，保留原 6 train / 3 dev / 3 holdout 标签；该回归已经曝光。
- final 2.1.0 全部 eval 72 例，28 random_zipf、28 random_hotspot、16 random_lognormal；不含 final train、inde 或其他成员套件。
- 后来出现的 final 3.0 不在此轮，不能以远端最新版本重新标注历史成绩。

输入 SHA、metadata SHA、实际 Miss 罚值在 inventory、selection、input gate、每条运行记录之间一致。这里复核的是保存的身份与读取头部记录，不把它冒称为再次独立读取 84 个大输入。输入实际罚值各异，在线 100μs 代理不替代评测器真实罚值。

## 重算结果

每例使用同一数据窗口的 Naive，分数为 `clip(10 × (1 − C / Naive), 0, 10)`，`C = IO + 实际罚值 × Miss + D`。先分别取两套数据的逐例均分，再各占 50%；未将 84 例直接等权混合。

| 方法 | dyna12 | final72 | 两套各 50% |
| --- | ---: | ---: | ---: |
| 原 paired100（R84 Van） | 4.049650 | 3.483631 | 3.766640 |
| R80 hierarchy | 4.306760 | 3.709253 | 4.008007 |
| R80 paired | 4.380691 | 3.625575 | 4.003133 |

两种 R80 的等权均分分别比原 paired100 高 **0.241366**、**0.236492**。dyna 的 12 例总成本均更低；final 中 hierarchy 为 46 胜 / 26 负，paired 为 42 胜 / 30 负。final 的最坏总成本 / 原 paired100 分别是 **1.167522**、**1.080183**，所以均分优势不表示逐例占优。

R81 的等权均分为 4.084522，但仍有尾部退化；上游未据此替换默认 R75。此审核只核实保存结果，不自行晋升任何方法。

## 执行与计费框架边界

已核 dyna `12 × 7 = 84`、final `72 × 7 = 504`，共 588 格，无缺失、重复、失败或超时记录。每格单次，CPU 串行，案例顺序固定并轮换方法顺序，官方单格限制 60 秒。保存窗口时长分别为 620.262305、278.550807 秒，后窗口在前窗口结束后开始；内部预算分别 900、600 秒。

每格 stdout 解析值与 `result.json`、`rows.json` 一致，输入/源码/ELF 绑定与 selection 一致。校核了逐格 `Hit + Miss = PROBE 数`、实际罚值成本分解、同窗 Naive 分母、各方法均分及最近秩 P50/P90/最坏成本比。显示到两位小数的成本恒等式，最大浮点残差为 0.010254μs，在 0.011μs 容差内。

七份实际完整 TU 的源码 SHA 与归档绑定匹配。规范 CRLF 后，将各自精确提交类替换为 `<SCHEDULER>`，七份剩余全文一致，SHA256 为 `98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9`。因此本轮方法之间没有额外 engine 或 main 修改。Naive/R75 绑定还记录原框架 SHA `1ed541a0d314c9b866b4a00198df3db5a3201d648e2c5b737b61cc8ab0e0a1da`；其他方法未单独重复该字段，不将缺失值虚补为独立核验。

环境文件披露 i7-14700HX、WSL2、当前 g++ 11.4.0，固定编译参数为 `-std=c++14 -O2`。这是归档的环境披露，不能用当前编译器字符串代替历史 ELF 构建证明。本次没有 ELF 原件重构或重测 D，单次 D 差异不提供统计显著性结论。

v1 在 metadata 路径分隔符预检失败，保存记录的 selection / campaign / solver 数均为 0；正式成绩来自 v2。JSON 清理了本机路径和执行命令，原件 SHA 与公开 SHA 不同，已按 manifest 区分：公开字节实际重哈希，原件引用通过保存的 source SHA 关联。没有声称能重建已清理的原始 JSON 字节。

## 本地证据与后续使用

- [审计程序](R84_AUDIT_V1.py)：只读固定 Git 对象，不会联网、编译或运行调度器。
- [结构化证据](R84_SOURCE_EVIDENCE_V1.json)：方法、版本、网格、窗口、源码/TU/ELF 记录与汇总。
- [588 条独立重算结果](R84_RECOMPUTED_PER_CASE_V1.csv)：含实际罚值、IO、Miss、D、物理成本、同窗 Naive 和逐例分数。
- `R84_CACHE/` 是本地只读工作副本，不纳入发布冻结。`full_v2/{dyna,final}/` 保存 rows/selection/input_gate 等；`measured_sources/` 保存七种完整 TU 和提交类。

共核对上游报告 manifest 的 3067 个公开文件指纹和七个方法类。先前默认协商的显式 blob fetch 部分报 `bad revision`；改为 `fetch.negotiationAlgorithm=noop`、`blob:none`、stdin 明确列举小对象后成功。来源归档约 10.93MB，不含输入、ELF 或新增运行。

跨归档联合版比较由主任务另行核输入身份、实际罚值及计费框架，仅比较物理成本，不能把跨窗口 D 混成新的 R84 同场分数；本报告不重复该比较，也不将其结果写回此轮冻结成绩。
