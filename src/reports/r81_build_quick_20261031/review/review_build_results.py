"""Read-only final result audit. No input-body reads and no native execution."""
from pathlib import Path
import csv, hashlib, importlib.util, json, math, statistics, sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'tmp/r81_build_eval_20261031'
OUT = Path(__file__).resolve().parent
NAMES = ['Naive', 'Full', 'BuildBestFit']
COUNTS = {'dyna': 12, 'stat': 10}
EXPECTED_RELEASE = '78a17cf1ba3cbf30123375270c62dae475e41f5e349ec9d24ace236fe5d28347'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def resolve(s):
    s = str(s).replace('\\', '/')
    if sys.platform == 'win32' and s.startswith('/mnt/'):
        s = s[5].upper() + ':' + s[6:]
    p = Path(s)
    return p if p.is_absolute() else ROOT / p
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
def score(c, n): return max(0., min(10., 10.*(1.-c/n))) if c > 0 and n > 0 else 0.
aggregation_roundoff = []
def equivalent(x, y, path=''):
    if isinstance(x, dict) and isinstance(y, dict):
        assert set(x) == set(y), path
        for k in x: equivalent(x[k], y[k], path+'/'+str(k))
    elif isinstance(x, list) and isinstance(y, list):
        assert len(x) == len(y), path
        for i, (v,w) in enumerate(zip(x,y)): equivalent(v,w,path+'/'+str(i))
    elif isinstance(x, (int,float)) and isinstance(y, (int,float)) and not isinstance(x,bool) and not isinstance(y,bool):
        if x != y:
            assert isinstance(x,float) or isinstance(y,float), path
            assert math.isclose(x,y,rel_tol=2e-15,abs_tol=1e-9), (path,x,y)
            aggregation_roundoff.append(dict(path=path,stored=x,recomputed=y,absolute_difference=abs(x-y)))
    else: assert x == y, (path,x,y)
def stats(pairs):
    vv = sorted(v for _, v in pairs)
    return dict(mean=statistics.mean(vv), p50=vv[math.ceil(.5*len(vv))-1],
                p90=vv[math.ceil(.9*len(vv))-1], worst=max(vv),
                worst_cases=[c for c, v in pairs if v == max(vv)],
                wins=sum(v < 1. for v in vv), ties=sum(v == 1. for v in vv), losses=sum(v > 1. for v in vv))
def m(v): return f'{v/1e6:.6f}'

release = read(HERE/'release.preparation.json')
assert sha(HERE/'release.preparation.json') == EXPECTED_RELEASE
go, attempt, done, pub, verification = [read(HERE/p) for p in
    ['GO.json', 'attempt.json', 'attempt_completion.json', 'publication.json', 'verification.json']]
assert go['approved'] and go['release_sha256'] == attempt['release_sha256'] == EXPECTED_RELEASE
assert attempt['GO_sha256'] == sha(HERE/'GO.json') and attempt['no_resume'] and attempt['no_retries']
assert done['complete'] and done['status'] == 'COMPLETE' and done['error'] is None
assert done['completed_suites'] == ['dyna', 'stat'] and done['planned_cells'] == 66
assert done['active_child_processes'] == 0 and not done['deadline_exceeded'] and done['seconds'] < 900
assert all(o['cleaned'] and o['alive_after_final_cleanup'] is False and o['cleanup_error'] is None for o in done['ownership'])
assert pub['status'] == 'PUBLISHED_VERIFIED_COMPLETE' and pub['seconds'] < 900
assert pub['attempt_completion_sha256'] == sha(HERE/'attempt_completion.json')
assert pub['verification_sha256'] == sha(HERE/'verification.json')
assert verification['status'] == 'PASS' and verification['output_count'] == 66 and verification['historical_count'] == 44
assert not verification['historical_D_reused'] and not verification['inputs_rescanned']
for p, h in pub['artifacts'].items(): assert sha(ROOT/p) == h

prepared = read(HERE/'cases.prepared.json')
input_paths = {str(resolve(c['input_path']).resolve()).lower() for v in prepared.values() for c in v['cases']}
for p, h in release['dependencies'].items():
    fp = resolve(p)
    assert str(fp.resolve()).lower() not in input_paths, 'Static auditor refuses input-body hashes'
    assert sha(fp) == h, p
