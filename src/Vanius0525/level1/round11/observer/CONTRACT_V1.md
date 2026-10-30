# 固定两流R80 observer合同 V1

2026-10-30。root授权实现并要求运行前检查。数据固定已发布24 Zipf原顺序前两条：train548、train593；来源、原R80源码、Round10原成功输出、脚本和插桩源码SHA在运行前冻结。可复用root `MECHANISM_NOTES_V1.md`，不重复广泛调研。AI暂停；每输入仪器化版本至多执行一次，0新增普通性能运行/teacher/dev/eval/dyna/参数网格。先交root审阅diff和冻结清单，之后才执行。

## 固定观察位置

全局合法时钟q=hit_count+miss_count。只在overflow或需求Miss且required > memory_limit-memory_used时，记录达到256、1024、4096之后的首个压力回调。多个阈值若落同一回调合并thresholds数组，每流至多3个唯一状态；不按预测/动作差或成本选位置，不强求未达到阈值。periodic callback仍原样执行但不选择快照。记录合法state、next、当前目标、回调序号与实际prune后SPILL及完整返回动作；不注入N/B/实际罚值/未来操作到调度器。

## 插桩隔离与共同状态硬核验

原R80正文只改类名并在类末新增observer专用方法；原update/release/propose/prune/record/callback字节保持。外层MySpillScheduler在选中回调之前复制整个参考实例，然后调用真实原callback，最后在该副本上生成日志。所有vector/标量状态按值复制，无原实例引用；补算未访问p缓存只发生在副本。原静态衰减表为不可变常量表，不改变逻辑概率/历史。

副本按原callback相同的active/update步骤吸收本回调信息，再产生三个独立副本：hier副本以原frequency_mode=2调用propose+prune；flat副本仅frequency_mode=1；view副本完整计算所有flat/hier p和share。两个proposal副本各自从同一pre-proposal状态开始，重置probability_cache_valid_与原release一致；一个副本不得污染另一个。**hier副本的prune后SPILL序列必须与真实返回动作中的SPILL序列完全一致**，包括顺序，否则记错误并停止。实际callback仍只有原release/prune/record路径；副本动作不执行，view补算不回写真实实例。

日志保存频率分支、scan/cycle标记、next保护对象、所有对象大小/驻留/eligible及flat/hier p、算子share/质量/平方质量/有效量。保存两套SPILL与实际动作。对flat/hier两集合分别交叉计算flat/hier未来费用代理、.25写项目标及实际当前写费；仅在普通PROBE频率分支时将其称对应subset目标。保留next的1e12保护项；不把100/s漏掉，不声称仅概率排序决定动作。K=1的仿射恒等式单独核验。

## 执行与审核

全部构建/运行/离线重算持共享experiment_lock。只构建一个观察版本，不运行额外未插桩参考；输出日志到stderr，stdout沿用官方框架五指标。每流完成后IO、Hit、Miss与Round10冻结R80原记录逐值精确相同；日志耗时不当正式性能。若不同、超时或任何异常，保留原输出并停止，不自动重试。

独立Python审核最多6条快照的概率/算子质量恒等式、层级保留的算子总质量、K=1仿射式、eligibility、实际/反事实集合合法释放量、hier复制动作相等与四种交叉估值。快照中没有实际全流动作TRACE，因此不宣称全流动作完全一致；物理/计数一致也不是其证明。不得把局部反事实动作当成完整轨迹收益、最优动作或teacher标签。

输出路径均为仓库相对路径。混合CRLF源码/patch用局部.gitattributes保留原字节；私人LAUNCH留本地，不发布。结束后更新本目录HANDOFF并交root复核发布；后续动作需单独合同，不在本轮追随结果加阈值或候选。
