# R85 两项独立消融：READY

按冻结计划 `docs/superpowers/plans/2026-10-30-r85-prior-and-anchor-ablations.md` 实施。没有合并两项变化，没有扫参数、生成数据、训练或性能评测。生产源码只有调度类改动，官方 TU 的类外前后缀逐字节保持；父 source/TU/ELF 均重新核 SHA 不变。

- **R85_fast_prior8**：继承 R81 op256/cond2048，仅将快算子边际总 prior 从 64 改为预声明常数 `8.009479828345365`。慢分区条件的 prior64、时钟、异质性、所有 guards 不变。该常数匹配固定观察率假设下的平均先验/质量比，不是 ESS 校准或已证实的修复。
- **R85_hier_anchor**：继承 R80 hierarchy，`release` 默认 mode2；只在原空间不足、all-PROBE、非 scan/cycle gate 内比较 mode0 替代。flat 概率、64 窗口、2sd、100 代理罚值、prune 和严格负优势比较不变。空证据、相同方案、平局保留 hierarchy；最终动作仍仅由原 callback 记录一次。替代 proposal 可 lazy advance 统计，不能声称私有状态与从未比较的父策略逐字节相同。

一次有界编译测试窗口耗时 **20.199269171 秒 / 90 秒**，已退出，`active_child_processes=0`。两个官方 TU 编译通过，七个小型功能测试程序通过：A 的概率直接向量 oracle（归一、非负、有限、K1/P1、空样本、长空窗、epoch、next 去重、miss 不另加样、慢条件独立及常数推导）；B 的 hierarchy anchor、完整 pruned plan 比较、四类不满足条件路径、相同/平局/空证据、delta 符号/已知 next、无重复 refault/最终 intents；两版各运行原 callback 测试和 400 步合法回调轨迹。

红测为实际编译运行：A 同一概率 oracle 在冻结 R81 的数值概率断言失败；B hierarchy 空证据 anchor 断言在旧 paired 版本失败。B 红测使用旧 paired 参照，**不是声称原 hierarchy 父在空证据时失败**。原 stdout/stderr 和退出状态完整保留，无意外测试失败或后续修补。

`parent.diff` 便于审阅；`producer.json` 给出每项 source/TU/ELF、父身份和编译参数；`source_manifest.json` 固定所有源文件/测试及计划；`test_summary.json` 记录全部命令和结果；`release.json` 绑定最终 producer 和测试。测试头暴露私有成员仅供定向测试，生产 TU/ELF `instrumented=false`。这不是性能验证、全输入合法性证明或方法晋升；Root 后续独立审查并授权正式计时。
