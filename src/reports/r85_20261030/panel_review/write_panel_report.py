from pathlib import Path
import csv,hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[2];R=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
x=read(R/'panel_result_review.json');assert x['status']=='PASS'
A='R85_fast_prior8';B='R85_hier_anchor';H='R80_next_hier_fast100';F='R81_op256_cond2048';V='Van_latest'
labels={'Naive':'Naive',H:'R80 hierarchy',F:'R81 op256','R80_paired_hier_fast100':'R80 paired',V:'Van paired100',A:'A：fast prior8',B:'B：hier anchor'}
index={phase:{e['method']:e for e in p['all']} for phase,p in x['phases'].items()}
per=list(csv.DictReader((R/'panel_per_case.csv').open(encoding='utf-8-sig')))
gs=list(csv.DictReader((R/'panel_groups.csv').open(encoding='utf-8-sig')))
for g in gs:
 if g['group']=='all':
  pp=[p for p in per if p['phase']==g['phase'] and p['method']==g['method']]
  assert abs(statistics.mean(float(p['score_delta__'+g['reference']]) for p in pp)-float(g['score_delta']))<1e-10
lines=['# R85 新数据诊断：A 有局部增益，B 尚未获益','',
'2026-10-30。**这是新 TRAIN12 与独立 seed DEV6 的完整七方法面板诊断，不是原 dyna/final 的全量结论。** 两阶段分别为84/84、42/42有效格；本报告独立重解析126份stdout，并核252份stdout/stderr SHA、完整病例/方法矩阵、固定顺序、完成门禁及全部分组统计。没有重跑策略、编译、训练或生成数据。','',
'A仅把R81的快算子边际总prior由64改为8.009479828345365，慢条件prior64不动；B以R80 hierarchy为默认，在原门槛内比较旧启发式替代，比较公式不动。两项保持独立，不合并。','',
'## 分阶段主结果','',
'每例使用同批Naive作为分母：`clip(10×(1−C/Cnaive),0,10)`；`C=模拟IO时间+输入罚值×miss+实测累计调度时间D`。raw保留负分。下表各列分别按该阶段病例等权，不混合12例与6例，也不套用原dyna/final各50%的协议。所有Naive与参考成本分母均有效。','',
'| 方法 | TRAIN12 clipped | TRAIN12 raw | DEV6 clipped/raw | TRAIN平均D(ms) | DEV平均D(ms) |',
'|---|---:|---:|---:|---:|---:|']
for name in labels:
 a,b=index['train'][name],index['dev'][name]
 lines.append(f"| {labels[name]} | {a['average_score']:.6f} | {a['mean_raw_unclipped_points']:.6f} | {b['average_score']:.6f} | {a['D_mean_us']/1000:.3f} | {b['D_mean_us']/1000:.3f} |")
lines+=['','A对其父R81：TRAIN均分提高0.135475，DEV提高0.051098。物理成本比均值分别为0.973478、0.980694，说明差异并非仅由D造成。但DEV仅3胜3负：slow_staggered单例增加0.428720分，六例总增分约0.306586，故其余五例合计为负。这是集中而非普遍的改善。','',
'A对R80 hierarchy：TRAIN clipped提高0.041639，但raw降低0.051938；DEV仅提高0.005027。A不能据本面板称为稳定全面优于hierarchy。','',
'B对其父hierarchy：TRAIN/DEV均分分别下降0.026990/0.034951，总成本为3胜9负/1胜5负。物理成本比均值为1.005331/1.008220，平均D约为父版的1.842/1.859倍，不能把下降全归因于D。虽然本面板B好于旧paired均分，但“更换默认方案”仍不足以超过直接hierarchy。','',
'## 成本分布与最差点','',
'比值为逐例总成本/参考总成本，越小越好；P50/P90用最近秩，TRAIN12取第6/11项，DEV6取第3/6项。这里DEV的P90就是最差点。','',
'| 阶段 | 候选/参考 | 胜:平:负 | 平均比 | P50 | P90 | 最差比 |',
'|---|---|---:|---:|---:|---:|---:|']
for phase in ['train','dev']:
 for name,ref in [(A,F),(B,H),(A,V),(B,V)]:
  s=index[phase][name]['references'][ref]['cost_ratio']
  lines.append(f"| {phase.upper()} | {labels[name]}/{labels[ref]} | {s['wins']}:{s['ties']}:{s['losses']} | {s['mean']:.6f} | {s['p50']:.6f} | {s['p90']:.6f} | {s['worst']:.6f} |")
lines+=['','A对R81的最差点：TRAIN `r85_train_12_random_lognormal`为1.048034，DEV `r85_dev_18_random_lognormal`为1.015786。B对hierarchy的最差点：TRAIN `r85_train_10_random_zipf`为1.036796，DEV `r85_dev_13_slow_staggered`为1.023469。A对Van分别10胜2负、5胜1负；B对Van分别10胜2负、4胜2负，仍不能称逐例支配。','',
'**不能被零分藏掉的反例：** `r85_train_08_random_hotspot`中A、R81、hierarchy的clipped分数均为0；A的raw为−5.676918，R81约−5.019260，hierarchy约−4.553997。A总成本比R81高4.3788%、比hierarchy高7.7156%。B同例也为0分，但其raw比父低0.277851分，总成本高1.9091%。TRAIN中A有1个负收益点、R81有2个；负收益点减少不代表每个已有负点都改善。DEV七方法均没有负收益被截断，故该阶段raw等于clipped。','',
'## 分轨与机制','',
'| 阶段/轨道 | 例数 | hierarchy | R81 | Van | A | B |',
'|---|---:|---:|---:|---:|---:|---:|']
for phase,p in x['phases'].items():
 for group,entries in p['tracks'].items():
  e={v['method']:v for v in entries}
  lines.append('| '+phase.upper()+'/'+group.split(':',1)[1]+' | '+str(e[H]['cases'])+' | '+' | '.join(f"{e[n]['average_score']:.6f}" for n in [H,F,V,A,B])+' |')
