"""Build the R85 report once, only after complete runs and independent Root audits."""
from pathlib import Path
import hashlib,json,csv
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
RUN=ROOT/'tmp/r85_full_eval'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def f(x):return f'{x:.6f}'
def table(lines,headers,rows):
    lines+=['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']
    lines+=['|'+'|'.join(map(str,row))+'|' for row in rows];lines.append('')
labels={'Naive':'Naive','R75_dense_switch':'R75','R80_next_hier_fast100':'R80 hierarchy','R80_paired_hier_fast100':'R80 paired','R81_op256_cond2048':'R81 op256','Van_latest':'Van paired100','R85_fast_prior8':'A：fast prior8','R85_hier_anchor':'B：hier anchor'}
combo=read(RUN/'combined_dataset_equal.json');assert combo['complete']
summaries={};selections={};completions={}
for mode in ['dyna','final']:
    folder=RUN/mode;s=read(folder/'finalized_summary.json');g=read(folder/'completion_gate.json');review=read(RUN/'root_review'/mode/'review.json')
    assert s['complete'] and g['status']=='PASS' and review['status']=='PASS'
    assert g['finalized_summary_sha256']==review['finalized_summary_sha256']==sha(folder/'finalized_summary.json')
    assert review['rows_sha256']==sha(folder/'rows.json') and review['gate_sha256']==sha(folder/'completion_gate.json')
    summaries[mode]=s;selections[mode]=read(folder/'selection.json');completions[mode]=read(folder/'completion.json')
assert selections['dyna']['methods']==selections['final']['methods']
methods=[m['name'] for m in selections['dyna']['methods']]
ranked=sorted(combo['methods'],key=lambda m:-m['equal_dataset_mean_score'])
byname={m['method']:m for m in combo['methods']}
lines=['# R85 原数据完整回归：两项独立数学改动与 Van 对照','',
 '2026-10-30。本轮完整覆盖原 dyna 12例（每例500万步）与 final v2.1.0 全部72例。固定8方法，共672格；各阶段以同批Naive为基线。全部完成门及Root独立原始输出复算通过后才生成本报告。','',
 f"按预先约定的两个数据集均分各占50%计算，本轮均分最高为 **{labels[ranked[0]['method']]}：{f(ranked[0]['equal_dataset_mean_score'])}**。这只是已曝光回归集上的本轮排名，不是官方隐藏集或全仓库所有成员的数据排名，也不自动改变冻结提交版。",'',
 '## 方法与评分口径','',
 'A仅将R81快速算子边际的平滑总权重64改为8.009479828345365，慢分区条件仍为64；B以R80分层策略为默认，在原比较条件内评估旧启发式方案。两项没有合并，没有依据新面板分数筛选或修改。Van保留作者paired_penalty100原字节；实验联合风险池不是这一列。','',
 '`C = 模拟IO时间 + 本例评测罚值×miss次数 + 实测累计决策时间D`。每例分数为 `clip(10×(1−C/Cnaive),0,10)`；非正成本/分母按固定评测器记0。raw保留未截断负分。调度器仍只使用合法固定代理罚值100，不知道本例隐藏罚值或未来操作序列。','',
 '先分别求dyna12和final72的逐例平均分，再取两者平均；不把84个点等权混合，不将不同输入的绝对成本先求和再相除，也不施加全局50分封顶。物理成本指IO+miss罚值，排除D。单次CPU串行测量没有误差条，小D差异不可视为显著性结论；模拟IO不是实盘端到端测速。','',
 '## 本轮完整主结果','']
table(lines,['方法','dyna12均分','final72均分','两数据集等权均分','等权raw分','dyna平均D(ms)','final平均D(ms)'],[[labels[m['method']],f(m['dyna_mean_score']),f(m['final_mean_score']),f(m['equal_dataset_mean_score']),f(m['equal_dataset_raw_points']),f(m['dyna_D_mean_us']/1000),f(m['final_D_mean_us']/1000)] for m in combo['methods']])
lines+=['## 直接父版本比较','', 'A的直接父版为R81，B的直接父版为R80 hierarchy。倍率为逐例候选成本/对应父版成本，越小越好；P50/P90为最近秩，n12取第6/11项，n72取第36/65项。','']
parent_rows=[]
for mode in ['dyna','final']:
    allrows={m['method']:m for m in summaries[mode]['groups']['all']}
    for name,parent in [('R85_fast_prior8','R81_op256_cond2048'),('R85_hier_anchor','R80_next_hier_fast100')]:
        m=allrows[name];r=m['references'][parent];q=r['cost_ratio'];p=r['physical_ratio']
        parent_rows.append([mode,labels[name],f(r['mean_score_delta']),f(m['mean_raw_unclipped_points']-allrows[parent]['mean_raw_unclipped_points']),f(q['mean']),f(q['p50']),f(q['p90']),f(q['worst']),f(p['mean']),f(m['D_total_us']/allrows[parent]['D_total_us']),f"{q['wins']}/{q['ties']}/{q['losses']}"])
