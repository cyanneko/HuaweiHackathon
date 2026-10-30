"""Reparse the frozen matrix and compare same-round controls. No policy launches."""
from pathlib import Path
import csv,json,math,statistics
from common import O,load,sha,locate,save,parser,index_grid,mean_metrics

def distribution(v):
 v=sorted(v);i=.9*(len(v)-1);a=math.floor(i);b=math.ceil(i)
 return dict(mean=statistics.mean(v),p50=statistics.median(v),p90=v[a]+(v[b]-v[a])*(i-a),worst=v[-1],best=v[0])
def points(c,b):return max(0.,min(10.,10*(1-c/b))) if c>0 and b>0 else 0.

def main():
 p=load(O/'precommit.json');s=load(O/'selection.json');done=load(O/'complete.json');campaign=load(O/'campaign.json')
 assert campaign['selection_sha256']==sha(O/'selection.json') and campaign['precommit_sha256']==sha(O/'precommit.json')
 cases=load(locate(p['case_manifest']))['cases'];ids=[c['case_id'] for c in cases];methods={m['name']:m for m in s['methods']}
 assert sha(locate(p['case_manifest']))==p['case_manifest_sha256']==campaign['case_manifest_sha256']
 assert done['terminal']==len(done['rows'])==p['intended_cells']
 assert done['valid']==sum(r['valid'] for r in done['rows']) and done['failed']==sum(not r['valid'] for r in done['rows'])
 by=index_grid(done['rows'],methods,ids,p['repeats']);ev=parser(s);raw_details=[]
 for row in done['rows']:
  folder=O/'raw'/f'{ids.index(row["case_id"]):02d}_r{row["repeat"]}_{row["method"]}'
  assert sha(folder/'stdout.txt')==row['process']['stdout_sha256'] and sha(folder/'stderr.txt')==row['process']['stderr_sha256']
  c=next(c for c in cases if c['case_id']==row['case_id']);m=methods[row['method']]
  assert row['identity']==dict(input_sha256=c['input_sha256'],binary_sha256=m['binary_sha256'],framework_sha256=m['framework_sha256'],params_sha256=campaign['params_sha256'])
  if row['valid']:assert ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26')==row['metrics']
  raw_details.append(dict(method=row['method'],case_id=row['case_id'],repeat=row['repeat'],valid=row['valid'],process_status=row['process']['status'],wall_seconds=row['process']['wall_seconds'],**(row['metrics'] or {})))
 ref=load(O/'normalization_reference.r72.json');assert sha(O/'normalization_reference.r72.json')==p['normalization_reference_sha256']
 historical={c['case_id']:c for c in ref['cases']}
 means={(m,c):mean_metrics([by[m,c,j] for j in range(p['repeats'])]) for m in methods for c in ids}
 case_rows=[];summaries=[];determinism=[]
 for name in methods:
  ratios={b:[] for b in ['VanBest','VanBest_p32']};scores=[];D=[]
  for cid in ids:
   repeated=[by[name,cid,j] for j in range(p['repeats'])];a=means[name,cid]
   original=historical[cid];c=next(c for c in cases if c['case_id']==cid);assert original['input_sha256']==c['input_sha256']
   row=dict(method=name,case_id=cid,valid_repeats=sum(r['valid'] for r in repeated),intended_repeats=p['repeats'],metrics_mean=a,
    historical_Naive_cost=original['metrics']['total_cost_us'],auxiliary_points_vs_historical_Naive=points(a['Total_Score'],original['metrics']['total_cost_us']) if a else None,
    wall_seconds_sum=sum(r['process']['wall_seconds'] for r in repeated))
   for base in ratios:
    b=means[base,cid];v=a['Total_Score']/b['Total_Score'] if a and b and b['Total_Score']>0 else None;row['ratio_to_'+base]=v
    if v is not None:ratios[base].append(v)
   if a:
    D.append(a['Total_Decision_Time']);scores.append(row['auxiliary_points_vs_historical_Naive'])
    trajectories={tuple(r['metrics'][k] for k in ['Total_IO_Time','Hit_Count','Miss_Count']) for r in repeated}
    if len(trajectories)>1:determinism.append(dict(method=name,case_id=cid,physical_trajectory_count=len(trajectories)))
   case_rows.append(row)
  summaries.append(dict(method=name,complete_cases=sum(means[name,c] is not None for c in ids),case_count=6,
   cost_ratios={b:distribution(v) if len(v)==6 else None for b,v in ratios.items()},
   auxiliary_case_mean_v1_vs_historical_Naive=statistics.mean(scores) if len(scores)==6 else None,
   cumulative_D_per_case_us=distribution(D) if len(D)==6 else None))
 report=dict(status='complete' if done['failed']==0 else 'complete_with_failures',terminal=done['terminal'],valid=done['valid'],failed=done['failed'],
  repeats=p['repeats'],unique_cases=6,primary='same-round cost comparison against VanBest and VanBest_p32',
  auxiliary_score_reference='historical sealed R72 Naive, not retimed this round',repeat_aggregation=p['repeat_aggregation'],quantiles='linear interpolation at (n-1)*p',
  D_scope='cumulative microseconds per complete case; repeats averaged within case; not per callback',
  summaries=summaries,per_case=case_rows,physical_repeat_differences=determinism,
  selection_sha256=sha(O/'selection.json'),precommit_sha256=sha(O/'precommit.json'),reporter_sha256=sha(Path(__file__)))
 save(O/'report.json',report)
 keys=['method','case_id','repeat','valid','process_status','wall_seconds','Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']
 with (O/'per_run.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(raw_details)
 fmt=lambda x:'不可用' if x is None else f'{x:.6f}'
 lines=['# R74 正式对比','',f'六个 R72 完整 500 万操作用例，{len(methods)} 种冻结方法，每格 {p["repeats"]} 次；{done["valid"]}/{done["terminal"]} 次有效，失败 {done["failed"]}。','',
  '主比较使用本轮实际重测的原 VanBest 和 p32。重复先在同一案例内对原始指标取平均，再计算成本倍率；六例仍为六个样本。Naive 未在本轮重测，归一化分数仅引用 R72 封存结果作辅助。','',
  '| 方法 | 完整例/6 | 辅助均分/10（历史Naive） | 每例累计D均值(us) |','| --- | ---: | ---: | ---: |']
 for x in summaries:lines.append(f'| {x["method"]} | {x["complete_cases"]} | {fmt(x["auxiliary_case_mean_v1_vs_historical_Naive"])} | {fmt(x["cumulative_D_per_case_us"]["mean"] if x["cumulative_D_per_case_us"] else None)} |')
 for base in ['VanBest','VanBest_p32']:
  lines+=['',f'## 相对本轮 {base} 的逐例成本倍率','', '| 方法 | 均值 | P50 | P90 | 最差 |','| --- | ---: | ---: | ---: | ---: |']
  for x in summaries:
   d=x['cost_ratios'][base];lines.append('| '+' | '.join([x['method'],*[fmt(d[k] if d else None) for k in ['mean','p50','p90','worst']]])+' |')
 lines+=['','## 全部单例','', '| 案例 | 方法 | 有效重复 | IO均值(us) | miss均值 | 总成本均值(us) | /VanBest | /p32 | 累计D均值(us) | 总墙钟(s) |','| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
 for x in case_rows:
  a=x['metrics_mean'];lines.append('| '+' | '.join([x['case_id'],x['method'],f'{x["valid_repeats"]}/{x["intended_repeats"]}',fmt(a['Total_IO_Time'] if a else None),fmt(a['Miss_Count'] if a else None),fmt(a['Total_Score'] if a else None),fmt(x['ratio_to_VanBest']),fmt(x['ratio_to_VanBest_p32']),fmt(a['Total_Decision_Time'] if a else None),fmt(x['wall_seconds_sum'])])+' |')
 lines+=['','所有失败和原始重复都保留，不静默改变分母。D 为整个案例累计耗时，不称单步延迟。六个既有合成用例不代表未知分布；本轮不使用 holdout。','', '[逐次原始指标](per_run.csv) · [完整结构化报告](report.json)']
 (O/'report_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(dict(status=report['status'],valid=done['valid'],failed=done['failed'],summaries=summaries)))
if __name__=='__main__':main()
