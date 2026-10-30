# train592/519 首次动作分歧：执行合同 V2

2026-10-30。root 已明确授权执行；V1 计划原字节保留。AI 暂停，后续测试单遍；本项不是测试重跑，新增 solver、编译、teacher、性能评测均为 0。

固定 train592、train519，按此顺序，各与 pool、flat、global 三份已冻结 100μs 风险候选比较。只读原主60成功审核日志及原训练输入，不读 eval/dyna 策略结果。输入、源码、成功 canonical、stdout/stderr、既有 freeze 和本次实现均在独立 EXECUTION_FREEZE 中绑定。paired 日志还须匹配旧 COLD_BUILD_PLAN 的既有 SHA；候选日志须匹配 MAIN60_RESULTS 既有 SHA。先检查可见进程与文件状态；进程命名空间观察不声称宿主全局空闲。

**覆盖修订**：撤销 V1 的20,000 PROBE任意截断。每对顺序重放至首次实际返回动作列表不同即停止；若始终相同则至原完整输入 EOF，最多6个共同分歧状态。不因局部结果改范围，不读分歧后轨迹。为验证文件身份，可顺序哈希完整文件，哈希不作后缀动作分析。

所有重放持 `level1.workflow.experiment_lock`，逐对串行。两个独立内存/分区/phase/字节/Hit/Miss账本从相同输入和各自 TRACE 重建；每次回调核对原始操作位置、tag/目标/tuple_size、完整合法 SystemState、next 原始请求及前缀动作。SWITCH 不计入 periodic 时钟；当前 Miss 先增加 miss_count，两个回调均使用当前操作的下一条原始请求。完整 state 含模拟内存、所有分区大小/驻留、phase、R/W、Hit/Miss、累计 I/O 字节及 next。此前已返回动作必须逐字相同；首差之前两个独立 state 的规范 JSON 必须完全相同。

首差仅在当前 state 的副本上检查两份实际动作的合法性及立即效果，不执行后继请求：记录受害者集合/顺序/基数、实际 SPILL 字节、需求 LOAD 与 periodic/其他预取分类、需释放量、释放超额、动作后空闲与驻留差、当前读/写成本。原两 proposal 的来源标签不能从所选动作的顺序自行猜测。

next-only p 可按冻结 sampleNext 的2048半衰期、≥256 PROBE更新、prior64与来源去重独立复算，记录样本量、有效量及对实际两动作差的 I/Fp/U；这些为源码公式复算，不冒称 C++ 已打印数值。符号固定为“候选实际 SPILL 集合 − paired 实际 SPILL 集合”，不是未经验证的 dynamic−history 标签。完整统计量若无法由原 TRACE 精确核对，输出 null 和缺口；特别是未选 proposal、原比较方向、RiskCore.before/future/sync 的逐次浮点状态、D/Z/h/兄弟项及实际 Fh/margin 没有原始快照。若只能得出两种标签下的条件式，不据此认定机制错误或全流退化原因。

结束条件：六对完成或任何身份/状态/动作断言失败。失败保留日志与状态，不自动重试。不新增配置、observer、续接或特判；需要 C++ 内部精确证据时另提最小 observer，等待 root 授权。首差能解释发生了什么，不能证明该决定导致全流退化或 h 估计不准。
