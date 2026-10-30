# R74 回访＋算子热度实验候选

优先试用[MySpillScheduler.cpp](MySpillScheduler.cpp)：与冻结fast operator.policy.cpp原字节相同，只含调度器和助手/标准库定义，无main或engine。接入官方兼容类型与引擎，C++14/O2、纯CPU、标准库；未覆盖任何现有默认提交。

[完整证据和限制](../../reports/r73_r74_20261030/report_zh.md)。原1us罚值代理保留；回访等待曝光、算子池化先验与分区信号融合，LUT只缓存相同衰减计算，首次初始化计入回调D。六个开发输入的slow成本改善与fast同轮D改善是两个独立比较，不能直接拼成其他数据上的承诺。

alternatives保留fast coverage；slow保留partition/operator/coverage/size四个消融。size有约1.994倍诊断退化，不推荐默认；fast coverage跨轮存在D反增例，所有失败均在报告中。源码生成、完整翻译单元和测试位于报告包的slow_source/fast_source，冻结源码不重写。
