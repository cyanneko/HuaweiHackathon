# 最终算法：R81

用户于2026-10-31最终选定 **R81_op256_cond2048**，停止继续优化。提交文件是[MySpillScheduler.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/a1ee48aee1af3b561efa2eacc5c68769a9a0dc83/submission/MySpillScheduler.cpp)，[身份清单](https://github.com/cyanneko/HuaweiHackathon/blob/a1ee48aee1af3b561efa2eacc5c68769a9a0dc83/submission/manifest.json)与[精简验证记录](https://github.com/cyanneko/HuaweiHackathon/blob/a1ee48aee1af3b561efa2eacc5c68769a9a0dc83/submission/verification.json)一并提供。

本次只整理排版和模块注释：6659词法token、296115官方翻译单元预处理token均与原版相同；官方前后缀原字节未改；两个C++14/O2构建的ELF与.text逐字节相同。没有新benchmark、调参或训练。

| 身份 | SHA256 |
| --- | --- |
| 当前易读提交源 | `ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65` |
| 历史实测R81源 | `7f65114b43dba6d5e3b5744fbee17a0b0f5b97a0d9b1b02702e3da6c8b0fb764` |
| 编译ELF（与已测版本相同） | `bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1` |

代码只含MySpillScheduler和必要助手/标准库，无main或引擎。按原赛题框架仅替换调度器，使用纯CPU、`g++ -std=c++14 -O2`，不修改官方框架或在线可见信息。历史源码、原始性能结果与旧默认R75记录均保留；最终选择来自用户决定，不宣称消除历史尾部退化。R87未采用，后续提案不执行。

主数据仍为[dyna1.0全12＋final2.1全72](EVALUATION_DATA_VERSIONS_20261030.md)，新3.0只保留为补充。现有已完成成果可归档；没有新的用户明确授权，不恢复算法优化、调参、训练或性能实验。
