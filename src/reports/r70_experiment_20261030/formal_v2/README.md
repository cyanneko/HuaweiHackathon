# R70 model_v2 评测入口

v1 在正式运行前被替代。原 `tmp/r70_final_eval/model_v1.precommit.json` 字节保留，`SUPERSEDED.json` 记录原因，`STOP_REQUESTED` 阻止误用旧入口；没有 v1 formal 或 holdout 结果需要撤回。

本轮特征版本固定为 `r70-causal32-v2-sequential-sums`：Python 显式顺序 double 聚合与 C++ 对齐，避免微小聚合差异经离散 rank 放大。相同 anchors 的整数 suffix G 保持不变，由生产方重提特征、固定 seed/32epoch 训练 model_v2 并重新完成全部 dev8 parity。v1 验证不作为 v2 通过证据。

等待 Root 给出新模型 SHA 后，用 `freeze_precommit.py --model <model_v2/model.json> --model-sha256 <Root提供的SHA>` 冻结唯一 primary。随后 `bind_producer.py <artifact_manifest>` 静态核对 v2 源码/权重/特征/预处理、评分 vectors、全 dev8 动作 parity 和两份已编译程序身份。四个原基线及两个新程序均复用已编译二进制，不重复编译未改源。

`formal96.py` 接受匹配 `lease_request.template.json` 的一个 Root release，先六方法×dev8=48格；全部有效、身份未变则自动 holdout48。推进条件只看有效性和预承诺，不查看分数、loss 或排名，不等待中间审批，也不据 holdout 调参。失败或缺格立即保留并停步，成功格身份一致时复用、不重跑；全程只有一次 holdout campaign。

dev 输入清单与 holdout 数据封印沿用原字节。本目录全新 selection/precommit/runner scope、输出、parity 身份，与 v1 和 final50 冻结榜分离。实际 Linux HOME 持久目录、原进程组超时和官方五指标解析器继续复用；正式 D 等全部计算释放后串行测量。

当前新模型 SHA 尚待交付，未生成 `selection.bound.json`，未运行 formal、编译或训练。`summarize96.py` 已准备，完成后分开给出 dev/holdout 的六方案、NN/Heuristic逐例比值、IO/miss/每例累计D和所有负例。
