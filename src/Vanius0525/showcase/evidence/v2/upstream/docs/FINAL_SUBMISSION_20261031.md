# 最终算法：R81

用户最终选定 **R81_op256_cond2048**。当前[MySpillScheduler.cpp](../submission/MySpillScheduler.cpp)仅做排版、注释与五个宏的含义命名整理，未改变参数或算法。[身份清单](../submission/manifest.json) · [等价验证](../submission/verification.json)。

| 宏名称 | 固定值 |
| --- | ---: |
| HASHJOIN_OPERATOR_HALF_LIFE | 256 |
| HASHJOIN_REUSE_ESTIMATOR | 2 |
| HASHJOIN_ADAPTIVE_RISK_SHARING | 1 |
| HASHJOIN_REFAULT_MODEL | 3 |
| HASHJOIN_SIZE_BIAS | 0 |

按允许的五名映射归一化后6659词法token相同；官方翻译单元296115预处理token相同，官方前后缀未改，C++14/O2构建的ELF与.text逐字节相同。没有新benchmark、调参或训练。命名整理不称为算法优化。

| 身份 | SHA256 |
| --- | --- |
| 当前宏含义命名源 | `2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617` |
| 上次易读源 | `ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65` |
| 历史实测源 | `7f65114b43dba6d5e3b5744fbee17a0b0f5b97a0d9b1b02702e3da6c8b0fb764` |
| 相同实测ELF | `bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1` |

只提交调度器类，不含main或引擎；在原官方声明后放置代码，只替换MySpillScheduler，纯CPU、`g++ -std=c++14 -O2`，不修改框架或在线可见信息。原版与历史结果永久保留；用户选择不等于消除历史尾部退化，R87未采用。另获授权的创新说明消融与最终源码分离，不用于调参或重新择优。

主数据仍为[dyna1.0全12＋final2.1全72](EVALUATION_DATA_VERSIONS_20261030.md)；新3.0和stat属于独立补充，不改变最终R81选择。没有新的用户明确授权，不恢复算法优化或新性能实验。