methods = read(HERE/'methods.prepared.json')
assert [x['name'] for x in methods['methods']] == NAMES
assert methods['flags'] == ['-std=c++14', '-O2'] and methods['full_ELF_matches_published']
for x in methods['methods']:
    for p, h in [('source_path','source_sha256'), ('translation_unit_path','translation_unit_sha256'), ('binary','binary_sha256')]:
        assert sha(resolve(x[p])) == x[h]
method_index = {x['name']: x for x in methods['methods']}
assert method_index['Full']['binary_sha256'] == 'bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1'
assert method_index['BuildBestFit']['source_sha256'] == 'b157c93d78928c237ba6050da33e0cd60ea9f58cd1991df7343c9a947851ce96'
assert sha(ROOT/'tmp/r81_named_20261031/MySpillScheduler.cpp') == method_index['Full']['source_sha256']

evdir = ROOT/'tmp/r79_final_eval/dependencies/evaluation'
sys.path.insert(0, str(evdir))
parser = load('independent_build_pinned_evaluator', evdir/'evaluate.py').parse_metrics
scorer = load('independent_build_frozen_scorer', HERE/'scoring.py')
assert scorer.REFERENCES == NAMES
result = {}; allrows = {}; case_stats = {}; artifacts = {}
for mode, count in COUNTS.items():
    folder = HERE/mode
    sel, rows, terminal, campaign, raw, final, gate, cpu = [read(folder/p) for p in
        ['selection.json','rows.json','completion.json','campaign.json','summary.json','finalized_summary.json','completion_gate.json','cpu_released.json']]
    assert sel['mode'] == mode and sel['cases'] == prepared[mode]['cases'] and sel['methods'] == methods['methods']
    assert len(sel['cases']) == count and sel['planned_cells'] == count*3
    assert sel['parallelism'] == sel['repeats'] == 1 and not sel['historical_D_reused'] and sel['global_wall_seconds'] == 900
    assert sel['active_controller_budget_seconds'] == {'dyna':500, 'stat':200}[mode]
    assert terminal['seconds'] <= sel['active_controller_budget_seconds']
    assert terminal['status'] == 'ALL_CELLS_TERMINAL' and terminal['terminal'] == terminal['valid'] == terminal['planned'] == count*3
    assert terminal['error'] is None and not terminal['changed_artifacts']
    assert terminal['rows_sha256'] == sha(folder/'rows.json') and terminal['summary_sha256'] == sha(folder/'summary.json')
    assert campaign['selection_sha256'] == sha(folder/'selection.json')
    equivalent(raw, scorer.summarize(sel, rows), mode+'/raw_summary')
    expected_final = scorer.finalize(raw, terminal)
    expected_final['completion_guards']['controller_wrapper_returned'] = True
    expected_final['controller_wrapper_error'] = None
    equivalent(final, expected_final, mode+'/final_summary')
    assert final['complete'] and all(final['completion_guards'].values())
    assert gate['status'] == 'PASS' and gate['controller_returned'] and gate['finalized_summary_sha256'] == sha(folder/'finalized_summary.json')
    assert cpu['status'] == 'RELEASED' and cpu['active_child_processes'] == 0
    for p, h in sel['dependencies'].items():
        assert str(resolve(p).resolve()).lower() not in input_paths
        assert sha(resolve(p)) == h
    input_gate = read(folder/'input_gate.json')
    assert input_gate['status'] == 'PASS_FULL_SHA_SIZE_METADATA' and input_gate['count'] == count
    assert {x['case_id'] for x in input_gate['cases']} == {x['case_id'] for x in sel['cases']}
    by_case = {c['case_id']: c for c in sel['cases']}
    index = {(r['case_id'], r['method']): r for r in rows}
    assert len(index) == len(rows) == count*3
    assert set(index) == {(c, n) for c in by_case for n in NAMES}
    for row in rows:
        c = by_case[row['case_id']]; met = row['metrics']; process = row['process']
        assert row['valid'] and row['status'] == 'PASS' and row['input_sha256'] == c['input_sha256']
        assert row['source_sha256'] == method_index[row['method']]['source_sha256']
        assert row['binary_sha256'] == method_index[row['method']]['binary_sha256']
        assert process['status'] == 'EXITED' and process['returncode'] == 0 and process['wall_seconds'] < 60
        cell = folder/'cells'/f'{row["case_index"]:02d}_{row["method"]}'
        assert read(cell/'result.json') == row and read(cell/'process.json') == process
        assert read(cell/'ownership.json')['cleaned']
        for kind in ['stdout','stderr']: assert sha(cell/(kind+'.txt')) == process[kind+'_sha256']
        assert parser((cell/'stdout.txt').read_text(encoding='utf-8'), c['stats'], sel['protocol']) == met
        allrows[mode,row['case_id'],row['method']] = row
        case_stats[mode,row['case_id']] = c['stats']
    cc = []
    for c in sel['cases']:
        cid = c['case_id']; mm = {n: index[cid,n]['metrics'] for n in NAMES}; penalty = c['stats']['penalty']
        for met in mm.values():
            assert met['Total_Score'] > 0 and all(math.isfinite(float(v)) for v in met.values())
        nf, ff, bb = [mm[n] for n in NAMES]
        physical_f = ff['Total_IO_Time'] + penalty*ff['Miss_Count']
        physical_b = bb['Total_IO_Time'] + penalty*bb['Miss_Count']
        row = dict(case_id=cid, original_split=c['original_split'], family=c['family'], penalty=penalty,
                   metrics=mm, full_score=score(ff['Total_Score'],nf['Total_Score']), build_score=score(bb['Total_Score'],nf['Total_Score']),
                   full_raw_points=10*(1-ff['Total_Score']/nf['Total_Score']), build_raw_points=10*(1-bb['Total_Score']/nf['Total_Score']),
                   cost_ratio=bb['Total_Score']/ff['Total_Score'], physical_ratio=physical_b/physical_f,
                   delta_cost=bb['Total_Score']-ff['Total_Score'], delta_io=bb['Total_IO_Time']-ff['Total_IO_Time'],
                   delta_miss=bb['Miss_Count']-ff['Miss_Count'], delta_penalty_miss=penalty*(bb['Miss_Count']-ff['Miss_Count']),
                   delta_D=bb['Total_Decision_Time']-ff['Total_Decision_Time'], delta_physical=physical_b-physical_f,
                   physical_identical=ff['Total_IO_Time']==bb['Total_IO_Time'] and ff['Hit_Count']==bb['Hit_Count'] and ff['Miss_Count']==bb['Miss_Count'])
        row['delta_score'] = row['build_score']-row['full_score']; cc.append(row)
    cost_stats = stats([(c['case_id'],c['cost_ratio']) for c in cc])
    physical_stats = stats([(c['case_id'],c['physical_ratio']) for c in cc])
    agg = {x['method']:x for x in final['aggregate']}
    for key, val in cost_stats.items(): assert agg['BuildBestFit']['references']['Full']['cost_ratio'][key] == val
    for key, val in physical_stats.items(): assert agg['BuildBestFit']['references']['Full']['physical_ratio'][key] == val
    assert statistics.mean(c['full_score'] for c in cc) == agg['Full']['average_score']
    assert statistics.mean(c['build_score'] for c in cc) == agg['BuildBestFit']['average_score']
    result[mode] = dict(case_count=count, valid_cells=count*3, full_mean_score=statistics.mean(c['full_score'] for c in cc),
        build_mean_score=statistics.mean(c['build_score'] for c in cc), mean_delta_score=statistics.mean(c['delta_score'] for c in cc),
        full_mean_raw_points=statistics.mean(c['full_raw_points'] for c in cc), build_mean_raw_points=statistics.mean(c['build_raw_points'] for c in cc),
        cost_ratio_to_Full=cost_stats, physical_ratio_to_Full=physical_stats,
        D_Full_total_us=sum(c['metrics']['Full']['Total_Decision_Time'] for c in cc),
        D_Build_total_us=sum(c['metrics']['BuildBestFit']['Total_Decision_Time'] for c in cc),
        identical_physical_case_count=sum(c['physical_identical'] for c in cc),
        total_delta_cost_us=sum(c['delta_cost'] for c in cc),total_delta_physical_us=sum(c['delta_physical'] for c in cc),
        negative_cases=[c for c in cc if c['cost_ratio'] > 1.], per_case=cc,
        controller_seconds=terminal['seconds'], max_cell_seconds=max(r['process']['wall_seconds'] for r in rows))
    artifacts[mode] = {p:sha(folder/p) for p in ['selection.json','rows.json','summary.json','completion.json','finalized_summary.json','completion_gate.json','cpu_released.json']}

