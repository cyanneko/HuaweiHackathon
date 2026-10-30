# R81创新机制与消融：固定两批次最终846格

[规范中文报告](report_zh.md) · [算法与复杂度](audit/algorithm_and_complexity.md) · [846行](original/REVIEWED_PER_CASE.csv) · [负向条目](original/REVIEWED_NEGATIVE_CASES.csv) · [独立终审](audit/ablation_result_review.json)。

原846尝试保持INCOMPLETE（845有效+1局部预算watchdog），恢复仅最后case全部九方法。837原+9恢复为最终846，旧8成功+1失败保留且不选入，共855尝试；不称原轮一次全过。恢复新Naive与D整case替换，188同输入控制复核通过。

Full主旧84分4.084507912，stat3.439812321单列。去算子热度主分降低1.395831780，单位成本干预降低.414375739；效应不均匀不可相加。scan/cycle的94例物理完全相同，本轮物理贡献记零；stat上统一慢时标/去预取反胜的负结果保留。不据此调参/择优，不承诺官方创新分/隐藏成绩，最终R81不变。

保留源/补丁/TU、协议、原失败、恢复、selected来源映射和审核；测量C++/原输出保字节，私有GO/owner不公开，元数据路径与进程字段清理，原件/公开SHA分列。需要恢复研究布局/依赖，不提供ELF或重复输入，没有新native/编译/复核。
