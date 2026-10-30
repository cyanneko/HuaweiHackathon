# R84 七方法冻结类

每个cpp单独定义MySpillScheduler，无main。使用一个类接入对应官方框架，不可将同名类一并编译。完整测量TU在报告包measured_sources；纯CPU、标准库、g++ -std=c++14 -O2，生成可执行程序后按固定输入运行。历史ELF哈希只标识本轮测量身份，不发布缓存或要求复用本机目录。

Van_latest.cpp归Vanius0525，来自[作者最新核实推荐入口](https://github.com/cyanneko/HuaweiHackathon/blob/d92ceb0262b556eb57aae61127d062174ffe6016/src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp)，原字节未改。其余同名版本各保留冻结来源，比较不是晋升；默认R75不变。[全部结果](../../reports/r84_20261030/report_zh.md)。
