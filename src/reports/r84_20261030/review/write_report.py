from pathlib import Path
import json,hashlib,csv
ROOT=Path(__file__).resolve().parents[2];RUN=ROOT/'tmp/r84_full_eval_v2';OUT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s={k:read(RUN/k/'finalized_summary.json') for k in ['dyna','final']}
combined=read(RUN/'combined_dataset_equal.json');assert combined['complete'] and all(x['complete'] for x in s.values())
methods=read(RUN/'dyna/selection.json')['methods'];names=[m['name'] for m in methods]
labels=dict(zip(names,['Naive','R75 原版','R79 自适应共享','R80 共享概率','R80 双方案','R81 快算子/慢分区','Van paired100']))
groups={k:{m['method']:m for m in v['groups']['all']} for k,v in s.items()}
H='R80_next_hier_fast100';P='R80_paired_hier_fast100';F='R81_op256_cond2048';V='Van_latest';R75='R75_dense_switch'
lines=['# R84：含 Van 的原 dyna 与 final 全量对比','',
'日期：2026-10-30。原dyna全部12例与final v2.1.0全部72个eval用例，七方法共588格全部通过；没有抽样、删例或策略重跑。输入和代码身份在计时前固定，全部使用同一官方框架。','',
'## 结论','',
'本轮预先指定的两个数据集等权均分，R81最高，为4.084522；R80共享概率4.008007，R80双方案4.003133，Van当前推荐版3.766640，R75原版3.606490。R81相对R75提高0.478032分，相对Van提高0.317881分。','',
'这不等于R81在final全面领先：final的截断均分仅比R80共享概率高0.003918，未截断平均收益反而低0.042023，逐例成本对R80为28胜44负，最坏退化27.043%。因此R81是本轮整体均分最高的实验候选；R80共享概率在final平均原始成本和最坏成本上仍更稳。默认R75未自动替换。','',
'本次全量结果还修正了对R80双方案的判断：它在dyna优于共享概率，但final均分低0.083679、成本对共享概率为19胜53负，最坏增加52.774%。不能从R83小型新增IID面板获益，推断它普遍适用于IID；两个数据范围分别保留。','',
'## 评分、范围和版本','',
'每例成本 C = 模拟IO时间 + 该输入真实罚值×miss + 实测累计调度时间D。同轮Naive作基线B，采用冻结case-mean-v1：clip(10×(1−C/B),0,10)，非正C/B按评测器记0。本轮分母都有效。另列不做逐例零截断的raw分数10×(1−C/B)，保留负收益。没有对总分做50分截断。每套数据先各自求逐例均分，再按dyna 50%、final 50%相加；没有将84个数据点直接等权，也不是全成员仓库排行榜或官方隐藏集成绩预测。','',
'数据固定到datasets分支提交`d144cdd1c3b78f9a73702b4facb382e6a3e31212`；原缓存提交为`01e9de234cc735bc442f020c8b1b503d961543db`，已核两选定目录Git tree完全一致。dyna tree `808ce8b11f57a1a96051f22aa572eceb82b1fba0`；final tree `41197783dd577dfccf5b007a6ece67cbfb241e4b`。完整输入SHA和头部校验在计时前全部通过，运行前后再次核输入身份。','',
'| 数据集 | 全量范围 | 总操作数（每个方法） | 原始输入字节 |','|---|---|---:|---:|',
'| dyna 1.0.0 | 12例，各500万；原train6/dev3/holdout3全部保留 | 60,000,000 | 1,170,613,062 |',
'| final 2.1.0 | 全eval72；hotspot28/Zipf28/lognormal16 | 22,528,629 | 474,874,705 |','',
'这些数据已有开发观察，标为完整回归，不称未见盲测。final训练集、inde_dataset和其他成员套件未混入。具体输入顺序与所有SHA见两窗口selection.json。','',
'环境为i7-14700HX、WSL2/Ubuntu，当前g++11.4.0；使用已核实的C++14/O2固定ELF，CPU串行、单次测量，轮换每个用例的七方法顺序。D是官方框架测出的每例累计调度时间，不是单次决策时间。每格官方墙钟限60秒；内部控制预算dyna900秒/final600秒，实际窗口用时620.262305秒/278.550807秒。单次D测量不支持细小速度差异的统计显著性判断，模拟IO也不等于真实磁盘端到端耗时。','',
'Van版本来自最新核实的`source/Vanius0525`提交`d92ceb0262b556eb57aae61127d062174ffe6016`，推荐入口是[src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/d92ceb0262b556eb57aae61127d062174ffe6016/src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp)。Round10记录没有晋升新候选；根目录历史CURRENT入口不是本次选择依据。推荐类与旧参考字节相同，源码、官方框架TU、ELF和原成功编译命令逐项核验后复用，没有改Van行为或假称重新编译。','',
'## 全量均分','',
'| 方法 | dyna12均分 | final72均分 | 两数据集等权 | 等权raw分数 |','|---|---:|---:|---:|---:|']
for m in combined['methods']:lines.append(f"| {labels[m['method']]} | {m['dyna_mean_score']:.6f} | {m['final_mean_score']:.6f} | {m['equal_dataset_mean_score']:.6f} | {m['equal_dataset_raw_points']:.6f} |")
lines+=['','## 中位数、P90和最差','',
'以下均为逐例 C方法/C同轮Naive，越小越好。最近秩P50/P90：12例取第6/11项，72例取第36/65项；不把两数据集的分位数平均。','']
for k,title in [('dyna','dyna 全12例'),('final','final 全72例')]:
    lines+=['### '+title,'','| 方法 | 平均倍率 | P50 | P90 | 最差倍率 | 差于Naive例数 |','|---|---:|---:|---:|---:|---:|']
    for name in names:
        m=groups[k][name];r=m['ratio_to_Naive']
        lines.append(f"| {labels[name]} | {r['mean']:.6f} | {r['p50']:.6f} | {r['p90']:.6f} | {r['worst']:.6f} | {m['negative_improvement_cases']}/{m['cases']} |")
    lines.append('')