table(lines,['数据集','候选','均分差','raw差','平均成本比','P50','P90','最差成本比','平均物理成本比','累计D比','胜/平/负'],parent_rows)
for name,parent in [('R85_fast_prior8','R81_op256_cond2048'),('R85_hier_anchor','R80_next_hier_fast100')]:
    a,b=byname[name],byname[parent]
    lines.append(f"- {labels[name]} 对 {labels[parent]}：等权均分变化 {a['equal_dataset_mean_score']-b['equal_dataset_mean_score']:+.6f}，等权raw变化 {a['equal_dataset_raw_points']-b['equal_dataset_raw_points']:+.6f}。")
lines+=['','## 相对Naive的成本尾部','', '这是逐例成本/同例Naive的分布，不是跨数据集混合分位数。','']
table(lines,['数据集','方法','平均倍率','P50','P90','最差倍率','比Naive更差例数'],[[mode,labels[m['method']],f(m['ratio_to_Naive']['mean']),f(m['ratio_to_Naive']['p50']),f(m['ratio_to_Naive']['p90']),f(m['ratio_to_Naive']['worst']),m['ratio_to_Naive']['losses']] for mode in ['dyna','final'] for m in summaries[mode]['groups']['all']])
lines+=['## 最差父版反例及分组','', '以下反例保留原始成本倍率与raw分，避免同为零分掩盖退步。不同机制分组是观察性诊断，不能当作因果试验。','']
for mode in ['dyna','final']:
    s=summaries[mode];pp={(p['case_id'],p['method']):p for p in s['per_case']}
    for name,parent in [('R85_fast_prior8','R81_op256_cond2048'),('R85_hier_anchor','R80_next_hier_fast100')]:
        candidates=[p for p in s['per_case'] if p['method']==name];worst=max(candidates,key=lambda p:p['references'][parent]['cost_ratio']);base=pp[worst['case_id'],parent]
        lines.append(f"- {mode} {labels[name]}最差父版倍率：`{worst['case_id']}`，成本比{f(worst['references'][parent]['cost_ratio'])}、物理比{f(worst['references'][parent]['physical_ratio'])}；候选/父版clipped分{f(worst['score'])}/{f(base['score'])}，raw分{f(worst['raw_unclipped_points'])}/{f(base['raw_unclipped_points'])}。")
lines.append('')
table(lines,['数据集/家族','例数']+[labels[n] for n in methods],[[mode+'/'+group[7:],entries[0]['cases']]+[f(next(x['average_score'] for x in entries if x['method']==n)) for n in methods] for mode in ['dyna','final'] for group,entries in summaries[mode]['groups'].items() if group.startswith('family:')])
lines+=['## 版本、完整性与复现','',
 f"数据捕获提交 `{selections['dyna']['dataset_commit']}`；dyna树 `{selections['dyna']['dataset_tree']}`，final树 `{selections['final']['dataset_tree']}`。两树与R84相同，当前结果没有把新生成TRAIN/DEV并入原始回归。",'',
 '固定Linux CPU运行；官方框架不改，仅MySpillScheduler类变化，构建参数`g++ -std=c++14 -O2`。六个对照复用已核源码/TU/ELF，两项新候选保留编译与定向测试记录。Van捕获提交`d92ceb0262b556eb57aae61127d062174ffe6016`，入口`src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp`；固定方法名Van_latest仅代表该次绑定的版本，不能被移动分支覆盖。','',
 f"dyna完成96/96、final完成576/576，控制器用时分别{completions['dyna']['seconds']:.3f}s/{completions['final']['seconds']:.3f}s，内部预算1100/650s、单格60s；单次串行，0重试。全部stdout与stderr共1344份由Root独立核SHA并从stdout复算成本、分数、分位数，完成门通过；没有据结果改代码或淘汰候选。",'',
 '原始实验清单与结果在`tmp/r85_full_eval/{dyna,final}`，权威为`finalized_summary.json`和`completion_gate.json`；汇总为`combined_dataset_equal.json`，独立复核为`root_review/{dyna,final}`。计划在`docs/superpowers/plans/2026-10-30-r85-full-regression.md`。新面板诊断另见`docs/20261030_R85新数据诊断.md`，不能混为本表数据。','']
table(lines,['方法','源码SHA256'],[[labels[m['name']],m['source_sha256']] for m in selections['dyna']['methods']])
files=['release.json','methods.prepared.json','combined_dataset_equal.json']+[f'{mode}/{file}' for mode in ['dyna','final'] for file in ['selection.json','rows.json','finalized_summary.json','completion_gate.json']]
table(lines,['固定产物','SHA256'],[[f'tmp/r85_full_eval/{p}',sha(RUN/p)] for p in files])
for mode in ['dyna','final']:
    lines+=['## '+mode+' 全部逐例分数','']
    pp={(p['case_id'],p['method']):p for p in summaries[mode]['per_case']}
    rr=[[c['case_id']]+[f(pp[c['case_id'],n]['score']) for n in methods] for c in selections[mode]['cases']]
    table(lines,['case_id']+[labels[n] for n in methods],rr)
    with (HERE/(mode+'_all_case_scores.csv')).open('x',encoding='utf-8',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['case_id']+methods);writer.writerows(rr)
target=ROOT/'docs/20261030_R85完整回归报告.md'
with target.open('x',encoding='utf-8') as handle:handle.write('\n'.join(lines)+'\n')
print(json.dumps(dict(report=str(target),sha256=sha(target),best=ranked[0],cases=84,cells=672),ensure_ascii=False))
