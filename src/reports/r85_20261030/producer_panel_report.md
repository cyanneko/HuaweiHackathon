# R85 新数据诊断：A 有局部增益，B 尚未获益

2026-10-30。**这是新 TRAIN12 与独立 seed DEV6 的完整七方法面板诊断，不是原 dyna/final 的全量结论。** 两阶段分别为84/84、42/42有效格；本报告独立重解析126份stdout，并核252份stdout/stderr SHA、完整病例/方法矩阵、固定顺序、完成门禁及全部分组统计。没有重跑策略、编译、训练或生成数据。

A仅把R81的快算子边际总prior由64改为8.009479828345365，慢条件prior64不动；B以R80 hierarchy为默认，在原门槛内比较旧启发式替代，比较公式不动。两项保持独立，不合并。

## 分阶段主结果

每例使用同批Naive作为分母：`clip(10×(1−C/Cnaive),0,10)`；`C=模拟IO时间+输入罚值×miss+实测累计调度时间D`。raw保留负分。下表各列分别按该阶段病例等权，不混合12例与6例，也不套用原dyna/final各50%的协议。所有Naive与参考成本分母均有效。

| 方法 | TRAIN12 clipped | TRAIN12 raw | DEV6 clipped/raw | TRAIN平均D(ms) | DEV平均D(ms) |
|---|---:|---:|---:|---:|---:|
| Naive | 0.000000 | 0.000000 | 0.000000 | 17.141 | 13.605 |
| R80 hierarchy | 4.568175 | 4.188675 | 4.825133 | 19.836 | 17.283 |
| R81 op256 | 4.474339 | 3.983312 | 4.779062 | 21.394 | 19.005 |
| R80 paired | 4.464401 | 4.013093 | 4.746826 | 38.363 | 32.476 |
| Van paired100 | 4.331874 | 3.702923 | 4.525768 | 31.672 | 26.194 |
| A：fast prior8 | 4.609814 | 4.136737 | 4.830160 | 20.767 | 18.099 |
| B：hier anchor | 4.541185 | 4.138531 | 4.790182 | 36.531 | 32.128 |

A对其父R81：TRAIN均分提高0.135475，DEV提高0.051098。物理成本比均值分别为0.973478、0.980694，说明差异并非仅由D造成。但DEV仅3胜3负：slow_staggered单例增加0.428720分，六例总增分约0.306586，故其余五例合计为负。这是集中而非普遍的改善。

A对R80 hierarchy：TRAIN clipped提高0.041639，但raw降低0.051938；DEV仅提高0.005027。A不能据本面板称为稳定全面优于hierarchy。

B对其父hierarchy：TRAIN/DEV均分分别下降0.026990/0.034951，总成本为3胜9负/1胜5负。物理成本比均值为1.005331/1.008220，平均D约为父版的1.842/1.859倍，不能把下降全归因于D。虽然本面板B好于旧paired均分，但“更换默认方案”仍不足以超过直接hierarchy。

## 成本分布与最差点

比值为逐例总成本/参考总成本，越小越好；P50/P90用最近秩，TRAIN12取第6/11项，DEV6取第3/6项。这里DEV的P90就是最差点。

| 阶段 | 候选/参考 | 胜:平:负 | 平均比 | P50 | P90 | 最差比 |
|---|---|---:|---:|---:|---:|---:|
| TRAIN | A：fast prior8/R81 op256 | 8:0:4 | 0.973482 | 0.993409 | 1.043788 | 1.048034 |
| TRAIN | B：hier anchor/R80 hierarchy | 3:0:9 | 1.005705 | 1.001963 | 1.023798 | 1.036796 |
| TRAIN | A：fast prior8/Van paired100 | 10:0:2 | 0.931058 | 0.949959 | 1.002871 | 1.016006 |
| TRAIN | B：hier anchor/Van paired100 | 10:0:2 | 0.943275 | 0.959330 | 1.002099 | 1.030496 |
| DEV | A：fast prior8/R81 op256 | 3:0:3 | 0.980658 | 0.997586 | 1.015786 | 1.015786 |
| DEV | B：hier anchor/R80 hierarchy | 1:0:5 | 1.008528 | 1.006847 | 1.023469 | 1.023469 |
| DEV | A：fast prior8/Van paired100 | 5:0:1 | 0.932896 | 0.984412 | 1.020716 | 1.020716 |
| DEV | B：hier anchor/Van paired100 | 4:0:2 | 0.949689 | 0.974725 | 1.028888 | 1.028888 |

