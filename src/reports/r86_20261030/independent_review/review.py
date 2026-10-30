"""Independent metadata and synthetic checks; no native or input-body access."""
import sys,json,hashlib,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'tmp/r86_eval'))
import regression as r
import scoring as s
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def save(name,x):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
def reject(fn):
    try:fn()
    except (AssertionError,ValueError):return
    raise AssertionError('invalid contract accepted')
pins={p:digest(p) for p in ['tmp/r86_eval/release.json','tmp/r86_eval/regression.py','tmp/r86_eval/inventory.py','tmp/r86_eval/scoring.py','tmp/r86_eval/test_protocol.py','tmp/r86_eval/final/selection.json','tmp/r86_runner_review/review.json','tmp/r86_root_review/preflight.json','docs/superpowers/plans/2026-10-30-r86-final3-complete-regression.md']}
assert pins['tmp/r86_eval/release.json']=='30ab0c0dd7f7a0f2a9734867205c63270b4777e47eb8a409aecd2fa8e0cb054f'
assert pins['tmp/r86_eval/regression.py']=='85e25ff9ac7411fbabcca85700d22fed1d1f2af145858210f1cf139fa27f4856'
sel=read('tmp/r86_eval/final/selection.json');binding=read('tmp/r86_eval/methods.prepared.json')
r.verify_selection(sel,binding,read('tmp/r86_eval/final.inventory.json'))
old=read('tmp/r85_full_eval/dyna/selection.json');r.validate_reused_methods(old['methods'],sel['methods'])
assert binding==read('tmp/r85_full_eval/methods.prepared.json')
assert len(sel['cases'])==72 and sel['planned_cells']==576
assert sel['active_controller_budget_seconds']==650 and sel['official_per_case_seconds']==60
assert sel['repeats']==sel['parallelism']==1 and sel['no_retries']
assert all(c['input_path'].startswith('${WORKSPACE}<LOCAL_TEMP>') for c in sel['cases'])
assert sum(c['stats']['operations'] for c in sel['cases'])==22528629
closure=['tmp/r86_eval/regression.py','tmp/r86_eval/scoring.py','tmp/r86_eval/inventory.py','tmp/r84_full_eval_v2/inventory.py','tmp/r80_eval/experiment.py','tmp/r79_final_eval/process_helper.py','tmp/r79_final_eval/dependencies/evaluation/evaluate.py','tmp/r79_final_eval/dependencies/evaluation/scripts/audit_datasets.py','tmp/r79_final_eval/dependencies/evaluation/scripts/summarize_member_scores.py']
for p in closure:assert sel['dependencies'][p]==digest(p),p
assert set(old['dependencies'])<=set(sel['dependencies'])
for p in ['selection.json','rows.json','finalized_summary.json']:
    assert digest('tmp/r85_full_eval/dyna/'+p)==r.DYNA_PINS[p]
checks=[]
def fixture(n):
    cs=[dict(case_id=str(i),family='fixture',original_split='eval',group='fixture',stats=dict(operations=1,probe_count=1,penalty=3)) for i in range(n)]
    z=dict(mode='final',scope='synthetic',cases=cs,methods=copy.deepcopy(binding['methods']),dependencies={})
    rows=[dict(case_id=c['case_id'],method=m['name'],valid=True,status='PASS',metrics=dict(Total_Score=10 if m['name']=='Naive' else 12,Total_IO_Time=5 if m['name']=='Naive' else 7,Total_Decision_Time=2,Miss_Count=1,Hit_Count=0)) for c in cs for m in z['methods']]
    return z,rows