history = read(HERE/'history.expected.json')['rows']; assert len(history) == 44
for old in history:
    row = allrows[old['suite'],old['case_id'],old['method']]
    assert row['input_sha256'] == old['input_sha256']
    for kind in ['stdout','stderr']: assert sha(ROOT/old['historical_'+kind+'_path']) == old['historical_'+kind+'_sha256']
    historical = parser((ROOT/old['historical_stdout_path']).read_text(encoding='utf-8'),case_stats[old['suite'],old['case_id']],'official-2026-10-26')
    for key in ['Total_IO_Time','Hit_Count','Miss_Count']:
        assert historical[key] == old['metrics'][key]
        assert (abs(row['metrics'][key]-historical[key]) <= .010001 if key == 'Total_IO_Time' else row['metrics'][key] == historical[key])
assert read(HERE/'effectiveness.json')['status'] == 'PASS'
assert (HERE/'effectiveness_red_run/stderr.txt').read_text(encoding='utf-8') == 'TINY_FAIL: minimum_single_victim_beyond_parent_top4\n'
assert (HERE/'effectiveness_run/stdout.txt').read_text(encoding='utf-8').strip() == 'TINY_BUILD_PASS cases=10'
for name in ['effectiveness_red_run','effectiveness_run']:
    proc = read(HERE/name/'process.json')
    for kind in ['stdout','stderr']: assert sha(HERE/name/(kind+'.txt')) == proc[kind+'_sha256']

