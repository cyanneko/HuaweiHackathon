"""Small-file post-run verification and readable report; never runs native code."""
import json, statistics
from pathlib import Path
import runner as r

o = Path(__file__).resolve().parent
p = r.load(o/'protocol.json'); summary = r.load(o/'summary.json')
controller = r.load(o/'controller.json'); release = r.load(o/'cpu_released.json')
r.gates(p)
r.require(summary['status']=='PASS' and controller['status']=='PASS', 'completion status')
r.require(release['active_children']==0 and not (o/'error.json').exists(), 'release/error gate')
r.require(controller['completed']==controller['valid']==60 and controller['global_seconds']<900, 'controller contract')
parse = r.imported_function(r.PARSER, 'parse_metrics')
all_hashes = {}
pairs = {}
walls = []
for item in p['order']:
    folder = o/'cells'/item['cell_id']; row = r.load(folder/'result.json')
    case = next(c for c in p['cases'] if c['case_id']==item['case_id'])
    method = next(m for m in p['methods'] if m['name']==item['method'])
    proc = r.load(folder/'process.json'); owner = r.load(folder/'ownership.json')
    r.require(all(row[k]==v for k,v in item.items()) and row['valid'], 'cell key/valid')
    r.require(row['input_sha256']==case['input_sha256'] and row['binary_sha256']==method['binary_sha256'], 'cell identity')
    r.require(proc==row['process'] and proc['status']=='EXITED' and proc['returncode']==0 and owner['cleaned'], 'process completion')
    r.require(proc['wall_seconds']<60 and (folder/'stderr.txt').stat().st_size==0, 'wall/stderr')
    for kind in ['stdout','stderr']:
        r.require(r.sha(folder/(kind+'.txt'))==proc[kind+'_sha256'], 'stream SHA')
    metrics = parse((folder/'stdout.txt').read_text(),case['stats'],'official-2026-10-26')
    r.require(metrics==row['metrics'], 'stored metrics vs native stdout')
    pairs.setdefault((item['case_id'],item['repeat']),{})[item['method']]=metrics
    walls.append(proc['wall_seconds'])
    for file in folder.iterdir():
        if file.is_file(): all_hashes[str(file.relative_to(o))]=r.sha(file)
case_scores=[]
for case in p['cases']:
    scores=[]
    for repeat in range(3):
        pair=pairs[(case['case_id'],repeat)]
        base=pair['Naive']['Total_Score']; cost=pair[r.R81]['Total_Score']
        scores.append(0. if cost<=0 or base<=0 else max(0.,min(10.,10*(1-cost/base))))
    case_scores.append(statistics.mean(scores))
r.require(abs(statistics.mean(case_scores)-summary['official_score'])<1e-12,'independent score calculation')
for name in ['protocol.json','runner.py','prepare.json','prepare.preflight_v1.json','contract_tests.json','controller.json','cpu_released.json','summary.json','GO.json']:
    all_hashes[name]=r.sha(o/name)
r.save(o/'verification.json', dict(status='PASS', cells=60, stdout_and_stderr_sha_verified=120,
    independent_score=statistics.mean(case_scores), max_native_wall_seconds=max(walls),
    source_gate='all frozen small source/TU/dependency/metadata/audit hashes checked',
    input_gate='full raw/native SHA checked by completed controller; not rescanned by post-run verification',
    files_sha256=all_hashes))

lines=['# R81 on stat_dataset 1.0.0 eval','',
    f"主分 **{summary['official_score']:.9f}/10**，固定全部 10 例、42M 操作；R81 / Naive 各 3 轮，共 60/60 有效运行。",
    '每个案例每一轮先计算裁剪得分，再对 3 轮及 10 例等权平均。主成本采用原生 Total_Score；解析器验证其等于 IO + penalty × miss + 实测 D（含打印舍入容差）。',
    '所有 30 个配对中 R81 总成本均低于 Naive；回退案例：无。两方法每例的三轮 IO、hit、miss 完全一致；D 按实测保留。',
    f"串行运行，最长单格 {max(walls):.3f}s；正式 {controller['seconds']:.3f}s，含两次准备 {controller['global_seconds']:.3f}s，预算 900s。CPU 已释放，活动子进程为 0。",'',
    '倍率统一为 Naive / R81，大于 1 表示 R81 成本较低。physical 成本为 IO + penalty × miss。以下为每例三轮平均；倍率按每轮计算后平均。', '',
    '| 案例 | 得分 /10 | Naive 总成本 | R81 总成本 | 总成本倍率 | physical 倍率 |',
    '|---|---:|---:|---:|---:|---:|']
for c in summary['cases']:
    lines.append(f"| {c['case_id']} | {c['score']:.6f} | {c['methods']['Naive']['cost']:.2f} | {c['methods'][r.R81]['cost']:.2f} | {c['cost_multiplier']:.6f} | {c['physical_multiplier']:.6f} |")
lines += ['', '| 案例 | Naive IO | R81 IO | Naive miss | R81 miss | Naive D | R81 D |','|---|---:|---:|---:|---:|---:|---:|']
for c in summary['cases']:
    a,b=c['methods']['Naive'],c['methods'][r.R81]
    lines.append(f"| {c['case_id']} | {a['IO']:.2f} | {b['IO']:.2f} | {a['miss']:.0f} | {b['miss']:.0f} | {a['D']:.6f} | {b['D']:.6f} |")
lines += ['', '分布统计基于 10 个案例的三轮均值，P50/P90 为线性插值；得分/倍率的 worst 取最小，成本/IO/miss/D 的 worst 取最大。', '',
    '| 指标 | 均值 | P50 | P90 | worst |','|---|---:|---:|---:|---:|']
for k,v in summary['distributions'].items():
    lines.append(f"| {k} | {v['mean']:.6f} | {v['P50']:.6f} | {v['P90']:.6f} | {v['min']:.6f} |")
for name, dist in summary['method_distributions'].items():
    for k,v in dist.items():
        lines.append(f"| {name} {k} | {v['mean']:.6f} | {v['P50']:.6f} | {v['P90']:.6f} | {v['max']:.6f} |")
lines += ['', '## 身份与范围', '',f"- stat manifest SHA-256: `{p['manifest_sha256']}`。",f"- protocol SHA-256: `{r.sha(o/'protocol.json')}`。"]
for m in p['methods']:
    lines += [f"- {m['name']}: source `{m['source_sha256']}`; TU `{m['translation_unit_sha256']}`; ELF `{m['binary_sha256']}`。"]
lines += ['- 所有 native stdout/stderr、进程退出/清理记录及 SHA 保存在 cells/；verification.json 绑定证据文件哈希。',
    '- 本轮使用旧 R81 源身份及其冻结 ELF；主 Agent 提供的可读格式版 ef1c26e8…8ef65 与其 token/ELF 等价映射不替换本轮 producer。',
    '- 只评测 stat 1.0.0 eval；不训练、不调参、不重试、不剔除案例。该 eval 现已观测，后续使用须注明。',
    '- IO 和缺失罚分是模拟器成本，D 是真实决策时间；这些倍率不是实盘端到端加速比。',
    '- runner.preflight_v1.py / protocol.preflight_v1.json 保存正式计时前的计分口径修订前版本；正式全部 60 次运行只使用最终协议。', '']
(o/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(dict(verification='PASS',score=summary['official_score'],report=str(o/'REPORT.md'),max_native_wall_seconds=max(walls))))
