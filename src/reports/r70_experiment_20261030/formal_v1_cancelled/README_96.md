# R70 预先固定模型的 96 格评测

本轮唯一 NN 已由 Root 在正式 dev 前固定为 model_v1：32→16→1、545 参数、base13 residual，模型 JSON SHA 为 `4798e68bfd3fb57230ce357115c6f1214e3639f4bea66895c0297a02ce50b630`。Heuristic 使用相同观察器、候选池、特征、tie 和动作生成，仅 base13 零 residual。

本文件与 `model_v1.precommit.json` 取代旧 README 的“dev 后再等人工选择/holdout 审批”步骤。旧 holdout seal 中的数据清单和配置 SHA 继续有效；所有模型选择、权重或阈值调整均不能利用 holdout。

生产方按 `producer_artifact_contract.json` 给出两份 formal binary 与源码/依赖/模型身份、评分 vectors 验证及完整 dev8 动作 parity。`bind_producer.py` 只读取源码和元数据，生成一次性的 `selection.bound.json`，不重编译和运行程序。四个既有基线及生产方两二进制均按原 SHA 复用。

`formal96.py` 为实际待用控制器，复用 final50 已验证的进程组超时/清理函数和官方五指标解析器，输出路由全部在本目录。它需要一份匹配 `lease_request.template.json` 的 Root release：六方法身份、预承诺、dev 清单、runner SHA、Worker/训练/NN验证释放，以及正式 D 时间窗。模板不是执行授权。

一个 campaign 内先做 dev48。48 格全部有效、全部身份仍与预承诺一致后，控制器自动解封 holdout8 并执行 holdout48，不查看得分或排名来决定是否推进，也不等待新的人工确认。非法输出或失败格立即留证停止；缺格时保持 partial，holdout 不会因不完整 dev 被提前打开。成功格续接时只核身份复用，不重复测量，不增加 repeat。

输入和输出缓存采用运行时实际 Linux HOME 持久目录；正式运行单进程串行，60 秒/格、至少 70 秒余量才入场。所有 stdout/stderr、退出/超时、五项原始指标和源/模型/输入/二进制身份保留。dev 与 holdout 分开汇总，八例未封顶主分上限各 80，逐例均分和每例累计 D（微秒）另列，坏例全部展示。

当前只有源文件和元数据准备，尚未运行 formal D，也未重编二进制或训练。本控制器的首次运行还需在获准窗口验证实际接入。
