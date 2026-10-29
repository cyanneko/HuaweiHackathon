2026-10-29：首次发布；仅本成员目录。原输入保持字节，manifest+逐例meta提供来源和指纹。train192、eval209，常规192/corner17，另有diagnostics1例不计分。公共校验报告见VALIDATION.json；本发布不修改其他成员数据或算法。

发布校验发现旧end_insert例缺少必须的SWITCH；原字节保留于diagnostics，不属于合法eval，也不参与内部性能评分。其他401例通过公共校验。
