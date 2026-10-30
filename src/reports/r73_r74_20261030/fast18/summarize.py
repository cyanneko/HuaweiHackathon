"""Final18 raw-output/D comparison, reusing the frozen parser and helpers."""
from pathlib import Path
import csv,json,math,statistics
from common import O,ROOT,load,sha,save,locate,parser,index_grid

def physical(m):return tuple(m[k] for k in ['Total_IO_Time','Hit_Count','Miss_Count'])
def distribution(values):
 v=sorted(values);i=.9*(len(v)-1);a=math.floor(i);b=math.ceil(i)
 return dict(mean=statistics.mean(v),p50=statistics.median(v),p90=v[a]+(v[b]-v[a])*(i-a),worst=v[-1],best=v[0])

def main():
 p=load(O/'precommit.json');s=load(O/'selection.json');done=load(O/'complete.json');campaign=load(O/'campaign.json')
 assert done['terminal']==18 and len(done['rows'])==18
 assert campaign['precommit_sha256']==sha(O/'precommit.json') and campaign['selection_sha256']==sha(O/'selection.json')
 cases=load(locate(p['case_manifest']))['cases'];ids=[c['case_id'] for c in cases];methods={m['name']:m for m in s['methods']}
 by=index_grid(done['rows'],methods,ids,1);ev=parser(s);raw=[]
 for row in done['rows']:
  c=next(c for c in cases if c['case_id']==row['case_id']);m=methods[row['method']];folder=O/'raw'/f'{ids.index(row["case_id"]):02d}_r0_{row["method"]}'
  assert row['identity']==dict(input_sha256=c['input_sha256'],binary_sha256=m['binary_sha256'],framework_sha256=m['framework_sha256'],params_sha256=campaign['params_sha256'])
  assert sha(folder/'stdout.txt')==row['process']['stdout_sha256'] and sha(folder/'stderr.txt')==row['process']['stderr_sha256']
  assert load(folder/'ownership.json')['cleaned'] is True
  if row['valid']:assert ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26')==row['metrics']
  raw.append(dict(case_id=row['case_id'],method=row['method'],valid=row['valid'],wall_seconds=row['process']['wall_seconds'],wall_under_60_seconds=row['process']['wall_seconds']<60,**(row['metrics'] or {})))
 history=load(O/'history.r74_slow.json');assert sha(O/'history.r74_slow.json')==p['historical_reference_sha256']
 old={(r['method'],r['case_id']):r['metrics_mean'] for r in history['per_case']};pairs=[]
 for c in cases:
  cid=c['case_id'];rows=[by[m,cid,0] for m in p['methods']]
  if not all(r['valid'] for r in rows):pairs.append(dict(case_id=cid,valid=False));continue
  slow,fast,cov=[r['metrics'] for r in rows];previous_op=old['R74_operator',cid];previous_cov=old['R74_coverage',cid]
  pairs.append(dict(case_id=cid,valid=True,same_round_operator_physical_equal=physical(slow)==physical(fast),
   slow_operator_matches_previous_physical=physical(slow)==physical(previous_op),fast_coverage_matches_historical_physical=physical(cov)==physical(previous_cov),
   slow_operator_D_us=slow['Total_Decision_Time'],fast_operator_D_us=fast['Total_Decision_Time'],fast_coverage_D_us=cov['Total_Decision_Time'],
   historical_slow_coverage_D_us=previous_cov['Total_Decision_Time'],same_round_operator_D_ratio=fast['Total_Decision_Time']/slow['Total_Decision_Time'],
   historical_coverage_D_ratio=cov['Total_Decision_Time']/previous_cov['Total_Decision_Time']))
 complete=all(x['valid'] for x in pairs);summary=None
 if complete:
  mean={m:statistics.mean(by[m,c,0]['metrics']['Total_Decision_Time'] for c in ids) for m in p['methods']}
  old_cov=statistics.mean(old['R74_coverage',c]['Total_Decision_Time'] for c in ids)
  summary=dict(mean_cumulative_D_us=mean,same_round_operator_mean_D_ratio=mean['R74_fast_operator']/mean['R74_operator'],
   same_round_operator_case_ratios=distribution([x['same_round_operator_D_ratio'] for x in pairs]),
   historical_slow_coverage_mean_D_us=old_cov,historical_coverage_mean_D_ratio=mean['R74_fast_coverage']/old_cov,
   historical_coverage_case_ratios=distribution([x['historical_coverage_D_ratio'] for x in pairs]),
   operator_physical_equal_cases=sum(x['same_round_operator_physical_equal'] for x in pairs),
   coverage_historical_physical_equal_cases=sum(x['fast_coverage_matches_historical_physical'] for x in pairs))
 report=dict(status='complete' if complete else 'complete_with_failures',terminal=18,valid=done['valid'],failed=done['failed'],repeats=1,summary=summary,per_case=pairs,
  all_actual_wall_under_official_60_seconds=all(r['wall_under_60_seconds'] for r in raw),max_actual_wall_seconds=max(r['wall_seconds'] for r in raw),
  primary='fast operator vs same-round remeasured slow operator',auxiliary='fast coverage vs previous slow coverage, cross-round only',
  physical_scope='Printed IO/hit/miss equality, not a per-action trace audit',D_scope='cumulative microseconds per complete case; LUT first-call initialization included, no warmup',
  watchdog='180 seconds internal only; official per-run wall limit checked separately at60 seconds',reporter_sha256=sha(Path(__file__)))
 save(O/'report.json',report)
 keys=['case_id','method','valid','wall_seconds','wall_under_60_seconds','Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']
 with (O/'per_run18.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(raw)
 lines=['# R74 LUT 最后18格复验','',f'18 格固定单次运行：有效 {done["valid"]}，失败 {done["failed"]}；最大实际进程墙钟 {report["max_actual_wall_seconds"]:.3f} 秒。180 秒仅为内部看护，题面 60 秒单独核对。','']
 if summary:
  a=summary['mean_cumulative_D_us'];lines += [f'同轮 operator 完整案例累计 D 均值从 {a["R74_operator"]/1e6:.6f} 秒降至 {a["R74_fast_operator"]/1e6:.6f} 秒，下降 {(1-summary["same_round_operator_mean_D_ratio"])*100:.3f}%。六例打印 IO/hit/miss 相同：{summary["operator_physical_equal_cases"]}/6。',
   f'fast coverage 累计 D 均值 {a["R74_fast_coverage"]/1e6:.6f} 秒；旧 slow coverage 为 {old_cov/1e6:.6f} 秒，跨轮比值 {summary["historical_coverage_mean_D_ratio"]:.6f}，仅作辅助参考。六例打印物理指标与旧 coverage 相同：{summary["coverage_historical_physical_equal_cases"]}/6。','']
 lines+=['| 完整用例 | slow operator D(us) | fast operator D(us) | 同轮D倍率 | 物理指标相同 | fast coverage D(us) | 旧coverage D(us) | 跨轮D倍率 |','| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |']
 for x in pairs:
  if x['valid']:lines.append(f'| {x["case_id"]} | {x["slow_operator_D_us"]:.2f} | {x["fast_operator_D_us"]:.2f} | {x["same_round_operator_D_ratio"]:.6f} | {x["same_round_operator_physical_equal"]} | {x["fast_coverage_D_us"]:.2f} | {x["historical_slow_coverage_D_us"]:.2f} | {x["historical_coverage_D_ratio"]:.6f} |')
  else:lines.append(f'| {x["case_id"]} | 未完整 | | | | | | |')
 lines+=['','每例均为新进程，无预热，LUT 首次初始化留在回调计时内。物理一致性只涵盖打印的 IO/hit/miss，不冒称逐动作轨迹审计；单次六例不外推为未知分布性能。原 slow R74 证据保持不变，本轮后不扩新实验。','', '[全部18次五指标与墙钟](per_run18.csv) · [结构化报告](report.json)']
 (O/'report_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='per_case'}))
if __name__=='__main__':main()
