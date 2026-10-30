# Fast ledger 独立静态审查

审查快照：2026-10-30 18:41:46 +08:00。**当前源码的计账推导在列出的前提下成立，未发现必须暂停验证的算术错误；不等于验证已通过或可直接产训练标签。** 此时 protocol 状态仍为 PREPARED_NOT_VALIDATED_NOT_USABLE_FOR_TRAINING，目录尚无 validation_report。源码可能继续修改，本结论仅绑定下列 SHA。

只读官方 engine、生成器、已生成 adapter、protocol 和 validator；不编译、不运行 native/teacher、不读取大 trace、不修改 Handler 文件。

## 快照身份与冻结框架

文件均相对 `hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030/corner_r75_v1/`：

| 文件 | SHA256 |
|---|---|
| prepare_fast_ledger.py | bef4c5122cde8a166c5b844849cee6139839a06bf888a65b3b6fbdbb1924f984 |
| fast_ledger_v1/adapter_ledger.cpp | cfad1939c51caddbe00313ef01780a7e2615c269684d2493141900de658d3eaf |
| fast_ledger_v1/validate.py | 960230d794ce3b3efe82a9463133244a1e3fe378fbde7c25dd7456bbb3bfd1a6 |
| fast_ledger_v1/protocol.json | 656b08646ec8ed0aa4c1a09244ced2c8d02c6932c4f69c1cd0895cf984000200 |
| adapter.cpp | fbd3d00c6a12662b0c5d6f1f9b88941ae729853bc2ce60ce3eaa7d2fbe744be4 |

官方参照 `round49_latency_baseline/reference_compilable.cpp` SHA 为 `1ed541a0d314c9b866b4a00198df3db5a3201d648e2c5b737b61cc8ab0e0a1da`。本次字节检查确认 ledger TU 的官方类前缀和从 `class HashJoinEngine` 开始的全部后缀保持原字节；`class R75Logic` 段与已审 adapter 完全一致。该 adapter 的冻结 R75 来源关系见 CORNER_STAGE0_REVIEW.md，不应把 ledger wrapper 当新提交框架或正式 D 测量对象。

## 官方执行语义

- SPILL 按动作顺序执行。已落盘或 size==0 时忽略；否则增加 write bytes/time、减少 memory_used、置 disk。
- LOAD 按当时驻留判定：已驻留或 BUILD 时忽略。其余必须检查 `memory_used+size<=limit`，失败直接非零退出；成功增加 read bytes/time、增加 memory_used、置 resident。零 size 的合法 LOAD 仍会改变驻留。
- 因而同一分区 SPILL→LOAD、LOAD→SPILL、重复动作不能按无序集合或原始驻留一次性计算。P 的动作也完整执行，P 自身不增加 hit/miss。
- Overflow 不会由 engine 自动挑 victim 或自动补 SPILL；只执行 scheduler actions，不够容量就退出。INSERT 原先在内存时，回调后新增 tuple 到 partition 和 memory_used，不额外产生 IO。
- 原先在磁盘上的 INSERT 则直接 WRITE tuple_size，同时增加 total_io_bytes，无需 O/M 回调。该写路径不能仅靠累加显式 SPILL 捕获。
- onM 之前 miss_count 已加一；动作 IO 在回调返回后执行。M 入口 prefix 已有当前 miss penalty，不能在 suffix 中再补一次。
- SWITCH 不增加 operation_count、不产生 periodic。最后若只有 hit PROBE 且未到 periodic，可完全没有 callback。

## 当前账本为何有条件正确

`record_ledger` 对每个实际返回动作使用 changed 列表，从前到后覆盖同 id 的驻留；因此计费使用最后一次动作后的驻留，包括 S/L/S。size 和 phase 在一次 executeActions 中不变，读原 state 是合适的。所有合法读取仅来自 LOAD，所以 ledger_read 可以跨 callback 累加。

每次 callback 用公开 `s.total_io_bytes + 当前动作delta` 覆盖 ledger_total。这吸收之前所有动作 IO，也吸收未触发 callback 的直接落盘 INSERT；它没有假装自己能从 SPILL 总和重建全部写入。最终 `write=ledger_total-ledger_read`。

