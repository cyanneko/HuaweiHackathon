# Corner stage0：真实R75续接下的首动作改进空间

8个新train输入，4机制×压力3/12；同机制压力兄弟共用seed，因此是4条训练seed谱系。每输入按预声明hash选一个O、一个M，共16起点。8000操作/输入，仅接口与局部空间诊断；dev未读取或评分。

统一执行墙时91.2396秒/180秒，89/89候选完整，16/16原R75动作force控制复现全轨迹/private hash/精确账；6个预声明逆序重复一致。所有候选HANDLER_END overrides=1，无替补样本或续有利样本。CPU已释放。

| 机制 | 压力 | 改善起点/选定 | 最大条件剩余代价降幅 |
|---|---:|---:|---:|
| fast_shared | 3 | 2/2 | 30.6112% |
| fast_shared | 12 | 1/2 | 0.5371% |
| fast_staggered | 3 | 2/2 | 18.5414% |
| fast_staggered | 12 | 2/2 | 1.1330% |
| burst_staggered | 3 | 1/2 | 0.1650% |
| burst_staggered | 12 | 2/2 | 0.5863% |
| slow_shared | 3 | 1/2 | 2.5091% |
| slow_shared | 12 | 1/2 | 0.3374% |

12/16起点存在更好的当前动作，随后仍由同一个真实R75继续。最大30.6112%是该起点剩余suffix的条件差，不能当完整输入加速、多个决策叠加收益或AI模型改善。Q是固定合法候选池内的一次动作偏离，不是Q*。

候选union始终包含真实R75完整动作；同spill集合只按R75原顺序保留，不改变执行顺序。非空periodic按真实ordered SPILL/LOAD产生IO，不增hit/miss/q；只重置明确版本的辅助R65 observer，不重置或冒称恢复R75 private history。

同池零残差规则（当前x13+原tie）在这些已算分支中的一次偏离Q_R75胜/负/平为7/8/1；这是现有矩阵查表诊断，不是闭环运行或新模型结果。full32相同输入异cost组为0。

## 精确账与验证边界

G严格来自真实ordered动作/输入字节的整数write/read/miss账；stdout两位IO只做舍入容差交叉检查，未反推G。M起点账已含触发miss，不重复计罚。

8条baseline的31226个callback entry物理hash和显式kind/参数/q已逐条验证，包含22个真实非空P。每候选native从原输入重放同一真实prefix；prefix全部动作、物理和private pre/post hashes逐条与baseline相同。强制点之后的每个callback物理entry hash/动作/整数账由Python独立核对，且明确命中一次强制。

physical hash未包含BW及显式operator/partition ID，这些另由完整输入SHA、固定header/config、canonical IDs及callback参数锁定。private_post为policy commit后、engine执行前；没有跨实现重建R75私有历史，也没有声称直接输出每步所有partition值。

R75保持原cab5源码不变，实际运行的是经no-override parity和intent反例验证的诊断副本，保留真实观察、只重绑最终实际动作意图。所有日志/哈希/teacher墙时不当正式D；将来hybrid若每次计算R75候选，该真实成本仍须计入部署D。

## 交付与下一步边界

labels.jsonl包含16条train监督、89个完整候选代价/原32维因果特征，1条全tie需零训练权重。只白名单读取x/target/mask/权重，raw、private hashes、case/seed/continuation等仅审计使用。artifact_audit.json保留整数账/178次witness与trace哈希/控制与反序核验。

这批仅8000操作，没有训练或dev评估，不能声称corner AI已超过R75；按预声明规模门，至少需要另冻新>=100k输入验证后，才能提出corner性能结论。后续训练/扩样由Root与Handler决定，本轮不自动执行。
