第20题关键项目文件 | source/liunianwww

当前推荐：MySpillScheduler_final.cpp。
单文件C++14，定义MySpillScheduler，无main；使用官方参考框架接入。

可选版本：
- MySpillScheduler_scan_fused.cpp：保持主版动作的扫描优化，性能收益依负载而变。
- MySpillScheduler_holistic.cpp：预算子集搜索与强制落盘集合研究组合，非默认。
- holistic_20261026/pressure.cpp：跨算子回读反馈实验，非默认。
每次只选择一个调度器，不要同时直接编译这些定义同名类的文件。

编译（需要Python 3、g++；Python仅使用标准库）：
  python design/tools/run.py --policy recommended
编译并运行已有正式格式输入：
  python design/tools/run.py --policy recommended --input /path/to/input.txt
可选policy：recommended、scan-fused、experimental、cross-feedback、baseline。
工具保持公开框架执行和计时不变，只引用选定调度器并替换实例。
编译产物写入design/build/，不会提交到仓库。

报告：topic20_holistic_iteration_report.pdf，13页中文说明。
内容含算法、七项要求落实、学术借鉴、自主贡献、局部证明、实测及退化情况。
结果摘要：results_summary.json。输入清单、完整原始结果和历史实验保留本地；
报告中的旧目录与审计命令对应本地研究档案，不保证可仅凭此精简仓库重新运行全部历史实验。
参考框架：holistic_20261026/reference_current.cpp。
来源与要求：holistic_20261026/research_sources.json、requirements_coverage.json、fetch_provenance.json。

本分支仅发布关键项目文件。原始截图、网页缓存、历史实验副本、生成输入、完整日志与预览图保留本地。
文件列表及字节SHA256记录于project_manifest.json；未改动任何算法源文件。
神经网络新增候选（2026-10-29）
  MySpillScheduler_neural.cpp：8专家、32→16→8网络、664参数。
  python design/tools/run.py --policy neural --input <输入文件>
  中文说明：topic20_neural_selector_report.pdf。
  训练、来源、指标、适用边界：neural_selector/README.txt。
  提供小型特征标签包用于复现训练；不包含原始截图与批量输入。
  已完成150例验证、378例新测试、8例GitHub回归、6例规模测试与第二轮模型评估。
