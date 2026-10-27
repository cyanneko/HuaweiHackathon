# cyanneko 的算法源码

先读 [Agent 上手指南](../docs/AGENT_GUIDE.md#参赛提交物与本地可测程序)，区分参赛类文件与本地完整可执行程序。

在本分支下的 `src/` 放置你的算法代码，后续可添加构建配置、模型和方法说明。

正式参赛仅提交定义 MySpillScheduler 的单个 `.cpp`，无 main/engine；本地测试另接官方兼容完整框架。两者均以纯 CPU、C++14 标准库为基线，模型权重内嵌源码；不依赖 CUDA、第三方推理运行时或外部模型文件。GPU 仅用于离线训练。统一构建基线为 `g++ -std=c++14 -O2`，不假定 `-march=native` 或 AVX 可用。详见 [提交与部署基线](../evaluation/README.md#提交与部署基线)。

已上传 [R49 的三种规则方法和一个基线](methods/r49/README.md)，原始字节与封存证据一致。这些文件仅定义 `MySpillScheduler`，需要接入官方 2026-10-26 执行框架；没有 `main`，不能单独编译成可执行程序。当前未上传历史模型或训练结果。

另补充 [R53 best_fit_fast 候选](methods/r53/README.md)：优化 best-fit 的实现路径，保留原版作对照，未设为默认策略。结果只覆盖六个已见开发输入，具体改善与退化边界见该目录说明。

评测程序默认需输出新版五项指标：`Total_IO_Time`、`Total_Decision_Time`、`Hit_Count`、`Miss_Count`、`Total_Score`。决策时间应由与官方规则一致的执行框架测量，不能以 0 补齐。完整协议见 [评测说明](../evaluation/README.md)。

共同数据在 `datasets` 分支。可以使用单独的工作目录存放该分支，然后给评测入口传入 `--datasets-root` 绝对路径，以免把数据混入本源码分支。
