# 实验、负结果与未完成尝试索引

失败或未胜出的方法保留源码、输入/模型/配置身份与复现边界，不能只上传成功者。分类以[机器可读索引](status_index.json)为准：validated_negative为指定条件下已完成的负结果；implementation_failure必须有已识别实现错误；execution_incomplete只描述未完成执行尝试；experimental_not_promoted为尚未推广的实验候选。四者不混用。

| 方法 | 状态 | 原数据/条件 | 材料 |
|---|---|---|---|
| R61树 | validated_negative | family CV及0.4/32；未优于固定SF，不推断所有树无用 | [源码/模型/452标签/配置/复现入口](r61_small_tree/README.md) |
| R62 soft | validated_negative | 0.4/32单次，严重尾部 | [原源码与固定公式](r62_rule_experts/README.md) |
| R62 pair8 | validated_negative | 0.4/32单次，最坏43.695590倍 | [原源码与固定公式](r62_rule_experts/README.md) |
| R63 Ghost | experimental_not_promoted | 0.5/40单次，仍有7.458362倍尾部和维护成本 | [冻结快照](r63_ghost_refault64/README.md) |

R61初次8例尝试另记execution_incomplete，后续重试已完成。没有证据认定上述R61/R62为implementation_failure，故该类当前无条目。未注册新专家ID、不改默认/官方Naive，不把保存复现材料等同本轮重新执行。
