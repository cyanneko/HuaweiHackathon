# cyanneko 的算法源码

在本分支下的 `src/` 放置你的算法代码，后续可添加构建配置、模型和方法说明。

最终提交须整理为纯 CPU、单个 `.cpp`、C++14 标准库程序，模型权重内嵌源码；不依赖 CUDA、第三方推理运行时或外部模型文件。GPU 仅用于离线训练。统一构建基线为 `g++ -std=c++14 -O2`，不假定 `-march=native` 或 AVX 可用。详见 [提交与部署基线](../evaluation/README.md#提交与部署基线)。

当前仅初始化目录，未迁入原有实验代码或训练结果。

评测程序默认需输出新版五项指标：`Total_IO_Time`、`Total_Decision_Time`、`Hit_Count`、`Miss_Count`、`Total_Score`。决策时间应由与官方规则一致的执行框架测量，不能以 0 补齐。完整协议见 [评测说明](../evaluation/README.md)。

共同数据在 `datasets` 分支。可以使用单独的工作目录存放该分支，然后给评测入口传入 `--datasets-root` 绝对路径，以免把数据混入本源码分支。
