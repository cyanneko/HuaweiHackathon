"""Build the concise Team 19 demonstration from fixed local evidence."""
from pathlib import Path
import json
from build_offline import build_offline
ROOT=Path(__file__).parent
D=ROOT/'dist'
data=json.loads((D/'assets/demo-results.json').read_text())
names={'Full':'完整算法','UniformOperatorMarginal':'算子边际改为均匀','UnitMissCost':'改为单位 Miss 代价','UnifiedSlow2048':'算子也改为慢速更新','FixedShare075':'共享固定为 0.75','NoNextProtection':'去 next 保护','NoPeriodicPrefetch':'去周期预取','NoStructurePolicy':'去扫描 / 循环决策'}
order=list(names)
rows=[]
for name in order:
 r=next(x for x in data['ablations'] if x['method']==name)
 cells=[names[name]]+[f'{r[k]:.4f}' for k in ['dyna12_score','final72_score','equal_dataset_score','stat10_score']]+['—' if name=='Full' else f'{r["score_gap"]:.4f}']
 rows.append('<tr'+(' class="full-row"' if name=='Full' else '')+'>'+''.join(f'<td>{x}</td>' for x in cells)+'</tr>')
html=(ROOT/'demo.html').read_text().replace('%%ABLATION_ROWS%%',''.join(rows)).replace('%%DEMO_DATA%%',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
assert '%%' not in html
(D/'index.html').write_text(html,encoding='utf-8')
build_offline()
print('Built five-section demonstration and standalone offline HTML.')
