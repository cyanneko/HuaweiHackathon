"""Verify preserved measurements and report the complete selected 50-case suite."""
from pathlib import Path
import collections,csv,hashlib,json,math,statistics,sys
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O/'dependencies/evaluation'))
import evaluate as evaluator
from scripts.summarize_member_scores import summarize_report

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def distribution(values):
 v=sorted(values)
 return dict(mean=statistics.mean(v),median=statistics.median(v),p90=v[math.ceil(.9*len(v))-1],max=v[-1],min=v[0]) if v else None
def write_csv(path,rows):
 if not rows:return
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 s=load(O/'selection.r1.json');cs=load(O/'cases.json');build=load(O/'build_identity.json')
 cases={r['case_id']:r for r in cs['cases']};methods={r['name']:r for r in s['methods']}
 built={r['name']:r for r in build['records']};rows={};bad=[]
 for path in sorted((O/'results').glob('*/result.json')):
  r=load(path);k=(r['method'],r['case_id'],r['repeat']);assert k not in rows,'duplicate measurement'
  assert r['method'] in methods and r['case_id'] in cases and r['repeat']==0
  expected=dict(input_sha256=cases[r['case_id']]['input_sha256'],binary_sha256=built[r['method']]['binary_sha256'],
   framework_sha256=s['framework_sha256'],selection_sha256=sha(O/'selection.r1.json'),runner_sha256=sha(O/'runner.py'),case_manifest_sha256=sha(O/'cases.json'))
  assert r['identity']==expected,(path,'identity')
  for name,key in [('stdout.txt','stdout_sha256'),('stderr.txt','stderr_sha256')]:assert sha(path.parent/name)==r['process'][key]
  if r['valid']:
   parsed=evaluator.parse_metrics((path.parent/'stdout.txt').read_text(),cases[r['case_id']]['stats'],'official-2026-10-26')
   assert parsed==r['metrics'];assert r['process']['status']=='EXITED' and r['process']['returncode']==0
  else:bad.append(dict(method=r['method'],case_id=r['case_id'],process=r['process'],parse_error=r.get('parse_error')))
  rows[k]=r
 for m in s['methods']:
  assert sha(O/m['policy'])==m['source_sha256']
  assert sha(O/m['translation_unit'])==m['translation_unit_sha256']==built[m['name']]['translation_unit_sha256']
 coverage={name:dict(recorded=sum((name,cid,0) in rows for cid in cases),
  valid=sum(rows.get((name,cid,0),{}).get('valid',False) for cid in cases)) for name in methods}
 complete=len(rows)==700 and not bad
 if not complete:
  save(O/'summary_partial.json',dict(status='partial',coverage=coverage,failed=bad,recorded=len(rows),intended=700))
  print(json.dumps(dict(status='partial',recorded=len(rows),intended=700,coverage=coverage)));return 1
 raw_base=[dict(member='final_dataset',case=c['name'],repeat=0,metrics=rows[('Naive',cid,0)]['metrics']) for cid,c in cases.items()]
 summary=[];detail=[];families=[]
 for name,m in methods.items():
  measured=[dict(member='final_dataset',case=c['name'],repeat=0,metrics=rows[(name,cid,0)]['metrics']) for cid,c in cases.items()]
  normalization=evaluator.normalize(measured,raw_base,[cs['dataset']])
  normalized= summarize_report(dict(status='complete',protocol='official-2026-10-26',suite_id=cs['suite_id'],repeats=1,partial=True,
   datasets=[cs['dataset']],skipped_members=[],normalization=normalization))
  points={r['case']:r['single_score'] for r in normalization['cases']};rr=[];dr=[];ds=[];io=[];costs=[];bases=[];wins=ties=losses=0
  per=[]
  for cid,c in cases.items():
   v=rows[(name,cid,0)]['metrics'];b=rows[('Naive',cid,0)]['metrics'];ratio=v['Total_Score']/b['Total_Score'];rr.append(ratio)
   costs.append(v['Total_Score']);bases.append(b['Total_Score']);ds.append(v['Total_Decision_Time'])
   io.append(v['Total_IO_Time']+c['stats']['penalty']*v['Miss_Count'])
   if b['Total_Decision_Time']>0:dr.append(v['Total_Decision_Time']/b['Total_Decision_Time'])
   delta=v['Total_Score']-b['Total_Score'];tol=1e-9
   wins+=delta < -tol;ties+=abs(delta)<=tol;losses+=delta>tol
   d=dict(method=name,role=m['role'],case=c['name'],family=c['family'],repeat=0,
    total_score=v['Total_Score'],naive_total_score=b['Total_Score'],total_ratio=ratio,single_score=points[c['name']],
    io_us=v['Total_IO_Time'],naive_io_us=b['Total_IO_Time'],miss_count=v['Miss_Count'],naive_miss_count=b['Miss_Count'],
    hit_count=v['Hit_Count'],decision_us=v['Total_Decision_Time'],naive_decision_us=b['Total_Decision_Time'],
    io_plus_miss_us=io[-1],operations=c['operations'])
   per.append(d);detail.append(d)
  summary.append(dict(method=name,role=m['role'],cases=50,repeats=1,
   score_sum=normalized['score_final'],mean_case_points=normalized['datasets'][0]['mean_case_points_aux'],
   raw_capped_score=normalized['raw_capped_average_score'],total_cost_ratio=math.fsum(costs)/math.fsum(bases),
   case_cost_ratio=distribution(rr),decision_us=distribution(ds),decision_ratio=distribution(dr),
   total_io_plus_miss_us=math.fsum(io),total_cost_us=math.fsum(costs),wins=wins,ties=ties,losses=losses,
   worst_cases=sorted(per,key=lambda x:x['total_ratio'],reverse=True)[:3],
   source_sha256=m['source_sha256'],binary_sha256=built[name]['binary_sha256']))
  for family in sorted({r['family'] for r in per}):
   group=[r for r in per if r['family']==family]
   families.append(dict(method=name,family=family,cases=len(group),mean_points=statistics.mean(r['single_score'] for r in group),
    mean_cost_ratio=statistics.mean(r['total_ratio'] for r in group),worst_cost_ratio=max(r['total_ratio'] for r in group),
    cost_sum_ratio=math.fsum(r['total_score'] for r in group)/math.fsum(r['naive_total_score'] for r in group),
    decision_mean_us=statistics.mean(r['decision_us'] for r in group)))
 summary.sort(key=lambda r:(-r['score_sum'],r['method']))
 report=dict(status='complete',scope=s['scope'],dataset_commit=s['data_commit'],dataset_version='2.0.0',suite_id=cs['suite_id'],
  case_count=50,method_count=14,repeats=1,measurements=700,valid_measurements=700,
  score_formula='sum_case(clip(10*(1-VAL/BASE),0,10)), no dataset50 cap; a single selected dataset',
  source_updates=load(O/'teammate_updates.json'),selection_sha256=sha(O/'selection.r1.json'),runner_sha256=sha(O/'runner.py'),
  build_identity=build,data_audit=load(O/'data_audit.json'),native_data_identity=load(O/'native_data_identity.json') if (O/'native_data_identity.json').exists() else None,
  methods=summary,failures=bad,
  limitations=['One repeat; callback D differences are not statistical significance.',
   'Fixed public synthetic 50-case eval; results do not establish official hidden-set performance.',
   'Unchanged official framework and metric validation; no independent action-by-action audit of these 700 performance runs.',
   'Best/robust/AI/tree labels refer to their authors stated candidates at the frozen revisions; experimental controls retain that status.'])
 save(O/'report.json',report);write_csv(O/'per_case.csv',detail);write_csv(O/'by_family.csv',families)
 write_csv(O/'ranking.csv',[dict(method=r['method'],role=r['role'],score_sum=r['score_sum'],mean_case_points=r['mean_case_points'],
  total_cost_ratio=r['total_cost_ratio'],case_ratio_median=r['case_cost_ratio']['median'],case_ratio_p90=r['case_cost_ratio']['p90'],
  case_ratio_worst=r['case_cost_ratio']['max'],D_mean_us=r['decision_us']['mean'],D_ratio_mean=r['decision_ratio']['mean'] if r['decision_ratio'] else None,
  wins=r['wins'],ties=r['ties'],losses=r['losses']) for r in summary])
 top=next(r for r in summary if r['method']!='Naive')
 lines=['# final_dataset v2 全部 50 例方法对比', '',
  f'固定数据提交 `{s["data_commit"]}`，VERSION=2.0.0；14 种方法 × 50 例 × 1 次重复，700/700 条指标完整有效。', '',
  f'按未封顶逐例分求和，{top["method"]} 在本轮最高：总分 {top["score_sum"]:.6f}，逐例均分 {top["mean_case_points"]:.6f}/10，合计成本为 Naive 的 {top["total_cost_ratio"]:.6f} 倍。该结论只对应这组固定公开合成测试。', '',
  '## 方法对比', '',
  '本轮只选择 final_dataset 这一个集合，主分为 50 例原始贡献求和，理论上限 500；逐例均分为主分除以 50。本表不代表旧三成员等权总榜。原评测器封顶 50 分另保留。Total_Score 包含 IO、miss 惩罚和正式回调决策耗时 D。', '',
  '`p_i = clip(10 * (1 - C_i / B_i), 0, 10)`，其中 C_i 为候选 Total_Score、B_i 为同例 Naive Total_Score；沿用原实现，任一成本不为正时贡献记 0。`主分 = sum_i(p_i)`，`逐例均分 = 主分 / 50`。', '',
  '| 方法 | 未封顶总分 ↑ | 逐例均分 ↑ | 合计成本/Naive ↓ | 成本倍率 P90 ↓ | 最差倍率 ↓ | 每例累计 D 的均值（微秒）↓ | 胜/平/负 |',
  '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
 for r in summary:
  lines.append(f'| {r["method"]} | {r["score_sum"]:.4f} | {r["mean_case_points"]:.4f} | {r["total_cost_ratio"]:.4f} | {r["case_cost_ratio"]["p90"]:.4f} | {r["case_cost_ratio"]["max"]:.4f} | {r["decision_us"]["mean"]:.2f} | {r["wins"]}/{r["ties"]}/{r["losses"]} |')
 lines += ['', 'Clean、FitTie 为同源消融候选，BBP 为实验对照；R63/R65 保留实验状态。VanLegacy、LiuFinal 为旧版对照。单次 D 和相应胜负受计时波动影响。', '',
  '## 同伴版本更新', '',
  'Vanius 源码固定 `9c755a71b26f5a0937dbbfc7edf68272b3510e72`：新增当前主推 MySpillSchedulerBest.cpp，同时纳入明确推荐的稳健备选和 ai_prefetch_budget2048；原纯算法保留为 VanLegacy 对照。', '',
  'liunian 源码固定 `0c6d963a1fcc364ecdf763c638571358928bab42`：新增并推荐 MySpillScheduler_tree.cpp，同时比较保留的 final 规则版和 neural 备选。源码变化及逐文件身份见 [teammate_updates.json](teammate_updates.json) 和 [selection.r1.json](selection.r1.json)。', '',
  '## 首位方法的退化案例', '',
  '| 输入 | 成本/Naive | 方法 IO 微秒 | 方法 miss | 方法 D 微秒 | Naive D 微秒 |',
  '| --- | ---: | ---: | ---: | ---: | ---: |']
 for r in top['worst_cases']:
  lines.append(f'| {r["case"]} | {r["total_ratio"]:.6f} | {r["io_us"]:.2f} | {r["miss_count"]} | {r["decision_us"]:.2f} | {r["naive_decision_us"]:.2f} |')
 lines += ['', '## 复核和范围', '',
  f'统一编译器：`{build["compiler"]}`，参数 `-std=c++14 -O2`；原官方框架只替换调度器类及其实例化。程序在实际 Linux HOME 下的持久工作目录 `{build["native_root"]}` 串行执行，逐格上限 60 秒。suite_id 为 `{cs["suite_id"]}`。', '',
  '全部 50 例已做严格输入审核。每条性能记录重新核对程序/输入身份、五项输出、Probe 总数和代价公式；本轮没有逐动作独立重放，不据自报指标声称完整动作审核通过。后续重复须另行安排，不能将本轮单次 D 当作稳定优势。', '',
  '全部逐例分数和原始成本见 [per_case.csv](per_case.csv)，家族分组见 [by_family.csv](by_family.csv)，完整机器、源码和程序身份及坏例见 [report.json](report.json)。']
 (O/'report_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(dict(status='complete',cases=50,methods=14,measurements=700,ranking=[dict(method=r['method'],sum=r['score_sum'],mean=r['mean_case_points'],cost_ratio=r['total_cost_ratio'],worst=r['case_cost_ratio']['max'],D_us=r['decision_us']['mean']) for r in summary]),ensure_ascii=False))
 return 0
if __name__=='__main__':raise SystemExit(main())
