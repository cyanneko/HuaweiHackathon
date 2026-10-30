# R12正式构建与单遍执行合同

保留原 `PLAN_PROPOSAL_V1.json`、`SOURCE_FREEZE_V1.json` 字节。候选/参数不改；正式Naive路径改为已公开的 `round10/official_naive_reference.cpp`，SHA不变。

`python round12/pure/run_v1.py prepare`在共享experiment_lock内核对原60输入/顺序/seed及5旧协议，复用原Naive、paired100、R80普通二进制（逐一核源、生成TU、编译元数据及exe SHA），仅构建新候选普通版和buffered审计版。源码、输入、框架、脚本、root预检查、环境与二进制写入 `EXECUTION_FREEZE_V1.json`。prepare不执行solver。

root核读runner并另写 `round12/START_AUTHORIZATION_V1.json`，其中`authorized=true`且`execution_freeze_sha256`绑定本freeze后，才执行 `python round12/pure/run_v1.py run`。这只是已授权任务的内部运行前审核，不要求用户重复确认。

先执行新候选的5个旧小协议，每输入一次；独立streaming replay核所有动作、内存、读写字节、Hit/Miss和公式。复用旧R80 TRACE仅作身份绑定与描述性相等比较，不新跑协议参考，不要求不同算法动作全同。全部成功后，原60train每题Naive/paired100/R80/候选各一次，共240未插桩运行。固定逐题次序及题内方法顺序来自提案；同题4方法持同锁，避免共享实验并发，但不承诺宿主绝对独占。

主60不另做全流动作审计，不将旧audit当新候选完整合法性证据。新单遍严格检查5项stdout、有限非负值、整数Hit/Miss及总PROBE计数、Decimal费用公式、空stderr和60秒资源界。3参考方法的新IO/Hit/Miss必须与Round10相同源/输入原记录逐值相同。主费用使用输入真实罚值；在线代理100不变。日志/未完成目录/失败均保留，任何失败停止，不自动重试或删例。

逐例保留IO、Miss、决策时间、真实罚值、来源及stdout/stderr/执行记录；汇总分别给等权逐例物理比、总成本比、胜平负、最坏案例、同窗口含决策分。Naive归一化按官方`VAL=0或BASE=0记0`，其余clamp到[0,10]。候选须同时相对R80和paired100通过：均物理比≤.995、最坏≤1.02、含决策均分不低，且5协议全部通过。未过保留负结果，不即时调权、扩池或进dev。

实际输出目录为相对level1的`build/round12_soft_tail_v1`，同时写入正式PLAN的`output_directory`。完成后发布`RAW_OUTPUTS_V1.json`：捆绑240条短stdout、空stderr、执行元数据，以及5条小协议stdout/TRACE，供其他人核读原文；大二进制与官方完整框架不发布。RESULTS(records/runs)、SUMMARY(methods)、PROTOCOL_RESULTS结构沿用R10。

只有一个整体候选on/off，不能独立归因预算、标签惯性或γ各因子。单buffer公式的模型失配与合法性边界仍以 `DESIGN_V1.md` 为准。不读AI/reserved dev/eval/dyna，不追逐未发布上游参数。root统一复核发布。
