liunianwww：Hash Join调度训练与开发评测数据（0.1.0）

新增数据，不替换其他成员输入。datasets/cyanneko的80份输入、原始元数据和eval/VERSION均保留原字节。

train：600份本地训练输入（580种规范化操作流），参与首轮与第二轮神经网络训练。
eval：528份开发评测输入（524种规范化操作流）：150份历史调参验证 + 378份冻结模型后生成的测试。
这378份已在此前实验中评分；本次公开后不再是未来未见数据。所有数据均有历史开发/测试暴露。
同一操作流的不同成本配置允许留在同一split；train/eval之间以及与旧成员的相反split之间无操作流重叠。

本目录输入共104354512字节，最大单文件1262748字节，最大N=58311。
数值范围、每算子一次SWITCH、阶段顺序、声明计数、key%P映射、单分区<=M及升序算子头均检查。
逐文件meta.json的可核对统计再经独立审计器验证；manifest.json含输入、元数据和操作流哈希。
大小偏斜统计：1094例全局正分区大小比>=2，34例标为near_uniform_diagnostic。
比值2只是本项目诊断标签阈值，不是题面官方界限；均衡诊断不宣称满足定性偏斜要求或代表隐藏分布。
500万操作等大型历史诊断输入未加入本次普通Git数据包；仍保留本地，不混入此次评测集合。

校验（仓库根目录）：
  python evaluation/scripts/audit_datasets.py --root datasets/liunianwww --out results/liunianwww-audit.json

合并后正式开发评测仅用eval，共568例：旧cyanneko 40例 + 本目录528例。
train总计640例不进入正式eval成绩；如评估train，必须另标开发诊断。
当前公共runner默认自动发现所有非空eval，完整评测不传--members：
  python evaluation/evaluate.py --datasets-root datasets --repeats 3 --out results/merged.json --command <solver> "{input}"

合并成绩使用同一公共评测器、同一suite_id、相同公开2026-10-26引擎计时。
原始总Score为逐案例重复算术均值之和；相对官方Naive下降%=100*(1-候选总Score/基线总Score)。
这不是官方隐藏测试成绩，也不是几何均值口径；近均匀诊断会另列子集结果。
源码与模型见source/liunianwww分支的design/，本分支不引入算法、截图或历史大日志。
