# R65 TurnoverRisk：实验单文件候选

状态：experimental_not_promoted。契约RED→最终GREEN、独立源码审查及最终单文件C++14/O2接口样例通过；[三例探索性九格结果](../../reports/r65_targeted_exploration_20261030/README.md)已完成：hot/heterogeneous成本约为Naive的0.6114/0.8311倍，growth为1.4336倍且比R63差3.279%。单次小样本，未替换默认或注册SDK专家ID。

提交形态为[MySpillScheduler.cpp](MySpillScheduler.cpp)，仅调度器及助手定义，无main/engine。官方框架先提供SystemState、Action、SpillScheduler等类型；只替换调度器类，不改引擎或计时边界。CPU、C++14/O2、标准库，无外部模型或未来输入特征。`R65_UNIT_TEST`和`R65_DIAGNOSTIC`均不得在正式构建定义。

原字节依赖是policy.hpp与dependencies/frozen_helpers.hpp。entry.cpp依次包含两者，再附`class MySpillScheduler:public R65TurnoverRisk{};`。可在仓库根运行`python expert_runtime/export.py --entry src/experiments/r65_turnover_risk/entry.cpp --out NEW.cpp`，输出必须是新文件；展开标记中的相对路径可能不同，重新导出的字节SHA应另记，策略依赖的冻结SHA不能改变。[manifest.json](manifest.json)记录本次单文件及依赖身份。

策略保留全部合法且足够释放空间的单受害者选择，以及无单个足够时的冻结BF回退。确认自身spill→miss→load周转后形成有偏热度H，按可见hit+miss时钟每64引用惰性减一，保留余量、限制H≤floor(M/bytes)，以H×bytes×(1/write_bw+1/read_bw)加入原成本代理。大小、时钟、形状和生命周期变化按审定契约失效历史。它不是完整访问频率、精确未来代价或收益保证。

完整源码审查结论和假设见[review.json](review.json)；官方有效状态/连续身份/有限正带宽是适用前提。确认延迟、同钟去重、惰性老化、容量上界、失效与回退契约见[tests/heat_contract.inc](tests/heat_contract.inc)。[unit_evidence.json](tests/unit_evidence.json)保留真实RED、最终GREEN及中间失败记录，不把修正前的单测失败当成最终策略的性能负结果。

[submission_check.json](submission_check.json)只证明单文件按官方类型定义编译、三个回调可调用以及少量接口动作/空间检查通过，不替代执行方的物理动作审核或正式性能结果。接口测试体见[tests/interface_smoke_body.inc](tests/interface_smoke_body.inc)，使用官方类型前缀并包含本单文件构建；没有随包发布框架、ELF或宿主路径。

[热流机制证据](../../reports/r65_mechanism_20261030/README.md)保留原核算器FAIL与补充有序重放PASS的区别。24例仅为回归池；当前不恢复全方法矩阵。尚未完成或失败的针对验证须按实际状态另记，不以单测、平均分或未来计划晋升默认。

[30例开发回归报告](../../reports/r65_sampled30_development_20261030/README.md)已另行完成：三成员各10，90记录含9复用+81新测，成员未封顶SUM均值R65为39.019057、R63为33.992676。原九格独立不变。R65有7/30成本回退、20/30 D回退，普通median/原nearest-rank P50分别报告；empty最差倍率只来自1.44/0.68微秒的单次D，Int64和growth实际退化保留。仍experimental、不作全785或稳定D优势结论。
