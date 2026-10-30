# stat_dataset：从算子热度转向分区级过程

`stat_dataset 1.0.0`把问题推进到“每个分区自行变化时，调度器能否持续估计并保留有价值的驻留集合”。它直接为全部`K×P`分区构造潜在热度，再进行一次全局归一化和抽样；没有独立的算子热度层，也不先选算子再选分区。算子的访问比例由其分区概率相加产生。这是生成模型的结构变化，不是AI效果已获证明。[生产README](https://github.com/cyanneko/HuaweiHackathon/blob/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset/README.md)

它仍是独立补充集，没有加入指定的旧dyna1.0全12＋final2.1 eval72主比较，也不追溯替换旧结果。名称中的`stat`不表示所有输入都静态。当前eval10已曝光，原README“未评测”的表述只记录生成审核完成时点；后续发布说明明确更新了状态。[发布与曝光说明](https://github.com/cyanneko/HuaweiHackathon/blob/a8f9a109cd350e06509419dc46bd3bbc9b95fd4d/stat_dataset/PUBLICATION.md)

## 经清单复算的规模

| 生产划分 | 案例 | 100万操作 | 500万操作 | 总操作 |
|---|---:|---:|---:|---:|
| train | 24 | 4 | 20 | 104M |
| dev | 6 | 2 | 4 | 22M |
| eval | 10 | 2 | 8 | 42M |
| 合计 | 40 | 8 | 32 | 168M |

**展示时保留24/6/10。** 冻结recipe、manifest、生成协议和质量摘要均使用该划分；PUBLICATION.md另写“30 train/10 eval”。30恰好等于24+6，但两个指定提交之间只有PUBLICATION.md变化，没有证据表明原dev6已改为train。可以展示“30条非eval开发材料”，同时保留内部24 train/6 dev标签，不能据一句发布概述擅自改划分。[冻结配方](https://github.com/cyanneko/HuaweiHackathon/blob/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset/recipe.json) · [输入清单](https://github.com/cyanneko/HuaweiHackathon/blob/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset/manifest.json)

40个不同seed，原始文本共3,299,015,915B，gzip共1,256,639,148B；单例原始文本19,309,226–102,406,987B。每例K=1–8、P=32–64、M=64MiB–4GiB，构建总字节压力为1.25–6倍M。168M是操作数，不能当作168M个独立测试样本。本次只读取232,870B小元数据，未取得或解压gzip/raw。

## 相对已有数据集的变化

| 数据集 | 主要设计 | stat的新增部分与保留边界 |
|---|---|---|
| final2.1 | 普通静态随机与倾斜、较大模拟字节压力；推荐540 train＋72 eval，最大约1M操作。 | stat增加大量5M长流和动态过程；仍是模拟数据，不能据此推断真实数据库流量分布。 |
| final3.0 | 保留2.1父规格/BUILD，重生成固定PROBE分布；每算子内明确验收倾斜，612条仍无实际阶段交叠。 | stat不要求全部案例持续满足固定偏斜阈值，允许动态变化及真实阶段交叠；同时重新包含均匀/近均匀对照，所以不能自动继承为本任务排除均匀主测后的新主标准。 |
| dyna1.0 | 12条5M输入；显式动态算子热度、算子局部分区时钟与shared/staggered阶段。 | stat取消算子热度层，以全局操作时钟更新分区潜在状态；未访问分区也持续演化。借用漂移/突变思想，不是与dyna逐步等价或强度校准后的同分布替代。 |

旧数据集事实依据已有[数据演进审核提要](../../../level1/round9/dataset_monitor/DATASET_EVOLUTION_BRIEF_V1.md)。本轮新增核验只覆盖stat固定元数据，不重新读取旧输入。

## 概率、时钟与大小如何构造

每个扁平分区`i=op×P+partition`有独立随机流、基础权重、对数偏移与变化速度，构成`w_i=b_i×exp(z_i)`，最后用`p_i=w_i/Σw`抽样。独立的是潜在状态驱动；归一化概率总和为1，因此概率和访问计数并不统计独立，初始Zipf/热点排名的随机打散也不等于独立同分布抽样。[生成策略定义](https://github.com/cyanneko/HuaweiHackathon/blob/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset/README.md)

全部过程按全局操作时钟每64步更新一次，BUILD和SWITCH也推进时钟，块内概率固定。动态过程含带惯性的速度、随机扰动、稀有放大扰动、边界反射及弱回归。64步合并和每块至多一个突变是明确的近似，不能称为逐操作动态过程的精确等价。发布质量摘要记录7条静态概率不变、33条动态概率变化；这是潜在概率轨迹的统计，不是实际观测频率或算法收益。[质量摘要](https://github.com/cyanneko/HuaweiHackathon/blob/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset/quality_summary.json)

BUILD抽样、PROBE潜在过程、分区大小预算分别使用不同随机流，避免直接把“大分区”等同于“热门分区”。但实际INSERT次数、整数分配和容量截断仍会产生耦合；不能写成实现后的大小与热度完全独立，也没有证据证明已系统覆盖正相关、独立、负相关三种关系。分区上限为0.75M，每条INSERT为1B–1MiB；它没有覆盖单个对象逼近整个M的极限。

shared案例把SWITCH集中在共同阶段边界；staggered允许算子阶段交错。清单与摘要一致记录：24条shared的实际混合阶段操作数为0，16条staggered均有交叠，交叠操作数3,957–1,178,620。混合阶段在同一扁平空间里按各分区当前所属阶段使用BUILD或PROBE权重；阶段转换会改变算子出现比例，但并非另加算子热度模型。

## 组成、曝光与结论限制

- 全集含uniform、Zipf、hotspot、lognormal各7条，以及mixed12条；时间模式static/slow/fast/burst各7条、mixed12条。eval五种家族及五种时间模式各2条，但这不是完整因子实验，更不能用每族2例支持强统计结论。
- uniform家族含2条静态等概率全PROBE过程和5条近均匀动态过程；eval各有1条static和fast。静态uniform也可有BUILD/PROBE阶段交叠，不能把整个输入笼统叫作纯均匀IID。
- mixed12条在分区层混合四种基础分布与四种变化模式。摘要记录每个算子内都包含四类成分和四类时间模式；不是指定单个异常算子，也不是采集的真实生产流量。
- 40条清单的raw、规范操作流、分区语义流指纹各全异，split之间没有精确重复。没有重扫全部历史数据，不能扩大为历史全集语义隔离。
- 发布者声明40条完整逐操作合法性审核及gzip往返SHA核验通过。本轮只检查文档身份、40条配方/清单一致性、计数及摘要，不重跑审核、不读取生成器C++实现或真实输入，不能称为第二次独立全输入审计。
- 发布说明记录eval10已用于R81/Naive各3轮、共60有效运行；本轮未读取其数值成绩。数据曝光不将eval转为train。潜在概率快照和分布标签仅为离线审计材料，不能作为题面之外的线上调度输入。

## 可直接放入网站的短文

> stat_dataset新增40条长工作负载，共1.68亿操作，其中32条达到500万操作。它直接建模所有分区的热度变化，取消独立算子热度层；大小预算、BUILD抽样与PROBE过程使用不同随机流，并加入分区级混合速度及16条实际BUILD/PROBE交叠案例。冻结生产划分为24 train、6 dev、10 eval。该集合属于独立补充，含均匀/近均匀对照，eval已曝光；它扩展了机制覆盖，不能单凭数据设计断言AI更优或代表官方隐藏分布。

元数据审核结果及完整SHA见[STAT_DATASET_REVIEW_V1.json](STAT_DATASET_REVIEW_V1.json)；只读复核脚本见[audit_stat_metadata.py](audit_stat_metadata.py)。当前没有恢复周期监测或任何生成、训练、评测任务。
