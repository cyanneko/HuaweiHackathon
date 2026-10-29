# 每小时研究续接提示

每小时继续本项目的Level 1优化。先读项目AGENTS.md、src/Vanius0525/HANDOFF.md、level1/HANDOFF.md和最新实验摘要，核对分支、已有改动及运行中的进程，保留单写者；不能重启重复实验或覆盖他人改动。

继续纯数学/算法与AI两条路线的调研、设计、实现、测试和迭代。优先实际Level 1：I/O+miss罚+决策时间。只提交C++14的MySpillScheduler类；不修改框架、不注入隐藏输入。所有用例自行生成。离线训练特征严格复现在线部分观测；新想法先查相关文献。

每轮完成一项具体可验证改进，保留负结果和反例，核对新seed/OOD、动作审核和CPU开销，更新HANDOFF。候选不能只凭开发集封顶50晋升。仓库完成一个完整阶段后按授权只提交本任务文件并推送source/Vanius0525；不force、不动其他成员分支。

若有已在运行的本地小时检查器，读取build/hourly/status.json及最新报告，不同时启动计时。该Python检查器完成回归后使用已验证的官方 `codex queue` 将本提示排入原会话，不创建新代理。会话续接依赖宿主WSL及app-server继续运行；这不是云端Scheduled任务。收到用户停止才停止持续迭代；额度中断保存状态，等待真实续接触发。

评分续接约束：读取SCORING_POLICY.md，三成员各1/3、成员内常规80%/明确corner20%，同时保留官方口径；缺任一成员完整结果不能晋升。自己的数据已发布datasets@e119c23，Vanius0525 v0.1.0，合法eval209；end_insert缺SWITCH只作diagnostics不计分。
