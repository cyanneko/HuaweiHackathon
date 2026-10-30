import json, math, hashlib, csv, statistics
from pathlib import Path
P=Path('tmp/r87_eval'); O=Path('tmp/r87_sol_review')
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def close(a,b): assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-7),(a,b)
def mean(v): return sum(v)/len(v)
def quant(v,q): return sorted(v)[math.ceil(len(v)*q)-1]
S={d:read(P/d/'selection.json') for d in ('dyna','final')}
M=[m['name'] for m in S['dyna']['methods']]
N=dict(zip(M,['Naive','R75','H：R80 hierarchy','R81','Van paired100','A：fast prior8','B：hier anchor','R87 Fixed-share']))
T='R87_fixedshare_op'; A='R85_fast_prior8'
data={}; agg={}; checks=[]
for d in S:
    rows=read(P/d/'rows.json'); summ=read(P/d/'finalized_summary.json'); gate=read(P/d/'completion_gate.json')
    assert gate['status']=='PASS' and summ['complete'] and all(gate['guards'].values())
    assert len(rows)==len(S[d]['cases'])*8 and all(r['valid'] and r['status']=='PASS' and r['process']['returncode']==0 for r in rows)
    assert len({(r['case_id'],r['method']) for r in rows})==len(rows)
    by={(r['case_id'],r['method']):r for r in rows}; data[d]={}
    for c in S[d]['cases']:
        cid=c['case_id']; penalty=c['stats']['penalty']; b=by[cid,'Naive']['metrics']['Total_Score']; assert b>0
        data[d][cid]={}
        for m in M:
            v=by[cid,m]['metrics']; io=v['Total_IO_Time']; pm=penalty*v['Miss_Count']; D=v['Total_Decision_Time']; C=io+pm+D
            assert math.isclose(C,v['Total_Score'],rel_tol=1e-10,abs_tol=.02),(C,v['Total_Score'])
            C=v['Total_Score']; raw=10*(1-C/b); score=max(0,min(10,raw))
            data[d][cid][m]=dict(IO=io,penalty_miss=pm,D=D,C=C,physical=io+pm,raw=raw,score=score,ratio=C/b,hit=v['Hit_Count'],miss=v['Miss_Count'])
    agg[d]={}
    for m in M:
        v=[x[m] for x in data[d].values()]; ratios=[x['ratio'] for x in v]
        agg[d][m]={k:mean([x[k] for x in v]) for k in ('score','raw','D')}
        agg[d][m].update({k:sum(x[k] for x in v) for k in ('IO','penalty_miss','C','physical')})
        agg[d][m].update(D_total=sum(x['D'] for x in v),p50=quant(ratios,.5),p90=quant(ratios,.9),worst=max(ratios),losses=sum(x>1 for x in ratios),ratio_mean=mean(ratios))
        original=next(x for x in summ['groups']['all'] if x['method']==m)
        for x,y in [('score','average_score'),('raw','mean_raw_unclipped_points'),('D_total','D_total_us'),('p50',None),('p90',None),('worst',None)]:
            close(agg[d][m][x], original[y] if y else original['ratio_to_Naive'][x])
    audit=read(P/'root_review'/d/'review.json'); assert audit['status']=='PASS'
    checks.append(dict(dataset=d,cells=len(rows),gate='PASS',summary_recalculation='PASS',stdout_audit='PASS'))
comb=read(P/'combined_dataset_equal.json'); eq={m:{k:(agg['dyna'][m][k]+agg['final'][m][k])/2 for k in ('score','raw')} for m in M}
for m in M:
    c=next(x for x in comb['methods'] if x['method']==m)
    close(eq[m]['score'],c['equal_dataset_mean_score']); close(eq[m]['raw'],c['equal_dataset_raw_points'])
