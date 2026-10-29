实测状态更新（2026-10-30）：源码已通过静态交叉审查、6个手算+24个随机Fraction直接枚举核对、全部785例输入及SDK成本核对。185可计算、600明确跳过、无错误。
证据：toy_verification.json、suite_verification.json、bound_comparison_members_r6_mode92.json；模型与数据身份分别绑定，不推广到其余600。
原始源码和下面初始说明保留生成阶段的pending字样；后续验证状态以本段及冻结结果为准，未改源代码来更新状态注释。
官方会忽略size=0的SPILL，所以final-empty分区始终resident。全轨迹扩展讨论中的空分区miss反例不成立，未改变已验证算法。

离线后缀下界工具（尚未编译或运行，待审查和独立验证）

用途与隔离
  offline_suffix_bound.cpp是独立离线分析程序，含main，不是MySpillScheduler提交物。
  允许读取全部输入、真实miss_penalty及B；这些信息绝不能进入在线调度器或模型特征。
  当前仅交付源码供root审查；需要独立toy、暴力DP与公开SDK比对后才能作为证据使用。

预期构建/调用（本次未执行）
  g++ -std=c++14 -O2 design/offline_bounds_20261030/offline_suffix_bound.cpp -o offline_suffix_bound
  ./offline_suffix_bound <正式输入文件路径>
  仅接受一个输入文件参数，向stdout输出一行JSON。

松弛与数学含义
  边界取最后一个SWITCH之后，此后只有PROBE。Q为最终非空分区数，A为其总大小。
  状态S只记录非空驻留分区，sum(S)<=M。空分区一律视作可免费保留的hit。
  任意实际边界S的prefix累计写出字节至少为A-size(S)；prefix读取、miss和全部决策CPU均忽略。
  后缀知道完整未来，periodic按全局INSERT+PROBE累计计数，不含SWITCH。
  periodicprefix是边界处累计INSERT+PROBE数；另给其mod B及前后periodic回调数。
  空分区PROBE不从后缀删除：它们仍推进计数，并可能触发periodic。

DP（下式为实数精确模型）
  terminal V(S)=0，对不可行S为inf。
  transfer(S,T)=sum(S\T)/W + sum(T\S)/R；先SPILL再LOAD可实现。
  每步先考虑该PROBE之后的periodic：触发时W(S)=min可行T[transfer(S,T)+Vnext(T)]，否则W=Vnext。
  当前目标在S或目标为空时F(S)=W(S)。
  当前目标非空且不在S时F(S)=p+min可行T含目标[transfer(S,T)+W(T)]。
  miss中可先载入其他新增分区，再最后LOAD当前目标；全程容量不会超过最终可行T。
  最终LB=min可行S[(A-size(S))/W+F_suffix(S)]。
  无后缀时仍枚举S计算prefix写出下界，不把结果直接设为0。
  这是允许任意可行边界S的全case松弛下界，不是全case最优Score，也不是一个实际在线方案。

有向Hamming min-plus变换
  逐位同时更新old0/old1：new0=min(old0,old1+s/R)，new1=min(old1,old0+s/W)。
  输入向量先把不可行目的状态T置inf；miss还需将不含当前目标的T置inf。
  变换内部不得再按容量裁剪；中间向量不是实际驻留状态。
  最终F只保留可行源状态S。每次变换O(Q*2^Q)。

资源预算
  Q<=16；超过则status=skipped且lower_bound=null，绝不伪称0界。
  保守工作估计estimated_work=2*原始N*Q*2^Q，上限2e8；另输出实际后缀长度对应估计。
  无后缀时只做状态枚举，DP估计为0，不因无用prefix长度跳过；Q=0也直接处理唯一零状态。
  预算检查不包含读入输入时间。读取时仅保留最后SWITCH之后的目标序列，无需保存全部操作。

浮点边界与结果解读
  使用long double，输出raw_relaxation_value和经下调的lower_bound。
  下调量=0.02us + 1e-12*max(1,raw) + 128*epsilon*(suffixlen+1)*(Q+1)*max(1,raw)。
  下调是保守数值余量启发式，未使用区间运算/有向舍入，不是machine-certified证明。
  exact_in_real_arithmetic=true仅指该递推在实数模型下精确求解这个松弛；不是机器结果认证。
  skipped时exact_in_real_arithmetic也为null。输入非法则status=error并返回非零退出码。
  若以后与SDK Score C比较，C-LB只是“最多改善空间的上界”，不能称“还可达到的收益”。
  当前没有任何测得结果；不得将本工具源码存在等同于下界已验证。