lines = ['# BUILD 单次快速对照：独立复核报告', '',
    '本次结果不支持替换最终 Full：dyna12 的 BuildBestFit 平均成本比 Full 增加约0.01435%，3胜9负；stat10 平均成本比下降约0.08019%，7胜3负。两套结果方向不同、幅度很小；只运行一次，不能据此认定稳定优势。最终主算法保持 Full，原846格消融仍为HOLD。', '',
    '## 1. 实验身份与复核结论', '',
    '- 独立协议：Naive、Full、BuildBestFit，各在完整dyna12与stat10重新测量一次，共66格；串行CPU，未重试、未恢复、未挑选获益用例。dyna/stat分别报告，不混入旧final72或旧84例分母，也不计算22例池化平均或任何50/50总分。',
    f'- 正式发布门通过：66/66 PASS；44个同输入历史Full/Naive对照的IO、hit、miss匹配；原stdout/stderr哈希及官方五指标解析逐格核对；所有控制器、完整网格、依赖身份、进程清理和截止门通过。全程约{pub["seconds"]:.3f}秒，额度900秒；已记录活动子进程0与各套CPU RELEASED。独立复核没有运行任何native或读取输入正文。',
    '- 最终Full源：`2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`；已发布源commit `3064e270fde0473810cd8c0e57b738ee48356254`。Full本轮ELF为`bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1`，与已冻结最终算法一致。',
    '- 候选源：`b157c93d78928c237ba6050da33e0cd60ea9f58cd1991df7343c9a947851ce96`；ELF为`647cd05d5decd34a16ee71fffacccc08a3e2cd1f9e1fd6ad38725f44fc57f7e9`。编译g++11.4.0，`-std=c++14 -O2`；计时程序未插入检测代码。',
    f'- 绑定release：`{EXPECTED_RELEASE}`；publication：`{sha(HERE/"publication.json")}`。正式证据由publication绑定；本报告另写，不修改原provisional报告。', '',
    '## 2. 候选到底改了什么', '',
    '只在onMemoryOverflow中增加一个冷启动全BUILD分支：尚无已观测PROBE、下一条也不是PROBE、所有算子仍在BUILD且确需释放空间时，在驻留非空分区中排除当前INSERT目标，选择能单独满足缺口的最小字节分区；同大小按原遍历顺序。没有单个可行victim，或不满足上述条件，均回退原release。update、prune与record保留，成功快捷路径使概率缓存失效；其他PROBE/周期回调未改。',
    'tiny机制验证已通过：原Full在指定反例应失败的RED对照命中，候选GREEN通过10场景，包括最小单victim、平局、目标/已落盘排除、无单victim与PROBE/混合阶段回退，以及官方BUILD直接写盘和忽略BUILD LOAD的语义。它验证开关和机制，不证明平均收益。',
    '这是BUILD干预点的整段执行总效应。驻留选择会传播到后续PROBE；本轮没有分阶段成本计数或轨迹分解，因此下文IO/miss/D的差值不能直接叫“BUILD阶段节省”。该分支只保证局部最小单victim字节数，不保证未来成本或全局子集最优。', '',
    '## 3. 口径', '',
    '`C`直接取原程序stdout的`Total_Score`，不从已舍入的IO、D重建。官方定义是`C=IO+输入penalty×Miss+D`；`physical=IO+penalty×Miss`是模拟物理代价代理；D是本轮真实测量的调度决策耗时（包含框架状态快照），不是磁盘端到端运行时间。',
    '逐例分数`clip(10×(1-C/C_Naive),0,10)`，每套按用例等权平均；raw points不截断。成本比统计是逐例`C_Build/C_Full`的算术均值及nearest-rank分位数`ceil(q×n)`，不是总成本之比。小于1有利。胜负依据成本比严格比较，不设置事后阈值。差分统一为Build−Full。',
    '本次两方法所有例的相对Naive分数均为正，故本表各套平均raw与截断分数相同；这不表示Build在所有例上都优于Full。逐例负向差值完整保留。表内C/IO单位为10^6微秒；D单位毫秒，显示舍入不参与计算。', '',
    '## 4. 分数据集结果', '',
    '|数据集|Full均分|Build均分|Build−Full分数|平均C比|C胜/平/负|平均physical比|physical胜/平/负|D总量Full/Build（秒）|',
    '|---|---:|---:|---:|---:|---|---:|---|---:|']
