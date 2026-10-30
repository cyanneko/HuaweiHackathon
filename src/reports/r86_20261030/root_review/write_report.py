"""Render the complete R86 report only after all result gates and Root audit pass."""
from pathlib import Path
import hashlib,json,statistics,math
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tmp/r86_eval'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def num(v):return '未定义' if v is None else f'{v:.6f}'
names={'Naive':'Naive','R75_dense_switch':'R75','R80_next_hier_fast100':'R80 hierarchy','R80_paired_hier_fast100':'R80 paired','R81_op256_cond2048':'R81 op256','Van_latest':'Van paired100','R85_fast_prior8':'A：fast prior8','R85_hier_anchor':'B：hier anchor'}
dyna=read(ROOT/'tmp/r85_full_eval/dyna/finalized_summary.json');final=read(OUT/'final/finalized_summary.json');old=read(ROOT/'tmp/r85_full_eval/final/finalized_summary.json');combined=read(OUT/'combined_dataset_equal.json');selection=read(OUT/'final/selection.json');done=read(OUT/'final/completion.json')
audit=read(OUT/'root_review/final/review.json')
assert all(x['complete'] for x in [dyna,final,old,combined]) and audit['status']=='PASS' and audit['cells']==576
assert read(OUT/'final/completion_gate.json')['status']=='PASS' and read(OUT/'final/cpu_released.json')['active_child_processes']==0
assert combined['historical_dyna_reuse'] and not combined['dyna_remeasured_in_R86'] and selection['dataset_version']=='3.0.0'
for p,h in combined['dependencies'].items():assert sha(ROOT/p)==h
di={x['method']:x for x in dyna['aggregate']};fi={x['method']:x for x in final['aggregate']};oi={x['method']:x for x in old['aggregate']};ci={x['method']:x for x in combined['methods']}
best=max(combined['methods'],key=lambda x:x['equal_dataset_mean_score']);finalbest=max(final['aggregate'],key=lambda x:x['average_score'])
lines=[]
def paragraph(s):lines.extend([s,''])
def table(headers,rows):
    lines.append('|'+ '|'.join(headers)+'|');lines.append('|'+ '|'.join(['---']*len(headers))+'|')
    for row in rows:lines.append('|'+ '|'.join(str(v) for v in row)+'|')
    lines.append('')