lines+=['## 决策耗时','',
'表中为每例累计D再取数据集平均，单位毫秒；dyna每例操作数相同，final每例操作数不同。所有D已计入前面的分数。','',
'| 方法 | dyna平均D(ms/例) | final平均D(ms/例) | 84例累计D(s) |','|---|---:|---:|---:|']
for m in combined['methods']:lines.append(f"| {labels[m['method']]} | {m['dyna_D_mean_us']/1000:.3f} | {m['final_D_mean_us']/1000:.3f} | {m['actual_D_total_us']/1e6:.3f} |")
lines+=['','R80共享概率在本轮final的平均D为25.207ms，双方案为50.310ms，约两倍；R81为27.346ms，Van为38.003ms。数据集间D不能直接解释为单次决策快慢，但同一用例上的方法对照已经体现在逐例记录中。','',
'## 不能被截断分数隐藏的回归','',
'`eval_059_random_zipf`：R81和R80共享概率的单例分数均为0，但R81实际成本/R80为1.270431，物理IO+罚值成本比为1.269680，说明主要退步并非D噪声。R81的未截断分约−4.222994，R80约−1.195408。此前1.25尾部门槛仍未通过，不能称无风险替代。','',
'全final中，R80共享概率有5例成本差于Naive，最差1.403433倍；R81也是5例，最差1.422299倍；双方案7例，最差1.710363倍；Van8例，最差1.927874倍；R75有11例，最差2.852538倍。R81的P90优于共享概率，和它有更坏的个别尾点并不矛盾。','',
'### 对 R75 和 Van 的逐例对照','',
'胜/平/负按总成本更低/相同/更高统计，不是比较被零截断后的分数。','',
'| 数据集 | 方法 | 对R75胜/平/负 | 对Van胜/平/负 | 对R80共享胜/平/负 |','|---|---|---:|---:|---:|']
for k in ['dyna','final']:
    for name in names[1:]:
        refs=groups[k][name]['references'];counts=[]
        for ref in [R75,V,H]:
            x=refs[ref]['cost_ratio'];counts.append(f"{x['wins']}/{x['ties']}/{x['losses']}")
        lines.append('| '+k+' | '+labels[name]+' | '+' | '.join(counts)+' |')
