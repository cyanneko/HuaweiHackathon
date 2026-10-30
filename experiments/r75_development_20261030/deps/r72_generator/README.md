# R72：分层概率与变化率驱动的主数据集

身份：`r72-hierarchical-probability-velocity-v3`。本数据族落实最新建模要求：算子之间活跃度变化较大，同一算子的分区大部分时间近均匀、缓慢小幅波动，少数场景允许一个分区持久热/冷。全部是合成数据，不宣称拟合官方隐藏分布。

## 所有出现次数都由采样产生

每一步先按K维算子概率p抽算子。所有K个算子始终参与，没有Build/Probe出现次数配额、退出/收尾掩码或按进度补操作。选中算子后，如应切换阶段则输出SWITCH；否则从其独立P维概率q抽分区，输出INSERT或PROBE。每个算子、每个分区的实际次数均由随机采样形成；头部Build和Probe计数先留12字符占位，EOF后seekp回填实际值，不作为生成器输入。

每个算子的阶段由独立phase随机流预设时间阈值τ控制：shared模式τ=floor(build-fraction×N)；staggered模式τ=floor(N×clip(build-fraction×U[.7,1.3],.08,.65))。全局操作索引t从1开始，尚未切换且t<τ输出INSERT；尚未切换且t≥τ输出SWITCH；切换后输出PROBE。shared表示共同阈值，不是等待所有算子的屏障；实际SWITCH发生在该算子阈值后的第一次被抽中。EOF必须每个算子都已恰好SWITCH，否则失败，不补齐、不换seed。

shared规则下，τ之前每一步都是INSERT，所以**全局Build总量自然等于τ−1**；这是时间规则的推论，不是给各算子/分区指定次数。staggered连全局Build总量也随采样变化。全局总操作N预设为5,000,000且包含K个SWITCH。

## 两级概率过程与两个时钟

算子p/v在每一个全局操作之后更新（包含SWITCH）。分区q/u仅在本算子自己的INSERT或PROBE访问后更新全部P坐标；别的算子访问和SWITCH不推动这个本地时钟。不是每全局步更新全部K×P维，既清楚建模，也减少生成开销。

两级均保持概率与变化驱动力：先取小的对称均匀创新，按小概率放大；`v=clip(rho*v+innovation,±vmax)`，再减坐标均值；概率加速度后做边界处理和归一。v是归一前驱动力，不等于最终真实概率差；vmax在中心化前生效，中心化后最多2×vmax。

算子层初始p=1/K，沿用三档：

| 档位 | rho | sigma | 大创新概率/坐标/步 | 倍数 | 中心化前vmax |
|---|---:|---:|---:|---:|---:|
| slow | .9995 | 2e-6 | 1e-5 | 20 | .003 |
| fast | .97 | 2e-4 | 1e-5 | 20 | .01 |
| burst | .999 | 3e-7 | 2e-5 | 1000 | .006 |

算子层概率候选下限为.0001/K，触边速度向内反射为原绝对值的.25倍，再归一；最终仅保证严格正，不误称等于这个归一前下限。

## 分区层：普通近均匀、少量持久异常

全部分区过程都是缓慢档：rho=.9998，sigma=2e-6×(8/P)×.0025，vmax=.003×(8/P)×.0025，大创新概率1e-7/坐标/本地访问、倍数100。回复强度κ=1/50000。初始正权重为独立U[.95,1.05]，归一后得到初始q；normal目标target=1/P。

每次更新用 `q_raw=q+u+κ(target−q)`，每个坐标限制在target的[.95,1.05]内，触边速度向内反射，再整体归一。因此normal最终相对均匀的包络为[.95/1.05,1.05/.95]/P，即最坏约−9.52%至+10.53%，长序列也不会扩散成普通算子内的强偏斜。此约束限制**概率**，不限制实际计数，不采用轮转/补齐访问来强制平均。

仅预设三个异常case，每case用独立随机流选一个算子和一个分区：

- `train_slow_shared_01`：rare_hot，目标热份额U[.5,.8]。
- `dev_slow_staggered_07`：rare_cold，目标冷概率为.001/P。
- `holdout_burst_shared_12`：rare_hot，目标热份额U[.5,.8]。