paragraph('# R86 新版 final 3.0 补充评测：含 Van，以旧版数据为主')
paragraph('**最新用户约定：以旧版为准。** 后续主评测和选优依据固定为原 dyna_dataset 1.0.0 全部12例 + final_dataset 2.1.0 全部72例。R85完整回归是这套主数据的当前结果；本报告的新 final3 仅保留为补充敏感性实验，不用于替换主榜或决定晋升。这个约定不改变官方框架和编译要求。')
paragraph('2026-10-30。本轮固定八个已有方法，完整新测 final_dataset 3.0.0 的全部 72 例，共 576 格。dyna 的 12 例沿用刚完成的 R85 全量结果，包含其原同轮 Naive 和决策时间；没有重新运行，也没有把旧 final 2.1 的成绩混入新榜。')
paragraph(f'仅在本补充实验中，按两套数据各占 50% 的预定计算口径，最高为 **{names[best["method"]]}：{num(best["equal_dataset_mean_score"])} 分**；单独新版 final 最高为 **{names[finalbest["method"]]}：{num(finalbest["average_score"])} 分**。这不是用户指定主数据上的排名，也不是官方隐藏集成绩或全仓库所有成员榜单。R75 默认保持不变。')
v=ci['Van_latest']
paragraph(f'Van 使用作者当前纯数学入口 `paired_penalty100.cpp` 的原字节：dyna 均分 **{num(v["dyna_mean_score"])}**，新版 final 均分 **{num(v["final_mean_score"])}**，两数据集等权均分 **{num(v["equal_dataset_mean_score"])}**。这里没有把作者另一个实验性联合风险池版本冒充当前入口。')
paragraph('## 评分、耗时和数据边界')
paragraph('`C = 模拟 IO 时间 + 本例评测罚值 × miss 次数 + 实测累计决策时间 D`。每例分数为 `clip(10×(1−C/Cnaive), 0, 10)`，非正成本或分母遵循冻结评测器的零分规则；raw 保留负分。每套数据分别求逐例算术平均，再各占 50%，不是把 84 个点等权混合，也不是总成本先相加后作比。没有全局 50 分封顶。物理成本仅指 IO+miss 罚值，不含 D；模拟 IO 不等于实盘端到端耗时。')
paragraph('每例使用同一测试批次的 Naive：dyna 用 R85 的 Naive，final3 用 R86 的 Naive。单次 CPU 串行计时，没有误差条；不能把微小 D 差异视为稳定优势。下文 D 为一例的累计决策时间，历史 dyna 的 D 明确为复用，不能计作本轮新增运行耗时。P50/P90 使用最近秩，12 例取第 6/11 项，72 例取第 36/65 项；不合并或平均两套数据的分位数。')
paragraph('新版 final 固定提交 `e6613435d59690d6dd768813332387108f7e83c2`，tree `35d4f98b7464e62a9a89b606e41d192380788e76`。72 例全部更换 PROBE 流，合计 22,528,629 操作、474,874,682 输入字节；28 hotspot、28 Zipf、16 lognormal。BUILD 布局继承已曝光的旧例，因此不是盲测。加强算子内热度差异是这批合成数据的设计约定，不是官方隐藏数据分布的保证。')
paragraph('独立数据审计完整扫描本地 eval72，并核对 72 份真实父版本 sidecar 的 BUILD 布局；没有重新审计全部 train540。发布者保存的 612 例审计另作来源证据。概率证书和未来计数只用于离线校验，不进入在线调度器。')
paragraph('## 补充实验完整结果（不替换旧版主榜）')
table(['方法','dyna12 均分（复用）','final3/72 均分','两集等权均分','两集等权 raw','dyna 平均 D(ms，复用)','final3 平均 D(ms)'],[[names[n],num(ci[n]['dyna_mean_score']),num(ci[n]['final_mean_score']),num(ci[n]['equal_dataset_mean_score']),num(ci[n]['equal_dataset_raw_points']),num(di[n]['D_mean_us']/1000),num(fi[n]['D_mean_us']/1000)] for n in names])
paragraph('## 相对 Naive 的成本分布')
table(['数据集','方法','平均倍率','P50','P90','最差倍率','比 Naive 更差例数'],[[label,names[n],num(a[n]['ratio_to_Naive']['mean']),num(a[n]['ratio_to_Naive']['p50']),num(a[n]['ratio_to_Naive']['p90']),num(a[n]['ratio_to_Naive']['worst']),a[n]['negative_improvement_cases']] for label,a in [('dyna12（历史）',di),('final3/72（新测）',fi)] for n in names])
paragraph('## 两项改动与直接父版本')
paragraph('A 仅降低 R81 快速算子边际的平滑权重，B 改为以 hierarchy 为比较基准；本轮没有调整它们的代码或参数。表中成本倍率的分母为各自父版，不是 Naive；双方零分时 raw 和倍率仍保留退化。')
rows=[]
for n,parent in [('R85_fast_prior8','R81_op256_cond2048'),('R85_hier_anchor','R80_next_hier_fast100')]:
    x=fi[n];p=fi[parent];ref=x['references'][parent];rat=ref['cost_ratio']
    rows.append([names[n],names[parent],num(x['average_score']-p['average_score']),num(x['mean_raw_unclipped_points']-p['mean_raw_unclipped_points']),num(rat['mean']),num(rat['p50']),num(rat['p90']),num(rat['worst']),f'{rat["wins"]}/{rat["ties"]}/{rat["losses"]}',num(x['D_total_us']/p['D_total_us'])])
