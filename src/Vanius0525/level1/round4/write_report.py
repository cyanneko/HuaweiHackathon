"""Readable stage2 frozen-slate results, preserving unfinished checks explicitly."""
from pathlib import Path
import json,statistics,hashlib,datetime
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'round4'
members={m:json.loads((ROOT/'results'/('round4-stage2-member-'+m+'.json')).read_text()) for m in ['Vanius0525','cyanneko','liunianwww']}
names=list(next(iter(members.values()))['scheduler_sha256']);rows=[];compact={}
for n in names:
 scores=[r['summary'][n]['mean_single_score'] for r in members.values()];worst=0.;zero=0
 for member,r in members.items():
  for c in r['cases']:
   cost=lambda a:statistics.mean(v['Total_IO_Time']+c['penalty']*v['Miss_Count'] for v in c['runs'][a])
   v,b=cost(n),cost('naive')
   if b:worst=max(worst,v/b)
   elif v:zero+=1
 compact[n]={'member_scores':dict(zip(members,scores)),'equal_member_mean':statistics.mean(scores),'worst_io_miss_ratio':worst,'positive_cost_against_zero_io_base':zero,'sha256':next(iter(members.values()))['scheduler_sha256'][n]}
 source='MySpillScheduler.cpp' if n=='pure' else 'MySpillSchedulerAI.cpp' if n=='ai' else 'round4/'+n+'.cpp';link='../'+Path(source).name if n in ['pure','ai'] else n+'.cpp'
 rows.append('| ['+n+']('+link+') | '+' | '.join(f'{v:.6f}' for v in scores)+f' | {statistics.mean(scores):.6f} | {worst:.3f} |')
text='''# Level1 持续优化：2026-10-30

保留纯算法与AI两方向、多种风险取舍及全部负结果。两个根目录冻结候选保持原字节；本目录是独立实验候选，每次只提交一个定义`MySpillScheduler`的C++14文件。训练教师、数据生成器及脚本不是提交物。

## 当前同批完整结果

固定三成员785条合法eval、11候选、每例5重复，8635次候选独立动作重放通过。每次重复先计算相对Naive的截断分，再平均重复和成员内案例，最后三成员等权平均，满分10；I/O、Miss罚与CPU均进入总分。保留所有案例，不采用旧50分cap或80:20混合权重。

| 候选 | 本人209 | cyanneko48 | liunianwww528 | 三成员等权 | 最坏I/O+Miss/Naive |
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'''

最坏列只比较Naive I/O+Miss为正的例，避免微秒CPU比例噪声；零I/O正成本例另记机器报告。该列不是总成本保证，也不包含未测场景。按候选结果筛掉的案例数为0。

- `all_probe`偏保守：只有所有算子都在PROBE阶段才启用集合优化；`io_asymmetry`也在读带宽不低于写带宽时启用，均分较高但尾部更差。
- `ai_set025_routecount`使用内嵌网络重排小候选，再枚举固定小集合；AI预取2048放宽一次真实next_op的传输预算，是显式风险先验，不读不可见罚值，不保证长期regret。
- context树每次比较多组假想动作，CPU明显更多。72367事件的首步周期回调边界对照标签变化0，已排除该疑点对当前结果的影响。原summary过滤丢掉9309组不同Action身份的候选，精确Action过滤消融继续验证。
- 同一Naive二进制独立重复，在36个零I/O用例上也可产生约0.79的正向截断均分。没有从正式成绩机械扣除该值，完整保留所有微秒例及重复；小分差不等于稳健收益。

## 新验证与机制证据

阶段2先冻结源码SHA，再生成fresh2的64条新种子和challenge的64条新生成规律；每套11候选、5重复、逐例审核。challenge含循环破坏、渐变热点、大小/热度翻转、扫描切换、混合phase、bridge、强读写不对称和空分区等轴，不声称代表正式分布。设计受已曝光问题启发，不能称完全不受反馈的confirmatory test。

新challenge均分：纯IOasym1.873141、AI预取1.834631、AI集合1.812337，原pure1.594315/AI1.711069；两context约1.72–1.73。训练策略没有稳定领先。所有入围者都报告，不只保留冠军。

10万请求机制面板：B1的scan_hot，纯有限预取256使Miss77091→0、总成本93.605M→16.441M us；uniform86819→1、105.396M→18.525M。B31收益显著缩小，低罚可能不划算。新联合LOAD版本利用Miss回调的一条真实next_op，把两对象同时纳入分配，仍可能丢失下一次Miss的额外lookahead；开发及新分布对照单列。

精确小例只改变接口不可见的Miss罚值，操作流、首次状态和next_op完全相同，最优首次驱逐相反；证明存在实例级信息边界，不代表benchmark有错，也不声称策略达到界或研究新颖。见[PENALTY_INFORMATION_BOUNDARY.json](PENALTY_INFORMATION_BOUNDARY.json)。

## 证据与复现入口

- [HANDOFF.md](HANDOFF.md)：完整阶段日志、失败尝试、当前队列及下一动作；[RESEARCH_UPDATE.md](RESEARCH_UPDATE.md)：原论文来源、结论和本题适用边界。
- [STAGE2_EXTERNAL_FREEZE.json](STAGE2_EXTERNAL_FREEZE.json)：先于新输入的源码清单；[PHASE_RESULTS.json](PHASE_RESULTS.json)：阶段限制完整三成员及corner敏感性；`STAGE2_RESULTS.json`是本批完整分析（若尚未生成，脚本正排队，不冒称已完成）。
- [VERSION_LEDGER.json](VERSION_LEDGER.json)：每份源码/已测SHA、原始报告SHA和状态；原始输入、完整动作及重复结果保留在本地忽略的`build/`与`results/`，不上传大日志或私有会话信息。
- `run_stage2_external.py`、`run_stage2_members.py`复现本批，但重跑会改变测量；已有进程运行时不要重复启动。`summarize_stage2.py`和`plot_stage2.py`只基于已有报告分析；corner重加权仅作敏感性诊断，不替换当前计分。
- `fuzz_stage2.py`、`fuzz_miss_lookahead.py`做ASan/UBSan抽象回调安全测试。`stress_campaign.py`及`run_stage2_maximum.py`保存最大N增量结果，只有state=complete才算整矩阵完成；未完成数据不能冒充最终压力结论。

小时续接已恢复为`../hourly_resume.py`，当前要求至少持续到北京时间07:00；不是云端Scheduled，依赖本地宿主与Codex服务。最近状态以[../HANDOFF.md](../HANDOFF.md)及本目录交接为准。
'''
(OUT/'README.md').write_text(text);(OUT/'STAGE2_CANDIDATES.json').write_text(json.dumps({'scores':compact,'scope':'same-batch fixed exposed synthetic suites; no promotion; frozen roots preserved'},indent=2)+'\n');print(json.dumps({'candidates':len(compact),'max_ratio':max(d['worst_io_miss_ratio'] for d in compact.values())}),flush=True)
