# Round11：两条固定训练流的最小R80 observer

2026-10-30。pure独占本目录；root负责round11根与发布。AI暂停。只取已发布24 Zipf原顺序前两条train548/train593，仪器化版本每条至多一次；不计新成绩、不读dev/eval/dyna、不扩大面板或修改参数。Round10已冻结文件不改。

已生成并冻结完整observer源码、最小插桩diff、合同和runner/audit。`BUILD_FREEZE_V1.json` SHA `52c3c8c39dbb386b3bac0955779ca7e4d918204f52d9ad7aa0249e2efc79a6b3`；原R80源码SHA `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`。反向恢复逐字节等于原源码，原357个CRLF保留。未记录propose之后已被fallback改变的victims_前四项；完整对象概率允许离线按原规则重建。

root运行前审查已通过，`../OBSERVER_PREFLIGHT_V1.json` SHA `882c6fb1d0310728a9c462b6e05337cca844546cbd19e780af8a554e97ca8c55`。`python -u round11/observer/run_v1.py` 已 exit 0：一次编译、原两训练流各一次仪器化执行，共6快照。两例原R80 IO/Hit/Miss逐值精确相同；6个hier副本SPILL与真实prune后动作逐序相同。0新增参考/普通性能/teacher/dev/eval/dyna运行。没有运行中的命令。

`RESULTS_V1.json`、`SUMMARY_V1.json`与`REPORT_V1.md`已完成。仅548 q4100的flat/hier集合不同：8 vs11个受害者，flat多写11,076B，当前写多8.790476μs；两个分布各自偏好自身集合，不能推出完整流优劣。其余5快照序列全同，含K=1的593全部3个。share不是恒.75，K=1仿射恒等式通过。原始日志在`artifacts_v1`；无全流动作TRACE，物理一致不等于证明全流动作相同。

最终冻结 `FINAL_FREEZE_V1.json` SHA `163792bb8124ef54d8b772aea5952333885d0fc7a1b9b9774635db5ce7b5cf3c`，绑定26文件；加freeze与本HANDOFF共28个发布文件。列表在freeze的publication.include，排除__pycache__与build二进制/官方框架。下一步：root独立复核并统一发布，本目录不自行提交、不追加solver或调参。

## Open Ideas / 值得深挖的问题

- 2026-10-30：将概率收缩与离散集合改变分开。K=1时hier是flat与均匀先验的仿射组合，频率排序本身不变；若动作改变，应检查100/s密度、子集大小/释放量与集合基数，而非直接说热点排序反转。本轮固定阈值观察，不按动作是否不同选择快照，不宣称新颖性或长期收益。
