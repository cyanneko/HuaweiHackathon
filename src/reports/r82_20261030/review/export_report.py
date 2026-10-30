from pathlib import Path
import csv,json,hashlib
r=Path(__file__).resolve().parent;root=r.parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review=read(r/'train_result_review.json');per=read(r/'train_per_case_recomputed.json');assert review['status']=='PASS'
parent='R80_next_hier_fast100';new=['R82_singlefit025','R82_write1'];idx={(x['case_id'],x['method']):x for x in per}
for x in per:
 b=idx[x['case_id'],parent];x['physical_ratio_parent']=x['physical']/b['physical'] if b['physical']>0 else None;x['D_ratio_parent']=x['D']/b['D'] if b['D']>0 else None
def table(path,rows):
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 with path.open(newline='',encoding='utf-8') as f:assert len(list(csv.DictReader(f)))==len(rows)
table(r/'per_case_scores.csv',per)
groups=[]
for group,entries in review['score_groups'].items():
 for entry in entries:
  row={'group':group};row.update({k:v for k,v in entry.items() if not isinstance(v,dict)})
  for field in ['cost_parent','physical_parent']:
   row.update({field+'_'+k:v for k,v in entry[field].items()})
  groups.append(row)
table(r/'group_scores.csv',groups)
decision=read(root/'tmp/r82_eval/train/advance.json');completion=read(root/'tmp/r82_eval/train/completion.json')
assert decision['selected']==[] and completion['valid']==228 and completion['changed_artifacts']==[]
dev=root/'tmp/r82_eval/dev';assert not any(dev.glob('cells/**/result.json')) and not (dev/'rows.json').exists() and not (dev/'campaign.json').exists()
failures=[]
for choice in decision['choices']:
 assert choice['method'] in new and not choice['eligible']
 failures.append(dict(method=choice['method'],failed_guards=[k for k,v in choice['guards'].items() if not v],guards=choice['guards'],new12_mean_score=choice['new_train_mean_score'],new12_score_delta_parent=choice['new_train_score_delta'],old26_score_delta_parent=choice['old26_score_delta'],worst_all38_cost_ratio_parent=choice['worst_cost_parent'],D_hard_veto=False))
failure_report=dict(status='BOTH_CANDIDATES_REJECTED_AS_PREDECLARED',execution_failures=0,terminal=228,valid=228,planned=228,selection_sha256=review['selection_sha256'],selected=[],candidates=failures,dev12_policy_runs=0,no_performance_retry=True,unchanged_sources_and_thresholds=True,interpretation='Local surrogate L nonincrease does not guarantee whole-stream physical or D-inclusive cost nonincrease.')
(r/'failure_report.json').write_text(json.dumps(failure_report,indent=2)+'\n')
(r/'audit_attempts.json').write_text(json.dumps(dict(attempts=[dict(runtime='Windows Python',status='PATH_ERROR_BEFORE_LOG_AUDIT',reason='Linux home Naive ELF path is not accessible as a Windows drive-relative path'),dict(runtime='WSL Python',status='PASS',policy_executions=0)],review_script_sha256=sha(r/'review_results.py')),indent=2)+'\n')
g={key:{x['method']:x for x in review['score_groups'][key]} for key in ['all','old26','new_train']}
lines=['# R82 独立结果复核：两个候选均未晋级','',f'228/228 格有效，456 个 stdout/stderr SHA 通过，执行失败0；Root串行单轮耗时 {completion["seconds"]:.3f} 秒（240秒预算）。独立重解析日志并重算同轮Naive分数、raw未截断收益、物理成本、D、P50/P90/最坏值及晋级规则，结果与原报告一致。','', '复用原38 TRAIN（旧26+新12），是反复使用的开发数据，不能称新鲜或盲测。没有修改源码/阈值，没有重跑性能；预留DEV12没有策略执行。','', '| 方法 | 新12平均分 | 新12分差 | 旧26分差 | 新12物理成本/父均值 | 全38最坏含D成本/父 | 全38 D/父 |','|---|---:|---:|---:|---:|---:|---:|']
for name in [parent]+new:
 a=g['all'][name];n=g['new_train'][name];o=g['old26'][name];lines.append(f'| {name} | {n["mean_score"]:.6f} | {n["score_delta_parent"]:+.6f} | {o["score_delta_parent"]:+.6f} | {n["physical_parent"]["mean"]:.6f} | {a["cost_parent"]["worst"]:.6f} | {a["D_total_us"]/g["all"][parent]["D_total_us"]:.6f} |')
lines+=['','singlefit025同时未通过“新12严格提高”和“旧26下降不超过.05”两项；write1未通过新12提高门槛。两者全38最坏成本比均未超过1.25，D也不是硬淘汰门槛。','',f'退步不只是计算开销：singlefit025新12物理成本平均比父高 {(g["new_train"][new[0]]["physical_parent"]["mean"]-1)*100:.4f}%，write1高 {(g["new_train"][new[1]]["physical_parent"]["mean"]-1)*100:.4f}%。两者新12均仅1胜11负；全38均7胜31负。','', 'singlefit025只保证当次、同一估计priority下选出的局部L不高于原方案；动作改变后续驻留、miss和可见样本，局部代理损失不升不意味着完整流物理成本或含D成本不升。write1的真实立即写盘系数也不能校正全部未来成本代理。','', '两个失败方案及其完整逐例数据保留用于发布，不晋级、不替换默认。CSV中的分差以同批R80层级父为基线；ratio为逐例比值的等权均值，不是总成本之比。物理成本=IO+真实penalty×miss；分数=clip(10×(1-C/Cnaive),0,10)，C含实测D。','', '产物：per_case_scores.csv（228行），group_scores.csv，train_per_case_recomputed.json，train_result_review.json，failure_report.json。audit_attempts.json保留Windows路径问题及转WSL纯审计通过的事实；没有额外策略执行。','',f'输入选择SHA：`{review["selection_sha256"]}`。原rows SHA：`{review["rows_sha256"]}`；原summary SHA：`{review["summary_sha256"]}`。source/TU/ELF和框架均复核不变；本次未重新hash大输入，输入身份承接冻结合同。']
(r/'RESULT_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
artifacts=['RESULT_REVIEW.md','per_case_scores.csv','group_scores.csv','train_result_review.json','train_per_case_recomputed.json','failure_report.json','audit_attempts.json']
manifest=dict(status='PASS',source_selection_sha256=review['selection_sha256'],files={name:sha(r/name) for name in artifacts})
(r/'result_artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
