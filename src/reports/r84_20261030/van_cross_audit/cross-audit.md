# R84与Van测试结果交叉核对

2026年10月30日。核对范围是本机已完成的R84七方法全量比较，与Van分支在提交 `6ded7022215b80a8edf4170faefe1ca4da16814f` 保存的最新性能和诊断报告。

同一Van算法在相同输入上的物理结果一致，均分的小差异可由两侧决策计时D和输出舍入完整解释。Van最新训练对照与R84使用不同数据，因此两份报告的排名不能互相替代。原R84成绩和报告保持不变。

## 相同算法与相同输入

Van的 [CURRENT_WORKING_SOURCES](https://github.com/cyanneko/HuaweiHackathon/blob/6ded7022215b80a8edf4170faefe1ca4da16814f/src/Vanius0525/level1/round9/CURRENT_WORKING_SOURCES.json) 仍将 `round9/candidates/paired_penalty100.cpp` 列为当前纯算法入口。本次读取的实际源码与R84冻结源码逐字节相同，SHA256为 `3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15`。R84捕获的是旧提交d92ceb，但此类在6ded提交没有改变。

对齐原dyna12和final2.1.0的全部72 eval后，84份输入SHA及真实罚值全部相同。Van原paired与Naive的216条计时记录，其 `Total_IO_Time`、Hit与Miss均与本机对应记录逐值相同。216的分母是final的72例×2方法，以及dyna的12例×2方法×作者3次重复；本机每例每方法只有1次。这个核对不证明完整动作轨迹逐步相同。

| 数据范围 | 本机R84均分 | Van原记录均分 | 本机减Van |
| --- | ---: | ---: | ---: |
| dyna完整12例 | 4.049649788429 | 4.049344085786 | 0.000305702643 |
| final完整72例 | 3.483631177477 | 3.481389129962 | 0.002242047515 |
| 两数据集各50% | 3.766640482953 | 3.765366607874 | 0.001273875079 |

最后一行的Van数值是本次按R84权重重算，不能冒称作者发布的总分。双方都按每例 `clip(10*(1-C/B),0,10)` 计算，C含模拟IO、真实罚值乘Miss及D，B是相应机器同批Naive成本。本机七方法均分也已从588条保存metrics独立重算，与其finalized_summary一致。

## 决策计时解释分差

| 每例累计D的均值 | 本机 | Van原记录 |
| --- | ---: | ---: |
| final paired100 | 38.003474 ms | 93.241386 ms |
| final Naive | 43.145328 ms | 93.760303 ms |
| dyna paired100 | 3692.235564 ms | 9283.486629 ms |
| dyna Naive | 2321.910532 ms | 6065.442171 ms |

本机报告环境是i7 14700HX、WSL2、g++11.4；Van保存的运行上下文为Ryzen 5 7535U，且明确不保证宿主独占。dyna作者取3次配对计时，本机1次；final作者先测20再补52，本机为一个完整串行窗口。跨机器的D不能直接拼成一个排行榜，也不能将单次差异称为统计显著性。

只在保存记录中同时把作者候选和Naive两侧D换为本机D，其逐例分数与本机的最大残差为final `3.21e-8` 分、dyna `2.28e-12` 分，符合两位小数stdout的费用舍入。完全去掉双方D后，dyna均分均为 `4.049849820710518`，final均为 `3.4850045964848246`。去D结果只用于定位差异，正式含D分数不被替换。

Van dyna summary中的精确物理账与stdout顺序浮点IO也是不同数值表示；其RESULTS保留了exact、sequential和roundoff bound。不能拿精确字节有理数与stdout的几微秒差异误判策略改变；本次对比的是双方保存的计时IO字段，它们精确相同。

## 不同报告的范围与算法名称

Van当前最新的大量方法性能表为 [Round10报告](https://github.com/cyanneko/HuaweiHackathon/blob/6ded7022215b80a8edf4170faefe1ca4da16814f/src/Vanius0525/level1/round10/REPORT_V1.md)，使用60例既有train，paired100为3.744278、R80为3.742522、joint为3.735174。该60例与R84全84例的输入SHA交集为0。双方R80源码的Git blob同为 `a9e3ae2d54f2b418a15766909f4880d6d7192115`，SHA256同为 `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`；同源码在不同数据上出现不同胜负，并不是同输入结果冲突。

Round11最新报告是固定两条训练流、六个压力快照的observer诊断，不是新的完整性能矩阵。与R84范围可对照的作者成绩是 [final72报告](https://github.com/cyanneko/HuaweiHackathon/blob/6ded7022215b80a8edf4170faefe1ca4da16814f/src/Vanius0525/level1/round9/eval72/REPORT_V1.md) 和 [dyna12汇总](https://github.com/cyanneko/HuaweiHackathon/blob/6ded7022215b80a8edf4170faefe1ca4da16814f/src/Vanius0525/level1/round9/DYNA_FULL_SUMMARY_V1.json)。

`risk_pool100`是另一项联合风险实验候选，源码为 `round9/pure/return_risk_pooling100_v1.cpp`，SHA256 `52ae25812a9863eae0774b2d45e837fd499506431650b8943ed6e4e979c76d2e`；它没有替代当前推荐paired100，也不在R84的Van列里。因此R84只比较了推荐paired100，不能扩大为比较了Van的所有实验候选。后续若增加joint，应另列身份、在同机同范围测量，保留旧列和旧结果。

R84的3.766640为两数据集各50%权重；若把84例直接等权，本机Van将是3.564491。两个数对应不同汇总目标，不能混用。

## 核对材料与复现

`audit_results.json`保存精确统计与输入文件指纹，`case_alignment.csv`保存全部84例对应关系，`audit_saved_results.py`只读取保存的JSON和源码；没有新增solver、策略计时、输入正文扫描或训练。没有重跑策略或改写R84证据。

审计脚本默认适配原工作区布局。公开副本可通过 `--local-results-root` 指向R84归档的 `full_v2`，`--van-level1-root` 指向固定6ded提交的 `src/Vanius0525/level1`，`--local-paired-source` 和 `--local-r80-source` 指向R84归档中对应类文件，`--van-git` 指向含该固定Git对象的checkout，`--out` 指向新目录。读取作者文件可复用其Git对象；不需要原始大输入或私有执行日志。

归档只包含上述短文、审计源码、小汇总、逐例CSV和指纹清单。bare clone、原始数据、私有本机路径、可执行文件与历史大trace均不归档。