lines+=['','A的正信号偏向动态轨道：TRAIN动态相对R81增加约0.161039分，DEV动态增加约0.122564分。TRAIN IID也高于R81，但仍低于hierarchy；DEV IID低于R81与hierarchy。B两轨两阶段都低于hierarchy。','',
'下面保留逐机制均分差；动态TRAIN每机制只有1例、IID每家族2例，DEV每机制1例。它们只是覆盖点，不是可靠的机制胜率。','',
'| 阶段/机制 | 例数 | A−R81 | B−hierarchy | A−Van | B−Van |',
'|---|---:|---:|---:|---:|---:|']
for phase,p in x['phases'].items():
 for group,entries in p['mechanisms'].items():
  e={v['method']:v for v in entries};score=lambda n:e[n]['average_score']
  lines.append('| '+phase.upper()+'/'+group.split(':',1)[1]+' | '+str(e[A]['cases'])+' | '+' | '.join(f'{v:+.6f}' for v in [score(A)-score(F),score(B)-score(H),score(A)-score(V),score(B)-score(V)])+' |')
lines+=['','本轮18个独立seed，没有带宽配对。动态TRAIN中shared全为压力1.25、staggered全为压力3，存在相位与压力混杂；各例K/P/内存/罚值等也变化，不能从这些分组差异推断相位因果。动态生成器自然采样counts，IID构造器预分配bytes/counts，两个轨道并非同一随机模型。DEV独立seed只代表同声明机制验证；执行后已曝光，不是官方未见集。','',
'## 完整性、失败与身份','',
'两阶段controller分别用时31.694089秒、15.663886秒，均在各180秒预算内；单格上限60秒，1repeat、CPU串行。最终gate均PASS，controller正常返回、error为空、terminal=valid=planned、身份无变化、CPU active0。raw summary始终complete=false，仅row_grid_complete=true；必须以finalized_summary和最后的completion_gate认定完成。独立检查也复核了这一分离，没有用全行齐全掩盖尾部异常。','',
'本轮生成失败0、策略失败0、缺格0、重试0。下列预执行证据继续保留，不混称为策略失败：A旧prior数值oracle与B旧paired空证据anchor两个预期红测；旧raw-summary完成语义的协议红测；Windows默认临时目录权限导致的测试工具失败（改为工作区内保留目录）；真实IID参数无n的KeyError（修为build_count+probe_count+K，补实际manifest测试）。这些修复均在正式native前，九项协议测试及七个候选定向程序已通过。没有依据本面板结果改候选。','',
'Van归属 `source/Vanius0525`，捕获提交 `d92ceb0262b556eb57aae61127d062174ffe6016`，入口 `src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp`；本轮保留Van原方案身份。A/B是本项目独立消融，不冒称Van原提交。','',
'关键身份如下；完整七方法source/TU/ELF、Van证明、冻结runner/data和所有失败证据SHA均在独立review JSON中，不以移动分支代替版本。','',
'| 产物 | SHA256 |','|---|---|']
for file in ['tmp/r85_ablations/producer.json','tmp/r85_eval/experiment.py','tmp/r85_eval/scoring.py','tmp/r85_eval/protocol.md','tmp/r85_eval/release.json','tmp/r85_data_panel/data_manifest.json','tmp/r85_data_panel/review.json','tmp/r85_eval/train/finalized_summary.json','tmp/r85_eval/dev/finalized_summary.json']:
 lines.append(f'| `{file}` | `{x["bindings"][file]}` |')
lines+=['','本次独立复核从stdout重算成本、分数和全部参考比，并核源/TU；ELF身份引用已绑定的Root source/TU/ELF重核记录，本次不额外读取Linux-home ELF，不重扫大输入。审查结果及每份日志SHA见 [panel_result_review.json](..<LOCAL_TEMP> [panel_per_case.csv](..<LOCAL_TEMP> [panel_groups.csv](..<LOCAL_TEMP>','',
'## 后续解释边界','',
'A的平均先验/质量匹配假设得到有限正信号，但证据不能证明它消除了回调采样偏差、修复了R84尾部，或普遍改善IID；B在新面板暂未证明相对hierarchy有益。两者仍按预先固定的八方法原数据全量协议继续比较，不据新面板成绩淘汰、调参或晋升。任何“原dyna/final更优”的判断必须等待该轮正式完整结果。一次D测量没有误差条，模拟IO+罚值也不是实盘端到端性能。','']
target=ROOT/'docs/20261030_R85新数据诊断.md';target.write_text('\n'.join(lines),encoding='utf-8')
files=[R/'panel_result_review.json',R/'panel_per_case.csv',R/'panel_groups.csv',R/'panel_audit.py',Path(__file__),target]
with (R/'panel_artifacts.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',native_runs=0,files={p.relative_to(ROOT).as_posix():sha(p) for p in files}),f,indent=2);f.write('\n')
print(json.dumps({'report_path':str(target),'report_sha256':sha(target),'review_sha256':sha(R/'panel_result_review.json')},ensure_ascii=False))
