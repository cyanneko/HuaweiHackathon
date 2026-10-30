# R85 完整新面板评测协议（运行前冻结）

方法固定为 Naive、R80_next_hier_fast100、R81_op256_cond2048、R80_paired_hier_fast100、Van_latest、R85_fast_prior8、R85_hier_anchor，顺序如列。方法来源为冻结 R84 v2 methods.prepared.json 与 R85 producer，保留 source/TU/ELF、编译参数及 Van 捕获提交归属；不以分支名称充当身份。

数据仅本轮预声明 18 例：TRAIN12、DEV6，所有合法声明用例均测全部七方法；生成失败留在 accounting，不替换、修剪或伪称完整18。运行失败、超时、缺失和额外格均不通过完成门禁。没有 advance 筛选、D 硬淘汰或默认晋升。DEV 必须等待 TRAIN 完成门通过，并绑定其 selection、rows、raw/finalized summary、completion、gate、campaign，方法全字段及 data manifest 完全相同。

每阶段单独 180 秒 controller 预算，每格官方墙钟上限 60 秒，实际可用时限为剩余预算与60秒之小者。CPU 串行，1 repeat，不使用 GPU；每例方法按固定表左轮换 `case_index % 7`。病例顺序为 `SHA256('r85-'+phase+'-order-v1'+case_id)` 升序，次序在 native 前写入不可覆盖的 selection。失败格不删除，剩余预算允许时继续下格；不静默重试、不自动恢复，不依据结果改候选。

复用 SHA 固定的 R80 execution core；prepare 核小合同/metadata 和方法身份，正式 run 的 core 对输入在执行前后核全 SHA。保留全部 stdout/stderr、解析结果及身份。这里只做开发诊断，不代表原 dyna/final 完整回归或官方隐藏集；DEV 执行后标为已曝光。

每例成本 `C=Total_IO_Time+penalty*Miss_Count+Total_Decision_Time`，罚值和实际 probe_count 来自该输入合同，不能用 N 代替 probe。同批同例 Naive 成本为 B；分数 `clip(10*(1-C/B),0,10)`，C或B非正按冻结评测器记0；raw保留 `10*(1-C/B)` 的负值，B非正则标未定义。汇总列出全部分母计数，不丢未定义例；D 是实测累计调度时间，物理成本为 IO+miss罚值。输出平均分、未封顶分数和、raw、IO/罚值/D、成本及物理比。各方法保留对 Naive、两父 R81/R80 hierarchy 及 Van 等七方法的对照；A明确对应R81，B对应R80 hierarchy。无本轮R75，不能填造同轮R75对比。

总体按本阶段实际合法病例等权；同时列 track/family/mechanism/参数层分组，各组明确分母，并另列等权 track/family 均值，不与病例等权混淆。不构造 bandwidth 配对或因果差值。18个独立seed，因子覆盖不是完整析因设计；dynamic TRAIN 的 shared/staggered 与压力有关联，分组差异不能单独归因为相位。分位数用最近秩 `ceil(q*n)`，报告P50/P90/最大成本比、最差例ID及胜/平/负。

**完成门禁**：raw summary 仅标 `row_grid_complete`，始终 `complete=false`，避免全行齐全掩盖 controller 尾部错误。最终完成须同时满足矩阵完整有效、controller正常返回、completion状态ALL_CELLS_TERMINAL、error为空、身份无变化、terminal=valid=planned、selection/campaign/rows/summary SHA与CPU释放证据一致。`completion_gate.json`最后落盘；任何检查失败不得用 raw aggregate 宣称完成，也不得准备DEV。缺门文件等于未完成；完整失败证据保留，不覆写已有selection/结果。

一次测量不能支持微小D差异的显著性声明。clip均分不能隐藏原始成本或尾部退步；结果不自动改变正式提交。