A对R81的最差点：TRAIN `r85_train_12_random_lognormal`为1.048034，DEV `r85_dev_18_random_lognormal`为1.015786。B对hierarchy的最差点：TRAIN `r85_train_10_random_zipf`为1.036796，DEV `r85_dev_13_slow_staggered`为1.023469。A对Van分别10胜2负、5胜1负；B对Van分别10胜2负、4胜2负，仍不能称逐例支配。

**不能被零分藏掉的反例：** `r85_train_08_random_hotspot`中A、R81、hierarchy的clipped分数均为0；A的raw为−5.676918，R81约−5.019260，hierarchy约−4.553997。A总成本比R81高4.3788%、比hierarchy高7.7156%。B同例也为0分，但其raw比父低0.277851分，总成本高1.9091%。TRAIN中A有1个负收益点、R81有2个；负收益点减少不代表每个已有负点都改善。DEV七方法均没有负收益被截断，故该阶段raw等于clipped。

## 分轨与机制

| 阶段/轨道 | 例数 | hierarchy | R81 | Van | A | B |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN/dynamic | 6 | 5.384990 | 5.373706 | 5.076252 | 5.534745 | 5.360708 |
| TRAIN/iid | 6 | 3.751360 | 3.574971 | 3.587496 | 3.684882 | 3.721663 |
| DEV/dynamic | 3 | 4.682681 | 4.602842 | 4.206561 | 4.725406 | 4.630816 |
| DEV/iid | 3 | 4.967585 | 4.955282 | 4.844976 | 4.934914 | 4.949548 |

A的正信号偏向动态轨道：TRAIN动态相对R81增加约0.161039分，DEV动态增加约0.122564分。TRAIN IID也高于R81，但仍低于hierarchy；DEV IID低于R81与hierarchy。B两轨两阶段都低于hierarchy。

下面保留逐机制均分差；动态TRAIN每机制只有1例、IID每家族2例，DEV每机制1例。它们只是覆盖点，不是可靠的机制胜率。

| 阶段/机制 | 例数 | A−R81 | B−hierarchy | A−Van | B−Van |
|---|---:|---:|---:|---:|---:|
| TRAIN/burst_shared | 1 | +0.043659 | +0.001437 | +0.419987 | +0.438276 |
| TRAIN/burst_staggered | 1 | +0.231046 | -0.121909 | +0.194245 | +0.114323 |
| TRAIN/fast_shared | 1 | +0.228363 | -0.042752 | +1.031406 | +0.260176 |
| TRAIN/fast_staggered | 1 | +0.008491 | -0.008785 | +0.101903 | +0.016113 |
| TRAIN/random_hotspot | 2 | +0.006162 | -0.003526 | +0.001332 | -0.003768 |
| TRAIN/random_lognormal | 2 | -0.096273 | -0.038585 | +0.371362 | +0.423259 |
| TRAIN/random_zipf | 2 | +0.419845 | -0.046980 | -0.080535 | -0.016992 |
| TRAIN/slow_shared | 1 | +0.411690 | +0.028674 | +0.154275 | +0.125384 |
| TRAIN/slow_staggered | 1 | +0.042982 | -0.002362 | +0.849139 | +0.752460 |
| DEV/burst_staggered | 1 | -0.048117 | -0.069445 | +0.154338 | +0.250247 |
| DEV/fast_shared | 1 | -0.012911 | -0.014866 | +0.033936 | +0.003620 |
| DEV/random_hotspot | 1 | +0.003826 | -0.011070 | +0.001287 | -0.045705 |
| DEV/random_lognormal | 1 | -0.093894 | -0.093596 | +0.422212 | +0.457163 |
| DEV/random_zipf | 1 | +0.028963 | +0.050555 | -0.153686 | -0.097744 |
| DEV/slow_staggered | 1 | +0.428720 | -0.071284 | +1.368263 | +1.018898 |