table(['候选','父版','final3 均分差','raw 差','平均成本比','P50','P90','最差成本比','胜/平/负','累计 D 比'],rows)
for n,parent in [('R85_fast_prior8','R81_op256_cond2048'),('R85_hier_anchor','R80_next_hier_fast100')]:
    cases=[r for r in final['per_case'] if r['method']==n];worst=max(cases,key=lambda r:r['references'][parent]['cost_ratio']);p=next(r for r in final['per_case'] if r['method']==parent and r['case_id']==worst['case_id'])
    paragraph(f'- {names[n]} 对 {names[parent]}：等权均分差 {num(ci[n]["equal_dataset_mean_score"]-ci[parent]["equal_dataset_mean_score"])}；等权 raw 差 {num(ci[n]["equal_dataset_raw_points"]-ci[parent]["equal_dataset_raw_points"])}。新版 final 最差父版倍率在 `{worst["case_id"]}`：成本比 {num(worst["references"][parent]["cost_ratio"])}，物理比 {num(worst["references"][parent]["physical_ratio"])}；候选/父版分数 {num(worst["score"])}/{num(p["score"])}，raw {num(worst["raw_unclipped_points"])}/{num(p["raw_unclipped_points"])}。')
paragraph('## 新旧 final 分开比较')
paragraph('以下两列使用相同方法代码，但 PROBE 输入不同、各自 Naive 与 D 也来自不同测试批次。因此差值反映数据升级后的表现变化，不能当作算法改进幅度；旧版结果不会回写。')
table(['方法','旧 final2.1/72（R85）','新 final3/72（R86）','新减旧'],[[names[n],num(oi[n]['average_score']),num(fi[n]['average_score']),num(fi[n]['average_score']-oi[n]['average_score'])] for n in names])
paragraph('## 新版 final 家族均分')
table(['家族','例数']+list(names.values()),[[key.split(':',1)[1],entries[0]['cases']]+[num(next(e for e in entries if e['method']==n)['average_score']) for n in names] for key,entries in final['groups'].items() if key.startswith('family:')])
paragraph('## 版本与完整性')
paragraph('保持官方框架不变，仅使用 MySpillScheduler 类；CPU-only，原构建参数 `g++ -std=c++14 -O2`。八方法与 R85 源码/TU/ELF 身份相同，调度器固定 proxy100，不知道真实评测罚值或完整未来序列。Van 同源入口在作者提交 `6ded7022215b80a8edf4170faefe1ca4da16814f` 再核，源码与此前捕获版本完全相同。')
paragraph('新 final 576/576 有效；完整完成门通过，Root 独立复核全部 1152 份 stdout/stderr 的哈希，并从原 stdout 重算成本、分数和分位数。R85 dyna 原 96 格及其完整门单独绑定。内部执行循环预算 650 秒、单格 60 秒、串行一遍、无重试；准备和收尾校验不全部计入循环预算，这也不是官方总运行时限。')
paragraph('初次 Windows 静态检查发现 Python 汇总浮点数末位与 Linux 不同，已记录并拒绝通过；该阶段未运行调度器。正式 Linux 静态检查与完整评测保留严格身份/完成门，不修改历史摘要来掩盖差异。')
table(['方法','源码 SHA256'],[[names[m['name']],m['source_sha256']] for m in selection['methods']])
artifacts=['docs/superpowers/plans/2026-10-30-r86-final3-complete-regression.md','tmp/r86_eval/release.json','tmp/r86_eval/final/selection.json','tmp/r86_eval/final/rows.json','tmp/r86_eval/final/finalized_summary.json','tmp/r86_eval/final/completion_gate.json','tmp/r86_eval/combined_dataset_equal.json','tmp/r86_eval/historical_dyna_reuse.json','tmp/r86_eval/root_review/final/review.json']
table(['复现产物','SHA256'],[[p,sha(ROOT/p)] for p in artifacts])
paragraph('复现入口为 `tmp/r86_eval/README.md` 与冻结计划；由合作 Master 归档到 `source/cyanneko`，固定发布链接由归档文档另列。本报告不把尚未推送的产物说成已发布。')
for title,summary in [('dyna12 全部逐例分数（R85 历史复用）',dyna),('final3/72 全部逐例分数（R86 新测）',final)]:
    paragraph('## '+title);idx={(r['case_id'],r['method']):r for r in summary['per_case']}
    table(['case_id']+list(names.values()),[[cid]+[num(idx[cid,n]['score']) for n in names] for cid in sorted({r['case_id'] for r in summary['per_case']})])
target=ROOT/'docs/20261030_R86新版final3补充评测报告.md'
with target.open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
print(json.dumps(dict(report=str(target),sha256=sha(target),best=best['method'],score=best['equal_dataset_mean_score'],Van_equal=v['equal_dataset_mean_score']),ensure_ascii=False))
