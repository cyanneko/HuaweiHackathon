# 第四阶段：恢复与退化定位（2026-10-30）

目标：继续提高Level 1纯算法及AI成本表现，保持部分观测、C++14/CPU/标准库、单类提交和三成员分别均分及等权汇报。独占写入 src/Vanius0525/level1，分支 source/Vanius0525。接管基线9aa7cac，工作区干净；只读队友数据，不读算法。

已完成：
- 阅读AGENTS、README、指南、指定会话交接及本目录历史。python mean_score.py退出0，重算纯3.1340875330617863、AI3.2111061351745653；冻结指纹由脚本逐报告核对。
- 原始报告只读归约生成BASELINE_DIAGNOSTICS.json。AI相对纯最差：本人serial_293046为4.1667倍、burst_295012为3.3416倍；cyanneko cross_operator_0为1.800倍；liunian almost_M_0897为2.800倍。纯相对Naive：liunian corners_0996为3.478倍。精确值以JSON为准。这是排除决策时间的I/O+Miss诊断，不能替代当前成绩，也不是新实验。
- 定向复查HALP/LAH会议页面，新增Merlin（OSDI26）摘要来源，见RESEARCH.md。不能声称完整精读Merlin或直接适用其保证。
- 新建hourly_resume.py和更新提醒原文；python -m py_compile通过。codex queue当前会话验证返回0；宿主进程启动及后续存活核验通过，状态waiting、间隔3600秒。旧STOP和旧运行产物保持。该检查器只检查SHA并排队提醒，不自行跑实验，不保证机器休眠/服务停止后仍执行。状态及绑定在build/hourly-resume（忽略）。

下一步（尚未执行）：
1. 对almost_M、burst和corner三类退化做首个动作分歧诊断；先检查已有轨迹，避免重复计时。
2. 检验AI候选重排是否造成额外写出：当前按启发式筛前4后覆盖priority，随后直接按网络次序累计释放；相较纯算法单受害者路径，可能将一次足够的SPILL替换成多个小对象SPILL。此为代码支持的机制假设，未证实是上述退化的原因。先记录每次need、受害者集合、写出字节和未来成本，不能只按即时代价晋升（早期cover最差189倍已有反证）。
3. 检验BUILD停滞下历史观测密度与scan误识别；已有phase一刀切保护已被新OOD否决，不重走同一路线。
4. 若形成新候选，先曝光集机制消融，再seed297000起及独立新分布外推，随后三成员完整集合审核/串行计时。固定环境和锁；当前尚无新候选收益或晋升结论。

正在运行：只有本地每小时检查器，无benchmark/stress/train任务。下一条可执行动作：从BASELINE_DIAGNOSTICS中的报告和输入指纹定位burst/almost_M轨迹，统计首处分歧的受害者数量和写出量。

## Open Ideas / 值得深挖的问题
沿用上级“预取动作改变未来信息机会”，本阶段没有新增已达到独立立项判断标准的问题。受害者集合重排先作为工程机制假设，不包装新颖性。
