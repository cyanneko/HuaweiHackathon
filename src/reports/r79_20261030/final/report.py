"""Summarize the frozen sample only; does not execute a policy."""
from common import HERE,read,save,sha,percentile
import math,sys
ORIGINAL=HERE
if len(sys.argv)>1 and sys.argv[1]=='recovery':HERE=HERE/'recovery'
s=read(HERE/'summary.json');selection=read(ORIGINAL/'selection.json');completion=read(HERE/'completion.json');rows=read(HERE/'rows.json');elapsed=completion.get('elapsed_seconds',completion.get('cumulative_active_controller_seconds'))
lines=['# R79 final_dataset 2.1.0：固定24例初测','',f"状态：{s['status']}；{completion['terminal']}/120格完成，{completion['failures']}失败，{completion['not_run']}未运行；active控制器累计{elapsed:.3f}s。",'',
'范围为三家族×N规模分层的24例（Zipf9、hotspot9、lognormal6），五方法、同批官方Naive、单次重复、case内轮换方法顺序。只代表该固定样本，不是完整72例排名，也不外推官方隐藏测试。', '',
'主分数为逐例包含实测决策时间D的Total_Score相对同批Naive归一化，零成本遵循固定commit的特殊0分规则，24例等权平均；未封顶sum只是辅助。','',
'| 方法 | 样本均分 /10 | 未封顶sum | D总计(ms) | 物理cost总计(us) | Score/Naive P50 | P90 | worst |',
'|---|---:|---:|---:|---:|---:|---:|---:|']
for m in s['methods']:
 a=m['aggregate']
 if a:lines.append(f"| {m['method']} | {a['average_score']:.6f} | {a['uncapped_sum_score']:.6f} | {a['decision_time']/1000:.3f} | {a['physical_cost']:.3f} | {a['ratio_p50']:.6f} | {a['ratio_p90']:.6f} | {a['worst_ratio']:.6f} |")
 else:lines.append(f"| {m['method']} | unavailable | — | — | — | — | — | — |")
pair=[];index={(r['case_id'],r['method']):r for r in rows};base='R75_dense_switch'
for m in selection['methods']:
 if m['name'] in ('Naive',base):continue
 ratios=[];physical=[];details=[]
 for c in selection['cases']:
  a=index.get((c['case_id'],m['name']));b=index.get((c['case_id'],base))
  if not a or not b or not a['valid'] or not b['valid']:continue
  am=a['metrics'];bm=b['metrics'];ratio=am['Total_Score']/bm['Total_Score'];p=c['stats']['penalty'];pr=(am['Total_IO_Time']+p*am['Miss_Count'])/(bm['Total_IO_Time']+p*bm['Miss_Count']);ratios.append(ratio);physical.append(pr);details.append({'case_id':c['case_id'],'score_ratio_to_R75':ratio,'physical_ratio_to_R75':pr})
 if len(ratios)==24:
  pair.append(dict(method=m['name'],case_count=24,equal_case_mean_score_ratio_to_R75=math.fsum(ratios)/24,equal_case_mean_physical_ratio_to_R75=math.fsum(physical)/24,score_wins=sum(v<1 for v in ratios),score_losses=sum(v>1 for v in ratios),score_ties=sum(v==1 for v in ratios),physical_wins=sum(v<1 for v in physical),physical_losses=sum(v>1 for v in physical),physical_ties=sum(v==1 for v in physical),score_p50=percentile(ratios,.5),score_p90=percentile(ratios,.9),best=min(details,key=lambda x:x['score_ratio_to_R75']),worst=max(details,key=lambda x:x['score_ratio_to_R75']),cases=details))
lines+=['','与冻结R75的同例配对诊断（比值小于1更好；不是主均分的另一种算法）：','', '| 方法 | mean Score/R75 | mean physical/R75 | Score胜/负/平 | worst Score/R75 |','|---|---:|---:|---:|---:|']
for p in pair:lines.append(f"| {p['method']} | {p['equal_case_mean_score_ratio_to_R75']:.6f} | {p['equal_case_mean_physical_ratio_to_R75']:.6f} | {p['score_wins']}/{p['score_losses']}/{p['score_ties']} | {p['worst']['score_ratio_to_R75']:.6f} ({p['worst']['case_id']}) |")
lines+=['','每case score、physical、D和原始协议输出见summary.json、rows.json及cells/。P50/P90使用nearest-rank。所有120个预定格保留；若失败/缺格，主完整均分不可用，不删除后重算。','',
'输入实际SHA与metadata由Root72例合同核验，所选输入执行前后再次核SHA；语义合法性继承固定发布审核，未在此重跑全输入语义审计。源码/TU/ELF和相同框架骨架已验证。固定最新evaluator commit为f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246。','',
'单次重复只构成初测，D存在机器与运行噪声；Van的penalty代理与R79不同，参考差异不能全部归于异质性。2.1.0含已曝光旧回归输入，不称untouched。没有借结果换样、调参、训练或自动晋升。','',
f"selection SHA256: `{sha(ORIGINAL/'selection.json')}`",f"rows SHA256: `{sha(HERE/'rows.json')}`",f"summary SHA256: `{sha(HERE/'summary.json')}`"]
if HERE!=ORIGINAL:
 lines+=['',f"执行分段：首次105格完成后progress.json的原子替换失败，第一段{completion['first_segment_controller_seconds']:.3f}s；随后明确授权仅补15个未启动格，第二段{completion['recovery_controller_seconds']:.3f}s。两段间等待不计active预算。没有重跑已完成格；原525个结果/日志/进程记录文件的哈希均保持不变。",'Windows文件占用只是可能原因，未被证实。原中断报告与105格原件仍保存在上一级目录，最终合并结果单独保存在recovery/。']
save(HERE/'paired_to_R75.json',pair);(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines[:18]))