for mode,s in result.items():
    a,b=s['cost_ratio_to_Full'],s['physical_ratio_to_Full']
    lines.append(f'|{mode}{s["case_count"]}|{s["full_mean_score"]:.9f}|{s["build_mean_score"]:.9f}|{s["mean_delta_score"]:+.9f}|{a["mean"]:.9f}|{a["wins"]}/{a["ties"]}/{a["losses"]}|{b["mean"]:.9f}|{b["wins"]}/{b["ties"]}/{b["losses"]}|{s["D_Full_total_us"]/1e6:.6f}/{s["D_Build_total_us"]/1e6:.6f}|')
lines += ['', '|数据集/比值|P50|P90|最坏|最坏用例|', '|---|---:|---:|---:|---|']
for mode,s in result.items():
    for label,key in [('C','cost_ratio_to_Full'),('physical','physical_ratio_to_Full')]:
        a=s[key];lines.append(f'|{mode}/{label}|{a["p50"]:.9f}|{a["p90"]:.9f}|{a["worst"]:.9f}|{", ".join(a["worst_cases"])}|')
lines += ['', 'dyna的物理指标也呈3胜9负，平均physical比增加约0.01326%；本轮D总量由29.790739秒增至32.355096秒。stat的physical为6胜1平3负，平均比下降约0.07865%；本轮D总量由11.138209秒增至11.209250秒。有一例physical完全相同而C因D不同变化，不能把这一差异写成物理收益。单次D差异只作描述，不作显著性或稳定速度主张。', '',
    '## 5. 全部成本坏例（Build相对Full）', '',
    '|数据集|用例|C比|成本变化%|分数变化|IO变化（10^6 µs）|Miss变化|惩罚项变化（10^6 µs）|D变化（ms）|', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
for mode,s in result.items():
    for c in sorted(s['negative_cases'], key=lambda x:x['cost_ratio'], reverse=True):
        lines.append(f'|{mode}|{c["case_id"]}|{c["cost_ratio"]:.9f}|{100*(c["cost_ratio"]-1):+.6f}|{c["delta_score"]:+.9f}|{c["delta_io"]/1e6:+.6f}|{c["delta_miss"]:+d}|{c["delta_penalty_miss"]/1e6:+.6f}|{c["delta_D"]/1000:+.3f}|')
lines += ['', '## 6. 逐例完整对照', '']
for mode,s in result.items():
    lines += [f'### {mode}：{s["case_count"]}例', '',
        '|用例|Naive C|Full C|Build C|Build/Full C|Full分数|Build分数|分数差|raw Full/Build|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for c in s['per_case']:
        mm=c['metrics'];lines.append(f'|{c["case_id"]}|{m(mm["Naive"]["Total_Score"])}|{m(mm["Full"]["Total_Score"])}|{m(mm["BuildBestFit"]["Total_Score"])}|{c["cost_ratio"]:.9f}|{c["full_score"]:.9f}|{c["build_score"]:.9f}|{c["delta_score"]:+.9f}|{c["full_raw_points"]:.9f}/{c["build_raw_points"]:.9f}|')
    lines += ['', '|用例|penalty（µs/缺失）|IO Full/Build（10^6 µs）|Hit Full/Build|Miss Full/Build|physical比|D Full/Build（ms）|', '|---|---:|---:|---:|---:|---:|---:|']
    for c in s['per_case']:
        ff,bb=c['metrics']['Full'],c['metrics']['BuildBestFit']
        lines.append(f'|{c["case_id"]}|{c["penalty"]}|{m(ff["Total_IO_Time"])}/{m(bb["Total_IO_Time"])}|{ff["Hit_Count"]}/{bb["Hit_Count"]}|{ff["Miss_Count"]}/{bb["Miss_Count"]}|{c["physical_ratio"]:.9f}|{ff["Total_Decision_Time"]/1000:.3f}/{bb["Total_Decision_Time"]/1000:.3f}|')
    lines += ['']
lines += ['## 7. 解释与限制', '',
    '本轮是一个预先固定候选的一次完整快速实验，结果具有方向相反的小幅变化，不能据此宣称整体优化。该候选与Full之间的唯一代码干预在冷启动BUILD分支，但收益/退化是闭环执行到结束的效应；没有测到BUILD/PROBE分别的成本，也没有统计该分支在每例中具体触发了多少次。',
    'dyna保留原train/dev/holdout标签，但已暴露，不能当作未见盲测；stat同样是已观察的本地合成数据。没有新训练、参数搜索或自动晋升。本地合成对照不能替代组织方用例展示，不能保证隐藏用例表现、真实磁盘端到端加速或创新加分。',
    '最终Full和已发布submission保持不替换。原九方法×94例的846格消融是另一协议，仍HOLD；本报告没有替它填补任何格，也没有把这次dyna/stat分母混入旧dyna/final的50/50口径。', '',
    '## 8. 证据文件', '',
    '- 发布绑定：`publication.json`、`attempt_completion.json`、`verification.json`。',
    '- 每套：`dyna/`、`stat/`下的selection、rows、completion、finalized_summary、completion_gate、cpu_released，以及cells原stdout/stderr/process/ownership。',
    '- 原始输出哈希、逐格指标与计数严格一致；聚合重算中求和的末位浮点差异按相对2×10^-15、绝对10^-9的容差核对，不改变任何报告位数。',
    '- 原完整CSV：`provisional/per_case.csv`；独立审计JSON：`../r81_ablation_audit_20261031/build_result_review.json`。',
    '- 本报告由独立复核者根据原输出另写，未修改runner原报告。', '']
report = HERE/'REVIEWED_REPORT.md'; assert not report.exists(), 'Do not silently overwrite a reviewed report'
report.write_text('\n'.join(lines), encoding='utf-8')
review = dict(status='PASS_INDEPENDENT_RESULT_AUDIT', input_body_scans=0, native_runs=0,
    release_sha256=EXPECTED_RELEASE, publication_sha256=sha(HERE/'publication.json'),
    attempt_completion_sha256=sha(HERE/'attempt_completion.json'), verification_sha256=sha(HERE/'verification.json'),
    complete_cells=66, historical_physical_controls_reparsed=44, all_raw_outputs_reparsed_and_hashed=True,
    authority_cost='stdout Total_Score', output_metrics_reconstructed_for_cost=False,
    main_final_unchanged=True, original_ablation_846_status='HOLD', final_algorithm_replaced=False,
    single_D_measurement=True, phase_costs_measured=False, groups_kept_separate=['dyna12','stat10'],
    pooled_22_or_old_84_used=False, results=result, phase_artifacts=artifacts,
    reviewed_report_path=str(report), reviewed_report_sha256=sha(report),
    process_cleanup_source='frozen helper ownership records and attempt final group rechecks; no native rerun by auditor',
    limits=['local observed synthetic data','single repeat descriptive D','cold BUILD intervention total effect only','no statistical significance claim','no automatic promotion','no hidden official case evidence'])
review['aggregation_float_check'] = dict(relative_tolerance=2e-15,absolute_tolerance=1e-9,
    differing_last_bit_fields=aggregation_roundoff,raw_metrics_strict_equality=True,output_hashes_strict_equality=True)
(OUT/'build_result_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=review['status'],cells=66,history=44,report=str(report),report_sha256=sha(report),
    summary={k:{q:v[q] for q in ['full_mean_score','build_mean_score','mean_delta_score','cost_ratio_to_Full','physical_ratio_to_Full','identical_physical_case_count']} for k,v in result.items()}),ensure_ascii=False,indent=2))
