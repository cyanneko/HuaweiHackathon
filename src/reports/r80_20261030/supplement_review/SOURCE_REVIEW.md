# R80最终源码数学复核

PASS（静态范围）。producer35ecb0a3dde9a7bca76898c624890f1d5b8722175e79a76502c442c3acd8a3cd；独立核4源码SHA及差分。Root训练prepare已核全部source/TU/ELF及官方框架骨架。本review不运行native、不修改候选。

- penalty100去注释/空白后与冻结R79只有priority penalty常数1→100；不读取真实输入penalty。flat/hier/paired三份主体完全相同，只有模式宏不同。
- N=K×P，统一q*=max(q,last_next)。flat分子总和S+64，因此归一；hier对每op求和为(1−a)So+aSo=So，保持同样全局归一。独立ci没有被混合值回写。
- next按ordinal去重，当前miss不增加next计数；group/partition采用一致公共衰减时钟。LUT0..8192逐项调用原nextDecay，越界仍用原公式，不是近似插值；测试记录验证精确值。
- paired用flat概率评估alt−base对称差，共同victim抵消；系数=sign×(bytes/read+bytes/write+100)，即时write与已知next暴露项、64×mean及2×sd和plan一致。S或W2非正保留base，没有额外ESS准入阈值；等方案不切换。
- paired仅all-PROBE、非scan/cycle；两计划先合法裁剪，最终callback在最终prune/LOAD后仅record一次。propose不confirm或追加intent，不重复计refault事件。查询会lazy advance风险暴露和sharing时钟，不应称为完全无副作用。

发现并已修复：flat/hier在均匀cycle MRU早退未命中时会落入频率ranking。最终条件明确加!uniform_cycle_；空MRU cycle定向断言在旧版RED、三新版PASS，避免改变原cycle fallback。

保留限制：IID式方差界未证明对策略选择后的next观察校准，不是置信保证；测试与静态审查不证明实际得分或CPU收益。所有性能结论等待冻结TRAIN与新validation24结果，不能据final调阈值。