本轮18个独立seed，没有带宽配对。动态TRAIN中shared全为压力1.25、staggered全为压力3，存在相位与压力混杂；各例K/P/内存/罚值等也变化，不能从这些分组差异推断相位因果。动态生成器自然采样counts，IID构造器预分配bytes/counts，两个轨道并非同一随机模型。DEV独立seed只代表同声明机制验证；执行后已曝光，不是官方未见集。

## 完整性、失败与身份

两阶段controller分别用时31.694089秒、15.663886秒，均在各180秒预算内；单格上限60秒，1repeat、CPU串行。最终gate均PASS，controller正常返回、error为空、terminal=valid=planned、身份无变化、CPU active0。raw summary始终complete=false，仅row_grid_complete=true；必须以finalized_summary和最后的completion_gate认定完成。独立检查也复核了这一分离，没有用全行齐全掩盖尾部异常。

本轮生成失败0、策略失败0、缺格0、重试0。下列预执行证据继续保留，不混称为策略失败：A旧prior数值oracle与B旧paired空证据anchor两个预期红测；旧raw-summary完成语义的协议红测；Windows默认临时目录权限导致的测试工具失败（改为工作区内保留目录）；真实IID参数无n的KeyError（修为build_count+probe_count+K，补实际manifest测试）。这些修复均在正式native前，九项协议测试及七个候选定向程序已通过。没有依据本面板结果改候选。

Van归属 `source/Vanius0525`，捕获提交 `d92ceb0262b556eb57aae61127d062174ffe6016`，入口 `src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp`；本轮保留Van原方案身份。A/B是本项目独立消融，不冒称Van原提交。

关键身份如下；完整七方法source/TU/ELF、Van证明、冻结runner/data和所有失败证据SHA均在独立review JSON中，不以移动分支代替版本。

| 产物 | SHA256 |
|---|---|
| `tmp/r85_ablations/producer.json` | `992a69c8c4c3a54e1136d9e342a4822fb67ce7e214fd5ec4c4cf31004e8cc9be` |
| `tmp/r85_eval/experiment.py` | `02de344cc16f065d9feb8709f952ed3d4bb0382b9055ef5b03672b82d0d62e42` |
| `tmp/r85_eval/scoring.py` | `f6fc385d3a74790ab0f7325ff8c89c7a650577c728c0c82914e64d5aad752057` |
| `tmp/r85_eval/protocol.md` | `020af40776f3fa0436a5e72af9addf3d033c9dc2a60967fe675a72a048a0b0a0` |
| `tmp/r85_eval/release.json` | `0eb48125e1fbfa564a6cb5e5f2cc50e9200af96f035dfd5910d6699c6abbd047` |
| `tmp/r85_data_panel/data_manifest.json` | `aee9a9717513d27b9f109d3fbe2926e2537903bd6a8e2c8fa9e768d9e0694a46` |
| `tmp/r85_data_panel/review.json` | `b6c04da59cad197c8c440d4b8a288d1e158a13f72fa39827d38cc295b029377f` |
| `tmp/r85_eval/train/finalized_summary.json` | `1739ce5e477bd9140e0b420bea134421b6ddcd674e8dc4886f07921e128dbbbf` |
| `tmp/r85_eval/dev/finalized_summary.json` | `4301db6cf825cf8d11ed2712a2e59bd3cc6d80eefe07dc66f62a315d0c10e01d` |

本次独立复核从stdout重算成本、分数和全部参考比，并核源/TU；ELF身份引用已绑定的Root source/TU/ELF重核记录，本次不额外读取Linux-home ELF，不重扫大输入。审查结果及每份日志SHA见 [panel_result_review.json](..<LOCAL_TEMP> [panel_per_case.csv](..<LOCAL_TEMP> [panel_groups.csv](..<LOCAL_TEMP>

## 后续解释边界

A的平均先验/质量匹配假设得到有限正信号，但证据不能证明它消除了回调采样偏差、修复了R84尾部，或普遍改善IID；B在新面板暂未证明相对hierarchy有益。两者仍按预先固定的八方法原数据全量协议继续比较，不据新面板成绩淘汰、调参或晋升。任何“原dyna/final更优”的判断必须等待该轮正式完整结果。一次D测量没有误差条，模拟IO+罚值也不是实盘端到端性能。