当前实现**不维护 shadow memory_used，也不自己检查逐动作容量**，而是预测本次动作将成功。可接受的条件是同一 native 进程随后由原 engine 实际执行全部动作且正常结束；不能把 callback 中预记的值当已成功执行，也不能接收崩溃/OOM/超时输出。因此它是依赖官方执行合法性的被动账本，不是独立动作合法性校验器。

最后一个 callback 入口必须全部 operator 已 PROBE，且输入经静态检查保证每个 operator SWITCH 后没有 INSERT。此时最后 callback 之后不能再有直接写；若后续出现 miss 必然再有 M callback，与“最后”矛盾，因此后续无新 miss/IO。由此最后入口 total_io 加最后动作即可推 EOF，最后入口 miss_count 也等于 EOF miss_count。尾部 hit 数仍应从 native 最终摘要取，不由该账本推断。

仅检查 next_op、q、最后 action 为空、或最后 callback 自己是 M/P，都不足以替代上述全 PROBE+输入合法性前提。无 callback 或最后入口尚有 BUILD 时，当前 all_probe=false，必须拒绝快标签，即使可能存在更宽松的可证明特例也不猜测补零。

## 当前 validator 已做与尚待验

validate.py 静态检查输入 SHA、操作行数、连续 operator IDs、INSERT 在各自 SWITCH 前、PROBE 在 SWITCH 后、每个 operator 恰好切换。它要求 Worker 最终 audit/CPU release，已完整分支与 control_valid，force 文件 SHA，运行成功，单个 HANDLER_END/LEDGER，override_count==1、all_probe==1、非负字节/次数；再逐项比较旧独立重放的 write/read/miss/整数 G、callback 数和 hits，并以约 0.01us 精度核对 native IO 摘要。计划覆盖 16 anchors/89 已审 primary branches，目前本审查未执行、未见结果，不能写成 89 PASS。

force 身份仍在目标 callback 读取真实 private/physical prehash；其他 callback 跳过只读 hash/trace 不改变 R75 状态。原动作 proposal 仍调用一次，commit_actual(pre,actual) 顺序不变。依旧必须恰好命中一次，不能用进程 exit0 代替 force 数验证。

后续新快标签接收门槛：

1. 同源 input/config/binary/force SHA 与联合 anchor `(input, callback index, raw/stage, kind,args,q,public/private prehash)` 绑定；原动作 forced control 在同一实现上成立。旧 control_valid 不是新 anchor 的控制证据。
2. 输入阶段约束、最后全 PROBE、单一完整 END/LEDGER、正常 EOF、override==1 必须逐分支硬拒绝检查；OOM/异常/timeout/不完整输出不得产标签。
3. candidate IDs、动作类型、key/size/带宽/计数合法与整数边界应由既有数据/动作合同约束。当前轻量 validate_input 不是完整格式或数值范围验证器。尤其 commit_actual 早于 ledger 的 `.at` 边界检查，不能靠 `.at` 安全处理非法动作 id。当前既有 Worker 审计分支可继承已证合法范围，扩展输入不可无条件继承。
4. 若要声称独立“每动作容量验证”，需另有执行/重放证据；当前只可声称官方 engine 运行成功完成该检查。engine 对部分无效 SPILL/LOAD 静默忽略，不代表强制动作意图一定生效，应明确候选有效性合同。
5. G 用整数 `write_bytes*R + read_bytes*W + misses*penalty*W*R`，当前 input parser 限整数 W/R；Python 整数可避免乘积溢出。C++累计字节/id仍需在给定数据范围内无溢出。勿用两位小数 IO 差产生精确 G。
6. 该账本输出最终 total，不直接输出 anchor suffix。suffix 应减同入口精确 prefix ledger；M prefix 已计当前 miss。物理 Q 不计 instrumented D，计账优化后的 D 也不能当正式提交计时。

建议先接受既定 89 分支的独立旧账逐项对照作为该固定实现的正确性证据，再将相同失败即拒绝条件复制到新分支生产入口。不能把只写在 protocol 的要求当新生产器已实现；源码变更后更新 SHA 并针对变更重新审查。