z,rows=fixture(72);raw=s.summarize(z,rows)
assert raw['complete'] and raw['per_case'][1]['score']==0 and abs(raw['per_case'][1]['raw_unclipped_points']+2)<1e-12
assert raw['per_case'][1]['physical']==10 and raw['per_case'][1]['D']==2
assert not s.summarize(z,rows[:-1])['complete']
bad=copy.deepcopy(rows);bad[-1]['valid']=False;assert not s.summarize(z,bad)['complete']
reject(lambda:s.summarize(z,rows+[rows[0]]))
bad=copy.deepcopy(rows);bad[0]['case_id']='extra';reject(lambda:s.summarize(z,bad))
assert s.score(0,10)==s.score(10,0)==0
assert s.ratio_stats([(str(i),i) for i in range(1,73)],72)['p90']==65
checks+=['full grid/missing/invalid/duplicate/extra','negative raw retained beneath zero clip','physical plus D accounting','zero-cost rule','nearest-rank P90']
a,ar=fixture(12);ds=s.summarize(a,ar);fs=copy.deepcopy(raw)
for x in ds['aggregate']:x['average_score']=2
for x in fs['aggregate']:x['average_score']=8
combined=r.combine_summaries(ds,fs)
assert all(x['equal_dataset_mean_score']==5 for x in combined['methods'])
assert combined['historical_dyna_reuse'] and not combined['dyna_remeasured_in_R86']
checks+=['50/50 dataset weighting not pooled 84','historical reuse explicitly labelled']
bad=copy.deepcopy(binding['methods']);bad[0]['binary_sha256']='0'*64
reject(lambda:r.validate_reused_methods(old['methods'],bad))
done=dict(status='ALL_CELLS_TERMINAL',planned=576,terminal=576,valid=576,error='after final row',changed_artifacts=[])
assert not s.finalize(raw,done)['complete']
checks+=['ELF dictionary mutation rejected','completion error rejects complete rows']
# Exercise the actual wrapper without spawning a process; preserve fixtures.
oldhere=r.HERE;r.HERE=OUT/'synthetic_last_cell';out=r.HERE/'final';out.mkdir(parents=True)
r.save(out/'selection.json',z)
def fake(mode):
    r.save(out/'rows.json',rows);r.save(out/'summary.json',raw)
    ok=dict(done,error=None,rows_sha256=r.sha(out/'rows.json'),summary_sha256=r.sha(out/'summary.json'))
    r.save(out/'completion.json',ok);r.save(out/'campaign.json',dict(selection_sha256=r.sha(out/'selection.json')))
    r.save(out/'cpu_released.json',dict(active_child_processes=0))
    raise RuntimeError('synthetic failure after complete rows')
try:
    try:r.execute_and_finalize('final',fake)
    except RuntimeError:pass
    else:raise AssertionError('failure swallowed')
    assert r.read(out/'completion_gate.json')['status']=='INCOMPLETE'
    assert not r.read(out/'finalized_summary.json')['complete']
finally:r.HERE=oldhere
checks+=['actual post-last-cell wrapper exception remains INCOMPLETE']
result=dict(status='PASS',blocking_findings=[],pins=pins,synthetic_checks=checks,execution_dependency_closure=closure,methods=binding['methods'],new_cases=72,new_cells=576,historical_reused_cases=12,historical_reused_cells=96,input_bodies_read=0,native_runs=0,compile_runs=0,scope='Static/source/small metadata and synthetic checks. Root independently rehashed actual inputs and ELF during prepare.',caveats=['Dyna D is historical R85 timing; final D is new R86 timing, not one simultaneous campaign.','Controller 650s is admission/process budget; setup/post-run hashes and cleanup may extend wall duration.','Raw grid complete is provisional; only completion_gate PASS and finalized_summary complete authorize reporting.','New PROBE streams retain exposed BUILD layouts; not untouched or independent of old workload design.'])
save('review.json',result)
(OUT/'REVIEW.md').write_text('# R86 独立静态复核\n\n结论：PASS，未发现阻止本轮执行的具体问题。\n\n核对新 3.0 固定提交的全部 72 例、八方法与 R85 完整 source/TU/ELF 字典相等、R85 dyna 12 例与同轮 Naive 原结果只复用。新执行 576 格，复用 96 格。依赖闭包包括原执行核、进程管理、解析器及其两个本地导入。Root 已另行完成真实输入和 ELF 重哈希，本次不重复大读取。\n\n独立 synthetic 覆盖缺失/失败/重复/额外格拒绝、物理成本加 D、零成本规则、负 raw 不被 clip 隐藏、最近秩 P90、数据集各 50% 权重、ELF 身份变化，以及最后一格已落盘后抛异常仍 INCOMPLETE。只有 finalized_summary 与 completion_gate 同时通过才能宣布完成。\n\n650 秒为执行循环的准入/进程预算，准备、收尾哈希及清理可能增加总墙钟；60 秒为每格上限。dyna 的 D 来自历史 R85，不能称全部成本同一时段重新测量。新流保留原 BUILD 布局，不能称完全未曝光独立数据。没有调度器运行、编译、输入全扫描或冻结文件修改。\n',encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=len(checks),review_sha256=digest('tmp/r86_independent_review/review.json'),markdown_sha256=digest('tmp/r86_independent_review/REVIEW.md'))))
