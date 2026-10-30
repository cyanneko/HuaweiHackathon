# R81独立stat、BUILD与创新消融：固定输入引用

本目录只引用输入，不复制原始数据、源码、ELF或结果日志。[main可读报告](https://github.com/cyanneko/HuaweiHackathon/tree/230f5d927388979e286a0d8abdc8883876048315/docs)与[source完整证据](https://github.com/cyanneko/HuaweiHackathon/tree/31dbf25826019cdb8983f1346b765172c67e6fc6/src/reports)已分别固定。

- stat：1.0.0 eval10，两法×3重复，60格有效，独立于旧84主榜。
- BUILD：dyna1.0全12+stat1.0 eval10，三法各一次66格，方向混合且未采用；不计算22池化均分。
- 消融：九法×(dyna12+final2.1 eval72+stat10)，最终选择846格。原批永久INCOMPLETE（845有效+1预算截断）；最后stat例全九法固定恢复，837原+9恢复，855总尝试；原8个成功和1个失败不选入但保留source证据。

旧主评测固定c65，不用移动分支的final3.0。stat压缩输入固定[e78279e3](https://github.com/cyanneko/HuaweiHackathon/tree/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset)，只在独立附表出现，不进入主分母。input_refs.json逐例绑定原输入SHA、archive SHA和版本；gzip解压后原输入路径由生产manifest指定，raw正文未上传。所有eval已曝光，不准用于拟合；最终R81源与参数不变，无新编译或策略运行。
