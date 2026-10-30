"""Add interpretation and the end-of-run source check to verified results."""
from pathlib import Path
import csv,hashlib,json,math
O=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
d=load(O/'report.json');latest=load(O/'latest_source_recheck.json');assert all(r['same_bytes'] for r in latest['checks'])
methods={r['method']:r for r in d['methods']}
family_rows=list(csv.DictReader((O/'by_family.csv').open(encoding='utf-8-sig')))
families=[r for r in family_rows if r['method']=='VanBest' and r['family'].startswith('random_')]
best,robust,legacy,tree,rule,ai=[methods[x] for x in ['VanBest','VanRobust','VanLegacy','LiuTree','LiuFinal','VanAI2048']]
derived=dict(best_vs_robust_score_gap=best['score_sum']-robust['score_sum'],
 best_vs_legacy_mean_points_delta=best['mean_case_points']-legacy['mean_case_points'],
 best_vs_legacy_aggregate_cost_reduction=1-best['total_cost_ratio']/legacy['total_cost_ratio'],
 tree_vs_final_mean_points_delta=tree['mean_case_points']-rule['mean_case_points'],
 tree_vs_final_aggregate_cost_reduction=1-tree['total_cost_ratio']/rule['total_cost_ratio'],
 latest_source_check_all_measured_vanius_same_bytes=True)
d.update(latest_source_recheck=latest,interpretation=derived,
 units_notes=dict(decision_us='Each value is the cumulative official callback D for one full case, in microseconds. Mean is over 50 cases, not per callback.',
 total_cost_ratio='Sum of candidate Total_Score divided by sum of Naive Total_Score; simulated IO plus miss penalty plus measured D.',
 score_sum='One selected final_dataset set, uncapped sum over 50 cases, maximum500; not the historical three-member equal-weight leaderboard.'))
save(O/'report.json',d)
path=O/'report_zh.md';text=path.read_text(encoding='utf-8')
interpretation=[
 '## 本轮结论', '',
 f'优先保留 VanBest 和 VanRobust 这一领先组。两者未封顶总分只差 {derived["best_vs_robust_score_gap"]:.4f}，VanRobust 的合计成本还略低；一次测量不足以把这点差异认定为稳定胜负。VanAI2048 分数稍低，每例累计 D 均值为 {ai["decision_us"]["mean"]/1000:.3f} 毫秒，对比 VanBest 的 {best["decision_us"]["mean"]/1000:.3f} 毫秒，本轮没有显示出更好的整体取舍。', '',
 f'同伴更新确有收益：VanBest 相对 VanLegacy 的逐例均分提高 {derived["best_vs_legacy_mean_points_delta"]:.4f}，合计成本降低约 {derived["best_vs_legacy_aggregate_cost_reduction"]*100:.2f}%；LiuTree 相对 LiuFinal 的均分提高 {derived["tree_vs_final_mean_points_delta"]:.4f}。不过 LiuFinal 的最差成本仅为 Naive 的 {rule["case_cost_ratio"]["max"]:.4f} 倍，50 例中 48 例更低，尾部比本轮 Tree 和 Vanius 领先组更稳健。', '',
 'R65 的逐例均分为 1.6956，低于本轮前列方法；BBP 未超过 R65，SingleFit 和 R63 的最坏成本分别达到 Naive 的约 1.95 倍和 1.51 倍。本轮结果不支持把这些实验方法提升为唯一主推。Clean 和 VanLegacy 的分数几乎相同，不能把极小差异解释成已确认的算法收益。', '',
 '## 为什么均分看起来偏低', '',
 '全部 50 例严格输入检查通过，本轮没有复现数据损坏。按家族观察，VanBest 在均匀随机场景相对 Naive 的收益较小；热点和对数正态场景收益明显。分数取决于输入分布及相对基线的成本改善，不能直接与旧三成员测试或旧场景抽样的均分横比。', '',
 '| 新常规家族 | 例数 | VanBest 逐例均分 /10 | 合计成本/Naive |',
 '| --- | ---: | ---: | ---: |']
labels={'random_uniform':'均匀随机','random_zipf':'Zipf 倾斜','random_hotspot':'随机热点','random_lognormal':'对数正态'}
for fam in ['random_uniform','random_zipf','random_hotspot','random_lognormal']:
 r=next(r for r in families if r['family']==fam)
 interpretation.append(f'| {labels[fam]} | {r["cases"]} | {float(r["mean_points"]):.4f} | {float(r["cost_sum_ratio"]):.4f} |')
interpretation += ['', '这仍不能定位队友那次自测的具体低分原因；要复现该次结果，仍需它使用的程序版本、基线、命令和原始输出。', '']
text=text.replace('## 同伴版本更新','\n'.join(interpretation)+'\n## 同伴版本更新')
source_note=(f'\n结束时再次核对 GitHub：Vanius 分支已前进到 `{latest["latest_checked_commit"]}`，'
 '上述已测原纯算法、Best、Robust、AI2048 四份文件仍与本轮冻结源逐字节相同，当前主推与备选入口也相同，因此本轮测量仍对应这些方法的最新源码字节。'
 '数据分支仍为 `33ab5af`，liunian 分支仍为 `0c6d963`。见 [末次源码核对](latest_source_recheck.json)。\n')
text=text.replace('## 首位方法的退化案例',source_note+'\n## 首位方法的退化案例')
assert '每例累计 D 的均值（微秒）' in text and 'p_i = clip' in text and '持久工作目录' in text
path.write_text(text,encoding='utf-8')
history=load(O/'phase_authorizations.json');lease=O.parents[2]/'tmp/final50_formal_lease_1793335208.json';raw=lease.read_bytes();l=json.loads(raw)
if not any(r['phase']=='formal_window2' for r in history):
 history.append(dict(phase='formal_window2',lease=lease.name,lease_sha256=hashlib.sha256(raw).hexdigest(),
  runner_sha256=l['runner_sha256'],allowed_phases=l['allowed_phases'],result='700/700 valid;191 newly measured,509 reused;exit0'))
 save(O/'phase_authorizations.json',history)
assert len(list((O/'results').glob('*/result.json')))==700
print(json.dumps(dict(status='complete',valid=700,case_count=50,methods=14,repeats=1,latest_vanius_same_bytes=True,
 top_group=['VanBest','VanRobust'],derived=derived),ensure_ascii=False))
