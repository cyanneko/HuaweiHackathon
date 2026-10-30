# R72 独立源码与数据检查

本目录独占审计，不修改生成器、旧 R71 数据或共享 Git。

## 已完成的生成器源码检查

检查的 `generator.cpp` SHA256 为 `c802d5bb9281948ba251e7f21eed6b5e6dffcd5c5911bd16d3d17d1cf8320b00`，对应编译程序 SHA256 为 `69d7226945d596304c9d5cb6575b76fe5316c5e7c78c815eea8f3dbea864ad67`。完整批次审计会再核对生成清单中的源与二进制在审计前后均未变化。

随后最终默认速度从 `.025` 调整为 `.0025`。最终冻结源为 `0611bdecc3640cffe06efbb9956fa2d3271d8d579c2318e1c1f938121709a175`，程序为 `774f700a909e6252443bcfe14cc8d2ebe59677b20db44684622298e840c30705`，配置为 `00b5a6f009f3c8c32c27df7feb611023b5a85db95b5c8e4f3afa35a173797962`。旧小诊断只证明相应参数下的合法性/隔离；最终速度与概率质量必须由最终完整文件及对应 metadata 统计，不将旧 `.025` 结果混入最终指标。

- 每个全局 t 都直接 `op_process.sample(op_choice)`；没有完成配额后剔除算子的分支，全部 K 始终参与。
- 阶段由 `t>=thresholds[op]` 且尚未 SWITCH 控制。INSERT/PROBE 计数没有进入采样或阶段决策；EOF 用真实计数 seek 回填头部。若算子未切换则报错，不强制补齐。
- 算子选择、算子漂移、阶段阈值、异常选择、分区选择、各算子分区漂移、初始分区概率、键编码及元组大小使用隔离 RNG。
- 只有选中算子的 INSERT/PROBE 更新该算子 q/u；SWITCH 不调用分区采样或更新。每个全局操作包括 SWITCH 都更新算子 p/v。
- 分区常态 target 为均匀分布，初始权重在 [0.95,1.05]。慢速度、回复力与按 target 的双边限幅保持缓变，不以经验访问计数修正概率。
- 每次归一前 q 分量在 [0.95 target,1.05 target]，target 总和为 1，因此归一后 q/target 在 [0.95/1.05,1.05/0.95]。初始常态归一概率也在此包络。窗口均值必然仍在包络，审计对此硬检查。
- rare_hot/cold 为个别算子的持续异常 target，不应称为短暂 spike；其他算子仍 normal。异常 PID 的次数、字节与实际概率另列。
- 分区超内存时原 case 报错，未重采样 PID、截断元组或替换种子。规划期望容量不是实际容量保证，必须逐行审核。

## 独立可运行检查

`audit.cpp` 逐行解析所有操作，独立计算 counts/phases/partition bytes、每个算子的首尾 INSERT/PROBE、SWITCH、全局窗口 op counts、各算子本地访问窗口 PID counts（I/P 分列、SWITCH 不计、尾窗保留）。

`run_audit.py` 与生成清单、metadata、operator windows、partition windows 逐项比对；概率均值只核归一化、正值、理论包络、跨窗口加权汇总一致性，不声称独立重生成了每步隐概率。实际窗口计数则由输入文件独立复算。非均匀 chi-square 仅描述，不当作正确性判据。

`independent_smoke.py` 另在本审计目录生成 normal、速度变化、rare_cold 三个诊断文件，各 80,008 操作。三份均通过新 C++ 审核、全部 metadata/CSV 交叉核验和旧 Python audit；操作类型+算子序列 SHA 与 INSERT 算子+大小序列 SHA 完全一致，而完整文件 SHA 三份不同，确认这些分区参数变化没有扰动算子和阶段序列。总 240,024 操作，脚本约 1.92 秒。不是大数据结果或独立官方分布证据。

新增测试包括缺尾窗、窗口错计数、阈值违反、错误概率归一、normal 大倾斜拒绝，及 explicit rare_hot 不因非均匀误拒。首批5个输入校验测试与8个 metadata/CSV 对照测试通过；还需在最终源/批次冻结后运行全部大文件审计。