lines+=['','## 全部单例分数','',
'Naive每例相对自己为0。下表列出所有84例，其完整IO、miss、D、成本、raw收益与各参考倍率保存在逐例CSV/JSON，不以均分替代单例。','']
for k in ['dyna','final']:
    selection=read(RUN/k/'selection.json');index={(r['case_id'],r['method']):r for r in s[k]['per_case']}
    lines+=['### '+k,'','| 用例 | '+' | '.join(labels[n] for n in names[1:])+' |','|---|'+'---:|'*(len(names)-1)]
    wide=[]
    for c in selection['cases']:
        cid=c['case_id'];values=[index[cid,n]['score'] for n in names[1:]]
        lines.append('| '+cid+' | '+' | '.join(f'{v:.6f}' for v in values)+' |')
        wide.append(dict(case_id=cid,original_split=c['original_split'],**{n:index[cid,n]['score'] for n in names}))
    with (OUT/(k+'_all_case_scores.csv')).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(wide[0]));writer.writeheader();writer.writerows(wide)
    lines.append('')
lines+=['## 复核、协议修复和复现','',
'Root独立重读588份stdout，核对1176份stdout/stderr指纹、hit+miss计数、成本公式和均分，通过。证据在`tmp/r84_full_eval_v2/root_review/dyna/`与`root_review/final/`，每个目录含逐例CSV、分组CSV和review.json；独立审查器为冻结的`tmp/root_full_eval_review.py`。另一位协作agent的独立审查完成后以`tmp/r84_review/result_review.json`补充归档。','',
'v1准备阶段因Windows依赖路径反斜杠与Linux正斜杠差异被拦截，当时没有正式selection/campaign或策略运行。v1全部保留；v2只将依赖键规范化为POSIX并严格拒绝键碰撞，真实文件SHA或参数变化仍会失败。跨平台正例、真实改字节/改SHA/改参数负例均通过，所有84个输入及七个方法未变。v2同时核实新远端提交的两数据目录tree与原缓存相同。此修复不影响策略行为，不能算作策略失败后重跑。','',
'完整复现命令、CPU窗口约定和单例超时见`tmp/r84_full_eval_v2/README.md`；正式输出仅来自v2。以`finalized_summary.json`及`completion_gate.json`为完整性判定，保留原core的summary/completion，防止最后一格后的控制器错误被错误当成成功。本轮两窗口均终止正常、没有身份变化。','',
'| 方法 | 被测源码SHA256 |','|---|---|']
for m in methods:lines.append(f"| {labels[m['name']]} | `{m['source_sha256']}` |")
lines+=['','完整源码/TU/ELF身份及Van归属见`tmp/r84_full_eval_v2/methods.prepared.json`与每个selection；R75等既有方法的归档提交由发布manifest映射，不能用移动分支头代替被测版本。','',
'| 关键证据 | SHA256 |','|---|---|']
for p in [RUN/'release.json',RUN/'methods.prepared.json',RUN/'dyna/selection.json',RUN/'dyna/rows.json',RUN/'final/selection.json',RUN/'final/rows.json',RUN/'combined_dataset_equal.json',RUN/'root_review/dyna/review.json',RUN/'root_review/final/review.json']:
    lines.append(f'| `{p.relative_to(ROOT).as_posix()}` | `{sha(p)}` |')
lines+=['','## 后续目标与发布','',
'优先研究如何保留R81在dyna的改进，同时减轻final的原始成本和个别尾点；R80共享概率保留作稳定对照。R80双方案的用途需按完整证据重新评估，不能直接用“IID就选双方案”的规则。后续修改仍先用独立训练/开发数据验证，再完整跑原dyna12与final全部eval；避免只围绕已见失败点调参。','',
'本轮协议、全部逐例结果、对应代码/数据版本、原始日志、失败准备记录和审查都交Master同步到用户`source/cyanneko`分支，并纳入统一评测索引。发布后在独立publication manifest映射Git固定提交，不修改冻结结果。本文不提前声称远端发布已完成。']
target=ROOT/'docs/20261030_R84含Van全量评测报告.md';assert not target.exists();target.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(str(target));print(sha(target))
