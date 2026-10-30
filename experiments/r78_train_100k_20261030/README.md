# R78 新100k TRAIN归档 1.0.0

仅含明确的8个TRAIN输入，各100000操作，共800000。四种机制各一个新seed，压力3/12成对，合计**4条种子谱系**，不是8个独立随机重复。所有输入原字节保留，inputs.json给出公开路径、逐文件SHA、来源及split。

| TRAIN下载 | 机制 | 压力 | 谱系 |
| --- | --- | ---: | --- |
| [r78_scale_train_fast_shared_p3](train/r78_scale_train_fast_shared_p3.txt) | fast_shared | 3 | r78_202610309601 |
| [r78_scale_train_fast_shared_p12](train/r78_scale_train_fast_shared_p12.txt) | fast_shared | 12 | r78_202610309601 |
| [r78_scale_train_fast_staggered_p3](train/r78_scale_train_fast_staggered_p3.txt) | fast_staggered | 3 | r78_202610309602 |
| [r78_scale_train_fast_staggered_p12](train/r78_scale_train_fast_staggered_p12.txt) | fast_staggered | 12 | r78_202610309602 |
| [r78_scale_train_burst_staggered_p3](train/r78_scale_train_burst_staggered_p3.txt) | burst_staggered | 3 | r78_202610309603 |
| [r78_scale_train_burst_staggered_p12](train/r78_scale_train_burst_staggered_p12.txt) | burst_staggered | 12 | r78_202610309603 |
| [r78_scale_train_slow_shared_p3](train/r78_scale_train_slow_shared_p3.txt) | slow_shared | 3 | r78_202610309604 |
| [r78_scale_train_slow_shared_p12](train/r78_scale_train_slow_shared_p12.txt) | slow_shared | 12 | r78_202610309604 |

generation保存冻结生成器、参数与准备脚本；provenance/source_data_manifest.json是清理本机路径后的原研究清单，其原始SHA为703b48a3522a09872728b018140613a28a74481ced3084fdd9cc9235720aacdb，公开件SHA另列manifest。此处不发布ELF或大动作trace/private witness。脚本是原研究布局的审阅快照，重现前需恢复manifest映射并编译生成器、绑定本机环境；输入本身可直接下载使用。

## 测试集发现与冻结边界

本归档版本1.0.0，**train=8、dev=0、eval=0，不是已注册测试集**。实际评测器默认从datasets根枚举成员，读取各成员非空eval/**/*.txt及eval/VERSION。本目录位于experiments，且没有eval；不添加R78排除规则、不改变任何已存在非空测试集的发现、分组或评分。即使显式把experiments作为数据根，本目录也按既有缺失eval规则处理。

本批没有进入既有成员785/旧576冻结范围、旧30/dev24抽样、final_dataset或dyna_dataset的冻结评测；原因是新增材料仅TRAIN且均未改原输入/集合。独立训练版本不是旧成员eval/VERSION，旧suite/count/成绩保持原样，不重跑长矩阵。将来若明确注册为测试集，须按那次任务设置eval/VERSION、count和suite身份，不能用本训练清单冒称已计入全测试榜。

本轮有24次R75/A/B完整训练诊断，物理目标为模拟IO+真实penalty×miss；没有同轮Naive且未正式测D，不给比赛分。A平均仅小幅改善，B无净收益，两者均未推广；报告与源码在source/cyanneko的R78实验归档。stage0旧8k输入没有重复上传，dev未引入或改split。
