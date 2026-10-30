"""Report all precommitted R70 rows; no model selection or solver execution."""
from pathlib import Path
import csv,hashlib,json,math,statistics,sys
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
sys.path.insert(0,str(ROOT/'tmp/dataset_score_audit_20261030/benchmark/dependencies/evaluation'))
import evaluate as evaluator
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def dist(v):
 v=sorted(v);i=.9*(len(v)-1);lo=math.floor(i);hi=math.ceil(i)
 return dict(mean=statistics.mean(v),p50=statistics.median(v),p90=v[lo]+(v[hi]-v[lo])*(i-lo),worst=v[-1],best=v[0])
def csvfile(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 selection=load(O/'selection.bound.json');pre=load(O/'model_v2.precommit.json');campaign=load(O/'campaign.json')
 assert campaign['selection_sha256']==sha(O/'selection.bound.json') and campaign['precommit_sha256']==sha(O/'model_v2.precommit.json')
 assert selection['primary_candidate']=='TinyNN' and selection['model_json_sha256']==pre['model_json_sha256']
 methods=[m['name'] for m in selection['methods']];all_details=[];reports={}
 for split in ['dev','holdout']:
  complete=load(O/split/'complete.json');assert complete['status']=='complete' and complete['valid']==complete['cells']==48
  case_doc=load(O/'dev_cases.json') if split=='dev' else load(O/'holdout/cases.released.json')
  cases={r['case_id']:r for r in case_doc['cases']};assert len(cases)==8
  rows={}
  for row in complete['rows']:
   key=(row['method'],row['case_id']);assert key not in rows and row['valid'];folder=O/split/'raw'/f'{list(cases).index(row["case_id"]):02d}_{row["method"]}'
   assert row['identity']['input_sha256']==cases[row['case_id']]['input_sha256']
   m=next(m for m in selection['methods'] if m['name']==row['method']);assert row['identity']['binary_sha256']==m['binary_sha256']
   assert sha(folder/'stdout.txt')==row['process']['stdout_sha256'] and sha(folder/'stderr.txt')==row['process']['stderr_sha256']
   parsed=evaluator.parse_metrics((folder/'stdout.txt').read_text(),cases[row['case_id']]['stats'],'official-2026-10-26')
   assert parsed==row['metrics'];rows[key]=row
  assert set(rows)=={(m,c) for m in methods for c in cases}
  ranking=[];details=[]
  for name in methods:
   points=[];ratios=[];cost=[];base=[];decisions=[];wins=ties=losses=0
   for cid,c in cases.items():
    a=rows[(name,cid)]['metrics'];b=rows[('Naive',cid)]['metrics'];val,bs=a['Total_Score'],b['Total_Score']
    point=max(0.,min(10.,10*(1-val/bs))) if val>0 and bs>0 else 0.;ratio=val/bs if bs>0 else None
    assert ratio is not None,'zero baseline must be reported explicitly, not discarded'
    points.append(point);ratios.append(ratio);cost.append(val);base.append(bs);decisions.append(a['Total_Decision_Time'])
    wins+=val<bs;ties+=val==bs;losses+=val>bs
    row=dict(split=split,method=name,case_id=cid,total_cost_us=val,naive_cost_us=bs,total_ratio=ratio,points=point,
     io_us=a['Total_IO_Time'],miss=a['Miss_Count'],hit=a['Hit_Count'],D_cumulative_us=a['Total_Decision_Time'],
     naive_io_us=b['Total_IO_Time'],naive_miss=b['Miss_Count'],naive_D_cumulative_us=b['Total_Decision_Time'])
    details.append(row);all_details.append(row)
   ranking.append(dict(method=name,score_sum_uncapped=math.fsum(points),mean_points=statistics.mean(points),
    total_cost_ratio=math.fsum(cost)/math.fsum(base),case_ratio=dist(ratios),D_per_case_cumulative_us=dist(decisions),
    wins=wins,ties=ties,losses=losses))
  pair=[]
  for cid,c in cases.items():
   n=rows[('TinyNN',cid)]['metrics'];h=rows[('Heuristic',cid)]['metrics']
   nio=n['Total_IO_Time']+c['stats']['penalty']*n['Miss_Count'];hio=h['Total_IO_Time']+c['stats']['penalty']*h['Miss_Count']
   pair.append(dict(case_id=cid,total_ratio=n['Total_Score']/h['Total_Score'],
    NN_cost=n['Total_Score'],Heuristic_cost=h['Total_Score'],NN_io_miss=nio,Heuristic_io_miss=hio,
    NN_D=n['Total_Decision_Time'],Heuristic_D=h['Total_Decision_Time']))
  comparison=dict(total_cost_ratio=math.fsum(r['NN_cost'] for r in pair)/math.fsum(r['Heuristic_cost'] for r in pair),
   case_ratio=dist([r['total_ratio'] for r in pair]),NN_better=sum(r['total_ratio']<1 for r in pair),
   NN_equal=sum(r['total_ratio']==1 for r in pair),NN_worse=sum(r['total_ratio']>1 for r in pair),per_case=pair)
  ranking.sort(key=lambda r:-r['score_sum_uncapped']);reports[split]=dict(status='complete',cases=8,measurements=48,repeats=1,
   ranking=ranking,precommitted_primary='TinyNN',NN_vs_Heuristic=comparison)
  save(O/split/'report.json',reports[split]);csvfile(O/split/'per_case.csv',details)
 csvfile(O/'per_case96.csv',all_details)
 report=dict(status='complete',cases=16,measurements=96,repeats=1,primary='TinyNN',model_sha256=pre['model_json_sha256'],quantile_method='linear interpolation at (n-1)*p',
  scope='precommitted model_v2; dev8 and once-only holdout8 reported separately',splits=reports,
  limits=['single repeat; small synthetic split; no hidden-distribution or generalization guarantee',
   'producer scorer/action parity is implementation validation, not a performance win',
   'training loss is not substituted for IO/miss/formal cumulative D'])
 save(O/'report.json',report)
 lines=['# R70 model_v2 六方案评测','', '唯一 primary 为预先冻结的 TinyNN model_v2。六方法 × dev8/holdout8 × 一次，共 96 格。dev 有效后自动评测 holdout，未依据得分换模型、调阈值或重训。','']
 for split in ['dev','holdout']:
  r=reports[split];p=r['NN_vs_Heuristic'];lines += [f'## {split}8','',
   f'TinyNN / Heuristic 合计成本倍率为 {p["total_cost_ratio"]:.6f}；逐例 NN 较好/相同/较差为 {p["NN_better"]}/{p["NN_equal"]}/{p["NN_worse"]}。',
   f'逐例倍率等权均值 {p["case_ratio"]["mean"]:.6f}，P50 {p["case_ratio"]["p50"]:.6f}，P90 {p["case_ratio"]["p90"]:.6f}，最差 {p["case_ratio"]["worst"]:.6f}。','',
   '| 方法 | 未封顶总分 /80 | 均分 /10 | 合计成本/Naive | P50 倍率 | P90 倍率 | 最差倍率 | 每例累计 D 均值（微秒） |',
   '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
  for x in r['ranking']:lines.append(f'| {x["method"]} | {x["score_sum_uncapped"]:.5f} | {x["mean_points"]:.5f} | {x["total_cost_ratio"]:.6f} | {x["case_ratio"]["p50"]:.6f} | {x["case_ratio"]["p90"]:.6f} | {x["case_ratio"]["worst"]:.6f} | {x["D_per_case_cumulative_us"]["mean"]:.2f} |')
  lines += ['', '| 案例 | NN/Heuristic 成本 | NN IO+miss | Heuristic IO+miss | NN 累计 D | Heuristic 累计 D |', '| --- | ---: | ---: | ---: | ---: | ---: |']
  for x in p['per_case']:lines.append(f'| {x["case_id"]} | {x["total_ratio"]:.6f} | {x["NN_io_miss"]:.2f} | {x["Heuristic_io_miss"]:.2f} | {x["NN_D"]:.2f} | {x["Heuristic_D"]:.2f} |')
  lines += ['']
 lines += ['D 是每个完整案例中正式回调累计耗时，单位微秒。P50/P90 使用排序位置 (n-1)*p 的线性插值。主分沿用逐例 clip(10*(1-C/B),0,10) 后八例未封顶求和，零成本规则沿用原解析器；dev 与 holdout 不合并作单一选型分。全部负例保留，训练 loss 和非正式 parity 耗时不作性能结论。','',
  '原始五指标和逐例身份位于各 split/raw；[全部 96 条结果](per_case96.csv) 与 [结构化报告](report.json) 可复核。']
 (O/'report_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(dict(status='complete',measurements=96,primary='TinyNN',NN_vs_Heuristic={k:v['NN_vs_Heuristic']['total_cost_ratio'] for k,v in reports.items()})))
if __name__=='__main__':main()