异常算子的其他分区保持温和初始权重并按剩余质量归一；target为整个异常初始分布，后续使用同样的慢过程与target相对带约束。异常持续该算子整个案例，metadata给出op/pid/target向量与全局[1,N]、本地[1,visits]区间。它们是**少数持久异常场景**，本版没有声称已实现突然发生/消失的瞬态异常。普通与异常窗口必须分组报告，不能将异常混入平均后宣称都均匀。

## 数据规模与容量

固定12个独立base seed，每例5M操作，共60M；6 train /3 dev /3 holdout。K=2/4/8，P=32/64；M=64MiB/256MiB/1GiB；压力目标1.5/3/6/12。源码、配置与最终数据SHA绑定。R71 v1/v2沿用了相同base seed和split，故它们是配对版本，不可当作更多独立样本或跨split混用；旧目录冻结，仅供对照。

元组平均大小用 `M×pressure / mean(τ_i)` 规划，即以期望Build总次数规划字节尺度；实际size从均值×U[.5,1.5]四舍五入。只是在生成前选择字节参数，不指定出现次数，也不在运行后修正总字节/分区。真实压力允许波动，最终以metadata为准。

两个hot例都采用shared且pressure/K=.375，目标热质量最多.8，因此热分区规划期望占M最多约.3，考虑带约束后仍留数倍均值余量。`planned_expected_partition_capacity_fraction`记录更紧的目标概率上界计算，仅是规划期望，绝不是容量确定保证。任何实际单分区>M均整例失败，保留原输入/seed/日志，不重采pid、不裁剪、不缩放成品。完整输入必须再经独立审核才称为容量合法。

## 独立随机流

算子抽样、算子漂移、阶段阈值、异常选择、key和size各自独立；每个算子另有独立分区抽样、分区漂移和分区初始化流。使用SplitMix64及显式映射，避免标准库随机分布实现差异。改变分区速度参数不会改变算子编号/操作类型序列（已测试），分区趋势不意外影响算子活跃概率。浮点位级复现仍绑定源码、编译环境与最终SHA。

## 重现与产物

```sh
mkdir -p build
g++ -std=c++14 -O2 -Wall -Wextra generator.cpp -o build/generator
python3 test_generator.py
python3 run_batch.py --smoke
python3 run_batch.py
```

`run_batch.py`冻结source/config/binary SHA，逐例流式生成、gzip level6压缩（空filename、mtime0）、解压校验SHA；不覆盖已有manifest。实际原文件位于data/{train,dev,holdout}，可公开的真实压缩输入位于archives。目录metadata有每例JSON、每10k全局操作窗口和每算子每10k本地访问分区窗口；EOF不足窗口也保留。

所有索引为1-based步骤，op/pid为0-based；无Probe时last_probe_steps=0。分区窗口记录operator/local_end/global_end/window_visits/build_visits/probe_visits、每pid实际count和平均采样q；尾窗按op顺序补写，因此尾行global_end不保证跨op全局排序，但各op local_end递增。这些概率轨迹只用于数据审核，不能作为线上调度输入。

metadata包含actual_build_counts/actual_probe_counts、switch_thresholds/switch_steps、每分区bytes/counts、两层更新次数与概率边界。partition_processes.regime区分normal/rare_hot/rare_cold，提供initial_probabilities、target_probabilities、rare_pid、带宽/回复参数。`operator_process.steps=N`；每个partition process.steps等于该op实际INSERT+PROBE次数。

本生成器交付不训练、不求离线标签、不跑策略性能、不直接改公共Git。开发原型保存在logs用于解释失败测试，不能与最终冻结源码混用。主数据正式上传与评分由协调者另行处理。

分层速度修订记录：早期 `.025` 的12例小样本保存在 `smoke`，K=2 burst案例分区/算子每次更新L1比达到约.797，未满足“分区明显更慢”。在任何主数据或策略评分前，统一将速度系数降为 `.0025`，其余seed、算子过程、阶段阈值与异常目标不变。旧源码/配置/说明保存在logs，最终小例在 `smoke_final`。速度比须注明分区本地访问时钟与算子全局时钟，不宣称每例必定十倍；由最终实测报告给出范围。