for f,h in comb['dependencies'].items(): assert sha(f)==h,(f,h)
with (O/'per_case_metrics.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(['dataset','case','method','IO_us','penalty_miss_us','D_us','C_us','physical_us','raw','score','C_Naive','hit','miss'])
    for d in data:
        for c,ms in data[d].items():
            for m,x in ms.items(): w.writerow([d,c,m]+[x[k] for k in ('IO','penalty_miss','D','C','physical','raw','score','ratio','hit','miss')])
(O/'independent_summary.json').write_text(json.dumps(dict(status='PASS',checks=checks,aggregate=agg,equal_dataset=eq,native_runs=0,input_body_scans=0,log_reaudit=False),indent=2),encoding='utf-8')
L=[]
def p(s=''): L.append(s)
def table(headers,rows):
    p('|'+ '|'.join(headers)+'|'); p('|'+ '|'.join(['---']*len(headers))+'|')
    for row in rows:p('|'+ '|'.join(str(x) for x in row)+'|')
    p()
def f(v):return f'{v:.6f}'
p('# R87 旧版完整评测报告：算子热度 Fixed-share 混合')
p('\n2026-10-31。固定旧版 dyna_dataset 1.0 全12例与 final_dataset 2.1.0 eval72；8方法，全部672格新测。两个阶段完成门和独立原始输出审计均 PASS。本文仅报告本轮旧版完整评测；R86 的 final3 补充结果没有混入。\n')
p(f'**主结论：R87 两数据集50/50均分 {f(eq[T]["score"])}，低于直接父版 A 的 {f(eq[A]["score"])}（差 {eq[T]["score"]-eq[A]["score"]:+.6f}），也低于 R81；高于 H、Van 与 R75。** 本轮不能认定 R87 优于 A。R87 的等权 raw 分为 '+f(eq[T]['raw'])+'，高于 A 的 '+f(eq[A]['raw'])+'；这说明截断排名与保留负分的排名不同，不能只选一种指标宣称全面胜出。冻结 R75 默认提交不自动晋级。\n')
p('## 方法与评测含义\n')
p('R87 从 A：R85_fast_prior8 出发，仅替换算子边际的快/慢热度概率混合。新 probe 标签先用尚未插入该标签的两专家预测概率做贝叶斯后验更新，再执行 `w′=α+(1−2α)×posterior`，其中 `α=1/256`，然后计入新标签；混合为 `w×p_fast+(1−w)×p_slow`。这不是神经网络。慢分区条件、候选提议和裁剪等行为保持父版。优化预测 logloss 并不保证 spill 代价改善；本轮只评价最终代价。\n')
p('`C=模拟IO时间+本例评测罚值×Miss_Count+实测累计决策时间D`。同阶段、同例的本轮 Naive 成本为 B，逐例分数为 `clip(10×(1−C/B),0,10)`；raw 为未截断的 `10×(1−C/B)`。本轮所有 B>0。先分别平均 dyna12 和 final72，再各占50%；没有把84例等权，也没有先加总绝对成本求分。P50/P90 使用最近秩 `ceil(q×n)`，分数据集报告，不混合分位数。\n')
p('调度器使用合法固定代理罚值100，不能读取本例隐藏实际罚值或未来完整序列；官方合法 next 一步信息可用。完整输入预读属于离线评测器，不是在线算法能力。IO与miss罚值是模拟量，不能解释为真实磁盘或端到端加速。D仅测一次，CPU频率、调度与系统负载会引入波动；任何细小D差及由此形成的微小总分差均不能声称统计显著。数据已用于开发，原 train/dev/holdout 名称不代表本轮盲测。\n')
p('## 全部方法主结果\n')
table(['方法','dyna均分','final均分','50/50均分','dyna raw','final raw','50/50 raw','dyna平均D(ms)','final平均D(ms)'],[[N[m],f(agg['dyna'][m]['score']),f(agg['final'][m]['score']),f(eq[m]['score']),f(agg['dyna'][m]['raw']),f(agg['final'][m]['raw']),f(eq[m]['raw']),f(agg['dyna'][m]['D']/1000),f(agg['final'][m]['D']/1000)] for m in M])
p('以下差值均为本轮同批新测；旧R85历史D不作分母。\n')
table(['R87相对','50/50均分差','50/50 raw差'],[[N[m],f(eq[T]['score']-eq[m]['score']),f(eq[T]['raw']-eq[m]['raw'])] for m in M if m!=T])
p('## 模拟成本与累计决策时间\n')
p('以下均为所列数据集所有例的累计量，统一换算为秒（原始记录为微秒）；这些绝对累计量用于成本分解，不用于替代逐例平均评分。\n')
table(['数据集','方法','模拟IO(s)','miss罚值(s)','IO+miss(s)','D(s)','总C(s)'],[[d,N[m]]+[f(agg[d][m][k]/1e6) for k in ('IO','penalty_miss','physical','D_total','C')] for d in data for m in M])
p('## 相对Naive的尾部\n')
table(['数据集','方法','平均C/Naive','P50','P90','最差','差于Naive例数'],[[d,N[m]]+[f(agg[d][m][k]) for k in ('ratio_mean','p50','p90','worst')]+[agg[d][m]['losses']] for d in data for m in M])
p('## 直接父版A与其他对照\n')
p('比值为逐例 R87/参考方法，越小越好。物理比排除D，累计D比为数据集D总和之比；胜/平/负按实测总C严格比较，接近1的差别仍需结合单次D局限。\n')
comp=[]
for d in data:
    for m in [A,'R81_op256_cond2048','R80_next_hier_fast100','Van_latest','R75_dense_switch']:
        vals=list(data[d].values()); r=[x[T]['C']/x[m]['C'] for x in vals]; pr=[x[T]['physical']/x[m]['physical'] for x in vals]
        comp.append([d,N[m],f(agg[d][T]['score']-agg[d][m]['score']),f(mean(r)),f(quant(r,.5)),f(quant(r,.9)),f(max(r)),f(mean(pr)),f(agg[d][T]['D_total']/agg[d][m]['D_total']),f'{sum(x<1 for x in r)}/{sum(x==1 for x in r)}/{sum(x>1 for x in r)}'])
table(['数据集','参考','均分差','平均C比','P50','P90','最差','平均物理比','累计D比','胜/平/负'],comp)
p('R87相对A在dyna为4胜8负，均分降低0.002404；final为41胜31负，均分降低0.005638，但raw提高0.031813，最终50/50 raw提高0.014705。final平均逐例成本比0.996351与最差1.214147同时存在：平均改善不代表每例改善。最差反例 `eval_051_random_zipf` 的总C比A高21.414726%，物理成本比高约21.4056%，分数由2.129542降到0.444105；不能把这次退化仅归为D波动。另有零分例的raw改善未进入截断分的增量。以上是数据事实，不据此猜测热度切换的因果机制；主展示分未胜、尾部存在明确反例，因此没有稳健晋级证据。\n')
p('### 退化与零分案例\n')
p('无运行失败、超时、缺格、无效格或重试。性能退化仍逐例保留；以下列出各数据集相对A最差的5例，并列出全部R87差于Naive的例子。零分截断会隐藏负分幅度，因此同时给raw。\n')
for d in data:
    ids=sorted(data[d],key=lambda c:data[d][c][T]['C']/data[d][c][A]['C'],reverse=True)[:5]
    table(['数据集/例','R87/A C','R87/A物理','R87分','A分','R87 raw','A raw'],[[d+'/'+c,f(data[d][c][T]['C']/data[d][c][A]['C']),f(data[d][c][T]['physical']/data[d][c][A]['physical'])]+[f(data[d][c][m][k]) for k in ('score','raw') for m in (T,A)] for c in ids])
table(['数据集/例','R87/Naive C','R87分','R87 raw'],[[d+'/'+c,f(x[T]['ratio']),f(x[T]['score']),f(x[T]['raw'])] for d in data for c,x in data[d].items() if x[T]['ratio']>1])
p('### 全部相对A成本更高案例\n')
table(['数据集/例','R87/A C','R87/A物理','R87−A分差','R87−A raw差'],[[d+'/'+c,f(x[T]['C']/x[A]['C']),f(x[T]['physical']/x[A]['physical']),f(x[T]['score']-x[A]['score']),f(x[T]['raw']-x[A]['raw'])] for d in data for c,x in data[d].items() if x[T]['C']>x[A]['C']])
p('## 家族与原始split均分\n')
p('分组为观察性描述，不能从某组涨跌推断机制因果。\n')
for field in ('family','original_split'):
    rr=[]
    for d in data:
        groups=sorted({c.get(field,'未标注') for c in S[d]['cases']})
        for g in groups:
            ids=[c['case_id'] for c in S[d]['cases'] if c.get(field,'未标注')==g]
            rr.append([d+'/'+g,len(ids)]+[f(mean([data[d][c][m]['score'] for c in ids])) for m in M])
    table([field,'例数']+[N[m] for m in M],rr)
p('## 框架、环境与完整性\n')
p('固定数据提交 `c65c7b32b06a5764ce9ad4881133a3c6eb33ed17`；dyna树 `808ce8b11f57a1a96051f22aa572eceb82b1fba0`，final树 `41197783dd577dfccf5b007a6ece67cbfb241e4b`。精确输入字节、大小、元数据和每方法身份保存在两个 `selection.json`，完整准备阶段已读全输入核SHA；本次报告复核未重扫大型输入。\n')
p('框架只替换 MySpillScheduler；Root源码审计确认类替换后官方框架完全相同。构建为 `g++ -std=c++14 -O2`，CPU-only。运行环境记录引用 `tmp/r84_van_build/environment.json`：Ubuntu 22.04 / WSL2 Linux 5.15.167.4，Intel Core i7-14700HX，g++11.4.0；该环境记录是本轮冻结依赖，并非本报告额外采样。源码定向编译测试窗口14.777639秒，其验证与性能主测相互区分。\n')
p('单次、串行、无历史D复用、无retry。按例名字典序、八方法固定顺序逐例左旋，避免每例完全相同的执行位置。dyna96格用时728.394629秒，final576格303.915679秒；循环预算1100/650秒，单格60秒；准备与部分退出完整性检查不在循环预算内。两个完成门均为PASS，控制器返回成功、无改动制品、有效格=计划格，active children=0且CPU已释放。\n')
p('独立原始输出审计 `tmp/r87_eval/root_review/{dyna,final}/review.json` 均PASS，核对1344份stdout/stderr哈希及结果复算；本报告另从672行metrics独立重算公式、均分、raw、Naive尾部，并核对combined的全部依赖SHA，未导入原评分器、未重跑native。stdout各字段仅保留小数，成本分解允许0.02微秒舍入容差，评分使用记录的Total_Score。独立报告复核记录为 `tmp/r87_sol_review/independent_summary.json`。七个控制组相对R85共588组的IO/Hit/Miss、input/source SHA逐项完全一致，审计 `tmp/r87_test_operator/control_comparison.json` PASS且无mismatch；新测D变化不应解释为算法行为变更。\n')
p('Van_latest 是固定作者 paired_penalty100 源码，并非实验联合风险池。沿用R85绑定的源码提交 `d92ceb0262b556eb57aae61127d062174ffe6016`，捕获证据提交 `6ded7022215b80a8edf4170faefe1ca4da16814f`；不得将移动分支名当成未来仍相同的实现。\n')
p('### 方法制品SHA256\n')
table(['方法','源码SHA256','TU SHA256','ELF SHA256'],[[m['name'],m['source_sha256'],m['translation_unit_sha256'],m['binary_sha256']] for m in S['dyna']['methods']])
p('### 结果及复现文件SHA256\n')
paths=['tmp/r87_eval/regression.py','tmp/r87_eval/scoring.py','tmp/r87_eval/release.json','docs/superpowers/plans/2026-10-30-r87-fixed-share-operator.md','tmp/r87_root_review/source_review.json','tmp/r87_impl_review/independent_review.json','tmp/r87_eval/combined_dataset_equal.json','tmp/r87_test_operator/control_comparison.json']
for d in data:
    paths += [f'tmp/r87_eval/{d}/{x}.json' for x in ('selection','rows','summary','finalized_summary','completion','completion_gate','input_gate','cpu_released')]+[f'tmp/r87_eval/root_review/{d}/review.json']
paths += ['tmp/r87_sol_review/independent_summary.json','tmp/r87_sol_review/per_case_metrics.csv']
table(['文件','SHA256'],[[x,sha(x)] for x in paths])
p('复算报告：在仓库根目录运行 `python tmp/r87_sol_review/build_report.py`，只读取冻结小结果文件并生成报告和CSV，不启动基准或训练。完整框架执行接口与限制见 `tmp/r87_eval/README.md`、`protocol.md` 和冻结计划；原运行是先prepare两个阶段，再各阶段run、完成门PASS后combine。不可覆盖现有write-once结果作为重跑。\n')
p('## 完整逐例分数\n')
p('以下是全部84例、每例8方法的截断分数。未截断raw、IO、miss罚值、D、C、Hit/Miss与Naive比值全部保存在 `tmp/r87_sol_review/per_case_metrics.csv`；SHA见上表。\n')
for d in data:
    p('### '+d+'\n')
    table(['例']+[N[m] for m in M],[[c]+[f(x[m]['score']) for m in M] for c,x in data[d].items()])
p('## 输入SHA256清单\n')
p('逐例完整输入SHA以冻结selection为准；下表直接提取其记录。准备阶段全文件验证已经完成，本报告未再次读取正文。\n')
table(['数据集/例','输入SHA256'],[[d+'/'+c['case_id'],c['input_sha256']] for d in S for c in S[d]['cases']])
Path('docs/20261031_R87旧版完整评测报告.md').write_text('\n'.join(L)+'\n',encoding='utf-8')
print(json.dumps(dict(status='PASS',report='docs/20261031_R87旧版完整评测报告.md',sha256=sha('docs/20261031_R87旧版完整评测报告.md'),equal=eq),ensure_ascii=False,indent=2))
