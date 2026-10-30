# 原两训练流全流周转分账 V1

2026-10-30，root 在六对首差完成后明确授权。仅复用 `RETURN_RISK_TAIL_ATTRIBUTION_EXECUTION_FREEZE_V2.json` 内 train592、train519 及 paired100/pool/flat/global 八份成功 TRACE。候选、代理100、输入和旧结果保持；AI暂停；0新solver、编译、teacher、输入、dev/eval/dyna读取。不重复性能测量。

逐流持公共 experiment_lock，每条输入顺序完整读取一次，同时维护四个独立状态账本、各自消费已有TRACE。记录每个对象的BUILD初写/追加、PROBE写次数/字节、需求LOAD/periodic预取/其他LOAD次数与字节、Hit/Miss，以及终态大小/驻留。原请求频数仅用于训练描述性核对，不成为在线特征、教师或参数选型标签。

完整核回既有 canonical 的四种整数字节、Hit/Miss、回调数、动作数和分项费用；检查所有合法SPILL/LOAD、容量、BUILD字节恒等式与EOF、header计数。I/O精确字节折算与旧逐次浮点累计按原 cost_replay_precise 误差界核对，不使用新的固定宽松阈值。六个首差回调的完整state与动作再绑定到V2已经保存的边界证据；不是再运行求解器。

结果报告全体对象分母及逐方法需求/预取分项；对象贡献是候选减参考的实际写读字节及实际罚值费用分解，可列最大正/负贡献，不能将事后贡献叫首差的因果效应。终态驻留不同、预取改变Miss回调/观测、未来策略耦合都保留为限制。最多2×4条既有轨迹，完成或任何断言失败立即停止，不换数据/参数、不自动observer或rollout。
