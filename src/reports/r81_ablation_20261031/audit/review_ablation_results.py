"""Independent output-only audit of the frozen original and fixed-recovery batches."""
from pathlib import Path
import csv, hashlib, importlib.util, json, math, statistics, sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
ORIG=ROOT/'tmp/r81_ablation_20261031';REC=ROOT/'tmp/r81_ablation_recovery_20261031'
NAMES=['Naive','Full','FixedShare075','UnifiedSlow2048','NoPeriodicPrefetch','NoNextProtection','UnitMissCost','NoStructurePolicy','UniformOperatorMarginal']
COUNTS={'dyna':12,'final':72,'stat':10};LAST='eval_09_mixed_mixed_staggered'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def resolve(s):
    s=str(s).replace('\\','/')
    if sys.platform=='win32' and s.startswith('/mnt/'):s=s[5].upper()+':'+s[6:]
    p=Path(s);return p if p.is_absolute() else ROOT/p
def load(n,p):
    spec=importlib.util.spec_from_file_location(n,p);o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o);return o
roundoff=[]
def eq(a,b,p=''):
    if isinstance(a,dict) and isinstance(b,dict):
        assert set(a)==set(b),p
        for k in a:eq(a[k],b[k],p+'/'+str(k))
    elif isinstance(a,list) and isinstance(b,list):
        assert len(a)==len(b),p
        for i,(v,w) in enumerate(zip(a,b)):eq(v,w,p+'/'+str(i))
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool):
        if a!=b:
            assert (isinstance(a,float) or isinstance(b,float)) and math.isclose(a,b,rel_tol=2e-15,abs_tol=1e-9),(p,a,b)
            roundoff.append(dict(path=p,stored=a,recomputed=b))
    else:assert a==b,(p,a,b)
def score(c,b):return max(0.,min(10.,10.*(1-c/b))) if c>0 and b>0 else 0.
def ratio(a,b):return a/b if b>0 else None
def tails(pairs,planned):
    vv=sorted(v for _,v in pairs if v is not None)
    return dict(planned=planned,defined=len(vv),undefined=planned-len(vv),mean=statistics.mean(vv) if vv else None,
        p50=vv[math.ceil(.5*len(vv))-1] if vv else None,p90=vv[math.ceil(.9*len(vv))-1] if vv else None,
        worst=max(vv) if vv else None,worst_cases=[c for c,v in pairs if vv and v==max(vv)],
        wins=sum(v<1 for v in vv),ties=sum(v==1 for v in vv),losses=sum(v>1 for v in vv))
def fmt(v,n=9):return '—' if v is None else f'{v:.{n}f}'
def csvwrite(p,rows,fields):
    assert not p.exists(),str(p)
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

original_release=read(ORIG/'release.preparation.json');recovery_release=read(REC/'release.json')
assert sha(ORIG/'release.preparation.json')=='dee2bbf1afcbd66ffd4f3e8ccfdbf0f0373d8efb3af9fe5e9444dbed0fb5e267'
assert sha(REC/'release.json')=='f4e535d440ada5293eb1558b37c3965cbe867239576621a9e7adb58ccf9dfa65'
prep=read(ORIG/'cases.prepared.json')
inputs={str(resolve(c['input_path']).resolve()).lower() for v in prep.values() for c in v['cases']}
for release in [original_release,recovery_release]:
    for p,h in release['dependencies'].items():
        fp=resolve(p);assert str(fp.resolve()).lower() not in inputs,'No input-body reads by auditor'
        assert sha(fp)==h,p
for folder,relname in [(ORIG,'release.preparation.json'),(REC,'release.json')]:
    go,attempt=read(folder/'GO.json'),read(folder/'attempt.json')
    assert go['approved'] and go['release_sha256']==attempt['release_sha256']==sha(folder/relname)
    assert attempt['GO_sha256']==sha(folder/'GO.json')
old_done,new_done=read(ORIG/'attempt_completion.json'),read(REC/'attempt_completion.json')
assert old_done['status']=='INCOMPLETE' and not old_done['complete'] and old_done['active_child_processes']==0
assert old_done['completed_suites']==['dyna','final'] and not (ORIG/'publication.json').exists()
assert old_done['seconds']<2200 and not old_done['deadline_exceeded']
assert all(x['cleaned'] and x['alive_after_final_cleanup'] is False and x['cleanup_error'] is None for x in old_done['ownership'])
assert new_done['status']=='COMPLETE_FIXED_RECOVERY' and new_done['complete'] and new_done['active_child_processes']==0 and new_done['error'] is None
assert new_done['compile_runs']==0 and new_done['new_native_cells']==9 and new_done['seconds']<180
assert all(x['cleaned'] and x['alive_after'] is False for x in new_done['ownership'])
pub=read(REC/'publication.json');v=read(REC/'verification.json');mapping=read(REC/'source_mapping.json')
assert pub['status']=='PUBLISHED_VERIFIED_FIXED_RECOVERY' and pub['original_attempt_unchanged_incomplete'] and pub['seconds']<180
for key,file in [('attempt_completion_sha256','attempt_completion.json'),('verification_sha256','verification.json'),('source_mapping_sha256','source_mapping.json')]:assert pub[key]==sha(REC/file)
for p,h in pub['artifacts'].items():assert sha(ROOT/p)==h
assert v['status']=='PASS' and v['selected_cells']==846 and v['historical_control_count']==188 and v['compile_runs']==0
assert mapping['original_retained']==837 and mapping['recovery_replacement']==9 and mapping['excluded_original_lastcase_valid']==8
assert mapping['excluded_original_lastcase_timeout']==1 and mapping['total_native_attempts_across_campaigns']==855
methods=read(ORIG/'methods.prepared.json');assert [m['name'] for m in methods['methods']]==NAMES
mi={m['name']:m for m in methods['methods']}
for m in mi.values():
    assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
    for p,h in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(resolve(m[p]))==m[h]
assert mi['Full']['source_sha256']=='2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617'
assert mi['Full']['binary_sha256']=='bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1'
assert read(ORIG/'effectiveness.json')['status']=='PASS'
assert (ORIG/'effectiveness_run/stdout.txt').read_text(encoding='utf-8').strip()=='EFFECTIVENESS_PASS 9'
evdir=ROOT/'tmp/r79_final_eval/dependencies/evaluation';sys.path.insert(0,str(evdir))
parse=load('independent_ablation_parser',evdir/'evaluate.py').parse_metrics
sc=load('independent_ablation_scorer',ORIG/'scoring.py');assert sc.REFERENCES==NAMES
original_rows={};selections={};original_terminals={};checked_valid=0;checked_invalid=[];artifact_hashes={}

def audit_cell(folder,row,case,mode):
    global checked_valid
    assert read(folder/'result.json')==row and read(folder/'process.json')==row['process']
    assert row['input_sha256']==case['input_sha256'] and row['source_sha256']==mi[row['method']]['source_sha256'] and row['binary_sha256']==mi[row['method']]['binary_sha256']
    assert read(folder/'ownership.json')['cleaned']
    for kind in ['stdout','stderr']:assert sha(folder/(kind+'.txt'))==row['process'][kind+'_sha256']
    if row['valid']:
        assert row['status']=='PASS' and row['process']['status']=='EXITED' and row['process']['returncode']==0 and row['process']['wall_seconds']<60
        assert parse((folder/'stdout.txt').read_text(encoding='utf-8'),case['stats'],'official-2026-10-26')==row['metrics']
        checked_valid+=1
    else:
        assert row['metrics'] is None
        checked_invalid.append(dict(suite=mode,case_id=row['case_id'],method=row['method'],status=row['status'],process=row['process']))

for mode,count in COUNTS.items():
    f=ORIG/mode;sel,rows,term,raw,final,gate,cpu=[read(f/p) for p in ['selection.json','rows.json','completion.json','summary.json','finalized_summary.json','completion_gate.json','cpu_released.json']]
    assert sel['cases']==prep[mode]['cases'] and sel['methods']==methods['methods'] and len(sel['cases'])==count
    assert sel['planned_cells']==len(rows)==count*9 and sel['parallelism']==sel['repeats']==1 and not sel['historical_D_reused']
    ci={c['case_id']:c for c in sel['cases']};idx={(r['case_id'],r['method']):r for r in rows}
    assert len(idx)==len(rows) and set(idx)=={(c,n) for c in ci for n in NAMES}
    assert term['rows_sha256']==sha(f/'rows.json') and term['summary_sha256']==sha(f/'summary.json') and not term['changed_artifacts'] and term['error'] is None
    assert read(f/'campaign.json')['selection_sha256']==sha(f/'selection.json') and cpu['active_child_processes']==0 and cpu['status']=='RELEASED'
    eq(raw,sc.summarize(sel,rows),mode+'/original_summary')
    expected=sc.finalize(raw,term);expected['completion_guards']['controller_wrapper_returned']=True;expected['controller_wrapper_error']=None
    eq(final,expected,mode+'/original_final')
    assert gate['finalized_summary_sha256']==sha(f/'finalized_summary.json')
    if mode!='stat':assert final['complete'] and gate['status']=='PASS' and all(final['completion_guards'].values())
    else:assert not final['complete'] and final['aggregate'] is None and gate['status']=='INCOMPLETE' and term['valid']==89
    for row in rows:audit_cell(f/'cells'/f'{row["case_index"]:02d}_{row["method"]}',row,ci[row['case_id']],mode)
    original_rows[mode]=rows;selections[mode]=sel;original_terminals[mode]=term
    artifact_hashes[mode]={p:sha(f/p) for p in ['selection.json','rows.json','completion.json','summary.json','finalized_summary.json','completion_gate.json','cpu_released.json']}
assert checked_valid==845 and len(checked_invalid)==1
bad=checked_invalid[0];assert bad['suite']=='stat' and bad['case_id']==LAST and bad['method']=='UniformOperatorMarginal' and bad['status']=='CONTROLLER_WATCHDOG_INTERRUPTED'
assert bad['process']['status']=='TIMEOUT' and bad['process']['returncode']==-9 and bad['process']['timeout_seconds']<60
fresh=read(REC/'lastcase/rows.json');rs=read(REC/'lastcase/selection.json');frozen=read(REC/'selection.frozen.json')
assert rs==frozen and rs['cases']==[selections['stat']['cases'][9]] and rs['methods']==methods['methods'] and rs['original_rotation_shift']==0 and rs['no_compile']
assert len(fresh)==9 and {(r['case_id'],r['method']) for r in fresh}=={(LAST,n) for n in NAMES} and all(r['valid'] for r in fresh)
for r in fresh:audit_cell(REC/'lastcase/cells'/f'00_{r["method"]}',r,rs['cases'][0],'recovery')
rt=read(REC/'lastcase/completion.json');rraw=read(REC/'lastcase/summary.json');rf=read(REC/'lastcase/finalized_summary.json')
assert rt['terminal']==rt['valid']==rt['planned']==9 and rt['status']=='ALL_CELLS_TERMINAL' and rt['error'] is None and not rt['changed_artifacts']
assert rt['rows_sha256']==sha(REC/'lastcase/rows.json') and rt['summary_sha256']==sha(REC/'lastcase/summary.json')
eq(rraw,sc.summarize(rs,fresh),'recovery/raw');ex=sc.finalize(rraw,rt);ex['completion_guards']['controller_wrapper_returned']=True;eq(rf,ex,'recovery/final')
assert rf['complete'] and all(rf['completion_guards'].values())
assert read(REC/'lastcase/campaign.json')['selection_sha256']==sha(REC/'lastcase/selection.json')
selected={**original_rows,'stat':[r for r in original_rows['stat'] if r['case_id']!=LAST]+fresh}
assert len(selected['stat'])==90 and selected['stat']==read(REC/'merged_stat/rows.json')
assert sum(len(x) for x in selected.values())==846 and checked_valid==854
sm={(x['suite'],x['case_id'],x['method']):x for x in mapping['mapping']};assert len(sm)==846
lookup={};summaries={};per=[];suite_results={};groups=[];losses=[]
for mode,count in COUNTS.items():
    sel=selections[mode];rows=selected[mode];ci={c['case_id']:c for c in sel['cases']};idx={(r['case_id'],r['method']):r for r in rows}
    assert len(idx)==len(rows)==count*9 and set(idx)=={(c,n) for c in ci for n in NAMES}
    summary=sc.summarize(sel,rows);assert summary['complete'];summaries[mode]=summary
    if mode=='stat':eq(summary,read(REC/'merged_stat/summary.json'),'merged/stat')
    else:eq(summary,read(ORIG/mode/'summary.json'),mode+'/selected')
    for row in rows:
        key=(mode,row['case_id'],row['method']);lookup[key]=row;mp=sm[key]
        recovery=mode=='stat' and row['case_id']==LAST
        expected_path=(REC/'lastcase/cells'/f'00_{row["method"]}/result.json') if recovery else (ORIG/mode/'cells'/f'{row["case_index"]:02d}_{row["method"]}/result.json')
        assert resolve(mp['result_path'])==expected_path and read(expected_path)==row and mp['fresh_D']
        assert mp['origin']==('recovery_entire_last_case' if recovery else 'original_complete_selected_cell')
        assert mp['source_batch_selection_sha256']==sha(REC/'lastcase/selection.json' if recovery else ORIG/mode/'selection.json')
    agg={x['method']:x for x in summary['aggregate']};suite_results[mode]={}
    for name in NAMES:
        rr=[]
        for c in sel['cases']:
            cid=c['case_id'];met=idx[cid,name]['metrics'];nm=idx[cid,'Naive']['metrics'];fm=idx[cid,'Full']['metrics'];p=c['stats']['penalty']
            cost,naive,full=met['Total_Score'],nm['Total_Score'],fm['Total_Score'];physical=met['Total_IO_Time']+p*met['Miss_Count'];fullphysical=fm['Total_IO_Time']+p*fm['Miss_Count']
            out=dict(suite=mode,case_id=cid,original_split=c['original_split'],family=c['family'],method=name,status='PASS',valid=True,
                source_batch='recovery' if mode=='stat' and cid==LAST else 'original',cost=cost,naive_cost=naive,full_cost=full,
                score=score(cost,naive),raw_points=10*(1-cost/naive) if naive>0 else None,full_score=score(full,naive),
                IO=met['Total_IO_Time'],hit=met['Hit_Count'],miss=met['Miss_Count'],penalty=p,penalty_miss=p*met['Miss_Count'],physical=physical,D=met['Total_Decision_Time'],
                cost_ratio_Full=ratio(cost,full),physical_ratio_Full=ratio(physical,fullphysical),delta_cost=cost-full,
                delta_IO=met['Total_IO_Time']-fm['Total_IO_Time'],delta_miss=met['Miss_Count']-fm['Miss_Count'],delta_D=met['Total_Decision_Time']-fm['Total_Decision_Time'],
                physical_identical=met['Total_IO_Time']==fm['Total_IO_Time'] and met['Hit_Count']==fm['Hit_Count'] and met['Miss_Count']==fm['Miss_Count'])
            out['removal_score_loss']=out['full_score']-out['score'];per.append(out);rr.append(out)
            if name not in ['Naive','Full'] and out['delta_cost']>0:losses.append(out)
        a=agg[name];cs=tails([(r['case_id'],r['cost_ratio_Full']) for r in rr],count);ps=tails([(r['case_id'],r['physical_ratio_Full']) for r in rr],count)
        assert statistics.mean(r['score'] for r in rr)==a['average_score']
        for own,key in [(cs,'cost_ratio'),(ps,'physical_ratio')]:
            expect=a['references']['Full'][key]
            for k in ['mean','p50','p90','worst','worst_cases','wins','ties','losses']:eq(own[k],expect[k],mode+'/'+name+'/'+key+'/'+k)
        sr=dict(mean_score=a['average_score'],mean_raw_points=a['mean_raw_unclipped_points'],defined_naive=a['defined_naive_denominators'],undefined_naive=a['undefined_naive_denominators'],
            cost_ratio_Full=cs,physical_ratio_Full=ps,physical_identical_cases=sum(r['physical_identical'] for r in rr),
            IO_total_us=a['IO_total_us'],penalty_miss_total_us=a['penalty_miss_total_us'],D_total_us=a['D_total_us'],D_mean_us=a['D_mean_us'],
            mean_removal_score_loss=statistics.mean(r['removal_score_loss'] for r in rr),negative_raw_cases=sum(r['raw_points'] is not None and r['raw_points']<0 for r in rr))
        suite_results[mode][name]=sr
    for group,entries in summary['groups'].items():
        for a in entries:groups.append(dict(suite=mode,group=group,method=a['method'],cases=a['cases'],mean_score=a['average_score'],mean_raw_points=a['mean_raw_unclipped_points'],defined_naive=a['defined_naive_denominators'],undefined_naive=a['undefined_naive_denominators'],mean_cost=a['mean_cost'],mean_physical=a['mean_physical'],IO_total_us=a['IO_total_us'],penalty_miss_total_us=a['penalty_miss_total_us'],D_total_us=a['D_total_us'],D_mean_us=a['D_mean_us']))

for old in read(ORIG/'history.expected.json')['rows']:
    row=lookup[old['suite'],old['case_id'],old['method']];assert row['input_sha256']==old['input_sha256']
    c=next(c for c in selections[old['suite']]['cases'] if c['case_id']==old['case_id'])
    for kind in ['stdout','stderr']:assert sha(ROOT/old['historical_'+kind+'_path'])==old['historical_'+kind+'_sha256']
    hm=parse((ROOT/old['historical_stdout_path']).read_text(encoding='utf-8'),c['stats'],'official-2026-10-26')
    for key in ['Total_IO_Time','Hit_Count','Miss_Count']:
        assert hm[key]==old['metrics'][key]
        assert (abs(row['metrics'][key]-hm[key])<=.010001 if key=='Total_IO_Time' else row['metrics'][key]==hm[key])
combined=sc.combine(summaries['dyna'],summaries['final']);stored=read(REC/'provisional/combined_dataset_equal.json')
for k in combined:eq(stored[k],combined[k],'combined/'+k)
assert not stored['stat_mixed_into_primary'] and not stored['original_attempt_complete']
source_csv=list(csv.DictReader((REC/'provisional/per_case.csv').open(encoding='utf-8-sig',newline='')))
csvindex={(r['suite'],r['case_id'],r['method']):r for r in source_csv};assert len(source_csv)==len(csvindex)==846
for r in per:
    cr=csvindex[r['suite'],r['case_id'],r['method']]
    for k,col in [('cost','cost'),('IO','IO'),('D','D'),('miss','miss'),('hit','hit')]:assert float(cr[col])==r[k]
primary={r['method']:r for r in combined['methods']};pfull=primary['Full']['equal_dataset_mean_score']
fields=['suite','case_id','original_split','family','method','source_batch','status','valid','cost','naive_cost','full_cost','score','raw_points','full_score','removal_score_loss','IO','hit','miss','penalty','penalty_miss','physical','D','cost_ratio_Full','physical_ratio_Full','delta_cost','delta_IO','delta_miss','delta_D','physical_identical']
csvwrite(ORIG/'REVIEWED_PER_CASE.csv',per,fields)
csvwrite(ORIG/'REVIEWED_GROUPS.csv',groups,list(groups[0]))
csvwrite(ORIG/'REVIEWED_NEGATIVE_CASES.csv',losses,fields)
mechanisms={
'FixedShare075':('异质性自适应共享→固定0.75','不是无共享；保留异质性统计、快边际、全部样本；主hier与risk均固定share'),
'UnifiedSlow2048':('快边际半衰期256→2048','慢分区2048不变；risk128/512、coverage256与历史统计不变'),
'NoPeriodicPrefetch':('去周期预取动作','周期update/coverage/next采样保留；闭环后续miss与可见样本会改变'),
'NoNextProtection':('去next PROBE保护','同时去cycle跳过和一般priority+1e12；next采样及当前目标排除保留'),
'UnitMissCost':('异质IO/100代理成本→单位miss密度','priority=reuse/bytes，top4损失=Σpriority×bytes；字节容量和冷启动R≥W门仍保留'),
'NoStructurePolicy':('去scan/cycle决策','保留历史/后继/步长维护；同时关闭cycle预取例外；不是分别隔离scan和cycle'),
'UniformOperatorMarginal':('快算子边际→均匀1/K','慢条件分布、共享、快统计维护及risk算子信息保留')}

lines=['# 双时间尺度分层复用调度器：创新机制与消融独立复核报告','',
'最终分析含94例×9方法的846个有效计分单元，但来自两个预先冻结的批次。原始846格运行仍为INCOMPLETE，不能说原一次运行成功：原845格有效、1格局部预算截断；经明确授权，仅将最后一个stat用例的全部9方法同批重测，排除该用例原8格成功结果和1格失败结果。最终使用837格原结果+9格恢复结果，总计855次计分尝试。', '',
f'Full在旧dyna12/final72分别为{suite_results["dyna"]["Full"]["mean_score"]:.9f}和{suite_results["final"]["Full"]["mean_score"]:.9f}分；两套先各均分再50/50得到{pfull:.9f}分。合并来源的stat10独立为{suite_results["stat"]["Full"]["mean_score"]:.9f}分，不进入主分母。七个干预不是可相加的贡献拆分；有负向和零物理差异结果，均保留。最终算法仍为冻结Full，BuildBestFit不在本消融中，也不据消融自动换版。','',
'## 1. 证据完整性、失败及固定恢复','',
'|批次/数据|计划|有效|失败|状态|控制器时间/额度（秒）|','|---|---:|---:|---:|---|---:|']
for mode in COUNTS:
    t=original_terminals[mode];lines.append(f'|原批/{mode}|{t["planned"]}|{t["valid"]}|{t["planned"]-t["valid"]}|{"PASS" if mode!="stat" else "INCOMPLETE"}|{t["seconds"]:.3f}/{t["budget_seconds"]}|')
lines += [f'|恢复批/仅stat case09全部九法|9|9|0|COMPLETE_FIXED_RECOVERY|{new_done["seconds"]:.3f}/180|','',
f'原失败格为`{LAST}`的`UniformOperatorMarginal`：局部450秒预算只剩{bad["process"]["timeout_seconds"]:.6f}秒，watchdog以-9终止，stdout/stderr为空且无metrics。它不是已证明超过60秒单格限时的算法失败。原stat有90个terminal行、89个valid；ALL_CELLS_TERMINAL不等于全部有效，原completion_gate与aggregate=null保留不改。原全局耗时{old_done["seconds"]:.3f}/2200秒，未耗尽全局预算。','',
'恢复规则在GO前冻结：前9个stat用例81格不变；case09全部9格统一采用恢复批的新成本、新Naive和新D，原8个成功格也全部排除；不择优、不改算法、0次重新编译。原完整dyna108格与final648格不重跑。恢复批180秒包括输入/ELF核对、9格执行、审核与发布；此次通过。','',
'独立复核覆盖原845个有效stdout、原1个失败日志、恢复9个stdout的哈希/五指标，以及最终选用846格的唯一性、来源映射、188个同输入历史Full/Naive物理对照。原始C严格取stdout Total_Score；源/TU/ELF、两批GO、输出及发布绑定均核对。原批与恢复批活动子进程均为0，CPU已释放。独立复核没有读取输入正文、没有运行native。','',
'## 2. Naive对照、代码来源与能主张什么','',
'Naive是冻结的官方朴素策略：从驻留非空分区中排除当前目标，按data_size降序std::sort，依次落盘到空间足够；miss后LOAD目标；周期回调不主动调整。同大小保留该官方比较器行为，不另造最大ID等平局规则。它是本轮每个用例同批新测的分母，不复用历史D。源SHA为`f15181df02b7f36624a9d11507e3167ab70617f52e587ed7215bc058e07db6ea`。','',
'Full实际源为`tmp/r81_named_20261031/MySpillScheduler.cpp`，SHA `2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`，已发布代码commit为`3064e270fde0473810cd8c0e57b738ee48356254`、路径`submission/MySpillScheduler.cpp`。原算法、可读版和语义宏命名版已有预处理tokens/ELF等价证据；本轮Full ELF再次匹配`bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1`。所有方法CPU C++14、g++ -O2、无计时插桩。','',
'对外机制名称采用快算子边际、慢分区条件分布、异质性共享、回访风险、next保护/受限预取、有限子集逐出与结构回退，不用实验编号代替解释。源码能证明这些机制如何组合，消融能提供所选输入上的条件效果；不据此声称指数衰减、共享、预取或贪心本身首次原创，也不声称全局最优。没有开展新的文献优先权检索，代码机制与理论原创性严格区分。','',
'按用户提供截图要求，本报告给出具体方案/复杂度、同轮Naive对照与来源/改动解释。这里的输入是已观察本地合成数据，不等于组织方隐藏用例；本地实测不能替代组织方用例展示，创新评审是否成立与是否获得分值由评审决定，不承诺30分或隐藏集表现。','',
'## 3. 评分与统计口径','',
'C直接取stdout Total_Score；定义为模拟IO+输入penalty×Miss+本轮实测D。physical=IO+penalty×Miss用于分解；真实隐藏惩罚不在SystemState中，策略固定100微秒只是假设代理。D包括框架状态复制等调度计时，不是磁盘端到端耗时。','',
'逐例score=clip(10×(1−C/C_Naive),0,10)，C/Naive为非正时按冻结规则记0；raw points=10×(1−C/C_Naive)不截断，零分母显式未定义并计数。先对每套用例等权均分，再将dyna12与final72各权0.5，不能把84例池化平均；stat10单列。尾部使用nearest-rank ceil(q×n)，每个比值保留planned/defined/undefined。C比和physical比是逐例比值的均值，不是总成本之比。','',
'表中的“保留机制分数差”定义为Full−干预版；为正表示该干预在此口径下降分，为负表示干预版得分更高。它是一次条件移除效果，不是独立可相加的贡献、因果份额或新增点数。因截断和不同Naive权重，成本比均值与均分差可能方向不同；raw表揭示这些边界。单次D仅描述，统计维护仍保留，不能把D差叫作可删除模块的全部运行开销。','',
'## 4. 同轮Naive与全部方法得分','',
'|方法|dyna12 score|final72 score|主50/50 score|主50/50 raw points|stat10 score|stat10 raw points|主保留机制分数差Full−干预|','|---|---:|---:|---:|---:|---:|---:|---:|']
for n in NAMES:
    p=primary[n];s=suite_results['stat'][n];delta=pfull-p['equal_dataset_mean_score']
    lines.append(f'|{n}|{p["dyna_mean_score"]:.9f}|{p["final_mean_score"]:.9f}|{p["equal_dataset_mean_score"]:.9f}|{fmt(p["equal_dataset_raw_points"])}|{s["mean_score"]:.9f}|{fmt(s["mean_raw_points"])}|{delta:+.9f}|')
lines += ['', '## 5. 七个干预的准确语义与结果边界','',
'|干预|实际关闭/替换内容|仍保留什么|主50/50 Full−干预|stat Full−干预|','|---|---|---|---:|---:|']
for n,(change,remains) in mechanisms.items():lines.append(f'|{n}|{change}|{remains}|{pfull-primary[n]["equal_dataset_mean_score"]:+.9f}|{suite_results["stat"]["Full"]["mean_score"]-suite_results["stat"][n]["mean_score"]:+.9f}|')
lines += ['',
'快算子边际、异质成本项的移除在主口径上退化较明显；这支持它们在本冻结组合/输入上的条件作用，不代表可外推或将分差相加。固定共享在dyna优于Full、在final及stat低于Full；统一慢时标与去预取也存在数据集间方向不同的结果，不能只报有利一套。','',
'NoStructurePolicy的物理差异必须单独判读：下表按完整IO/hit/miss三项完全一致计数。若全相同，则本轮观察到的物理贡献为零；分数/D小差不计作结构机制的创新增益，也不能由输出相同反推该分支从未执行或对所有未来输入都无用。','',
'|干预|dyna物理相同/12|final物理相同/72|stat物理相同/10|','|---|---:|---:|---:|']
for n in NAMES[2:]:lines.append(f'|{n}|{suite_results["dyna"][n]["physical_identical_cases"]}|{suite_results["final"][n]["physical_identical_cases"]}|{suite_results["stat"][n]["physical_identical_cases"]}|')
lines += ['', '## 6. 每套raw、IO+miss与D完整分解','',
'IO、惩罚项、D均为本套所有用例之和，单位10^6微秒；它们是分解展示，C仍以原stdout为准。raw未定义和负raw例数显式保留。','',
'|数据集|方法|score均值|raw均值|raw已定义/未定义|raw负例|IO总量|penalty×Miss总量|D总量|','|---|---|---:|---:|---|---:|---:|---:|---:|']
for mode in COUNTS:
    for n in NAMES:
        s=suite_results[mode][n];lines.append(f'|{mode}|{n}|{s["mean_score"]:.9f}|{fmt(s["mean_raw_points"])}|{s["defined_naive"]}/{s["undefined_naive"]}|{s["negative_raw_cases"]}|{s["IO_total_us"]/1e6:.6f}|{s["penalty_miss_total_us"]/1e6:.6f}|{s["D_total_us"]/1e6:.6f}|')
lines += ['', '## 7. 成本比与物理比的尾部及所有负向方向','',
'以下比值均为方法/Full；胜表示<1，负表示>1。每套每法均保留，不能用一次D差异证明稳定时延优势。全部逐例成本坏例另见REVIEWED_NEGATIVE_CASES.csv；不只列最坏一例。','',
'|数据集|方法|比值|有效/未定义|均值|P50|P90|最坏|胜/平/负|最坏用例|','|---|---|---|---|---:|---:|---:|---:|---|---|']
for mode in COUNTS:
    for n in NAMES:
        for label,key in [('C','cost_ratio_Full'),('physical','physical_ratio_Full')]:
            s=suite_results[mode][n][key];lines.append(f'|{mode}|{n}|{label}|{s["defined"]}/{s["undefined"]}|{fmt(s["mean"])}|{fmt(s["p50"])}|{fmt(s["p90"])}|{fmt(s["worst"])}|{s["wins"]}/{s["ties"]}/{s["losses"]}|{", ".join(s["worst_cases"])}|')
lines += ['', '## 8. 分族与原始split','',
'完整family、原train/dev/holdout标签统计见REVIEWED_GROUPS.csv，保持每套内部均值；其数据没有回流训练。dyna原holdout已暴露，不能当成未见测试。主表不混其他成员数据、final新版本或BUILD实验。','',
'## 9. 逐例完整表（846行）','',
'每个方法/用例一行，失败原格不用于下表；stat case09九行统一来自恢复批。C、IO、惩罚项、D显示单位10^6微秒，计算使用原stdout全值；原精度及全部delta字段保存在REVIEWED_PER_CASE.csv。raw与比值未定义显示“—”。','',
'|数据集|用例|方法|批次|score|raw points|C|C/Full|IO|penalty×Miss|D|physical/Full|','|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for mode in COUNTS:
    order={c['case_id']:i for i,c in enumerate(selections[mode]['cases'])}
    for r in sorted([r for r in per if r['suite']==mode],key=lambda x:(order[x['case_id']],NAMES.index(x['method']))):
        lines.append(f'|{mode}|{r["case_id"]}|{r["method"]}|{r["source_batch"]}|{r["score"]:.9f}|{fmt(r["raw_points"])}|{r["cost"]/1e6:.6f}|{fmt(r["cost_ratio_Full"])}|{r["IO"]/1e6:.6f}|{r["penalty_miss"]/1e6:.6f}|{r["D"]/1e6:.6f}|{fmt(r["physical_ratio_Full"])}|')
lines += ['', '## 10. 实际算法与完整复杂度（预先完成的源码审计）','',
'令K为算子数、P为每算子分区数、N=KP。固定有效尺寸、合法索引、正带宽及单位成本浮点模型下，完整回调最坏O(N log(N+1))，常见单victim/top4命中路径O(N)，额外空间O(N)。固定查表初始化18,436个double（147,488字节）另列常数成本。下面保留逐部件审计，特别包括确认动作、观测步长表、结构分析、惰性概率初始化/epoch清零及动作整理，不能仅引用victim排序。','',
'行号对应预先逐行审计的可读源SHA ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65；语义命名源仅五宏机械重命名且已验证等价。源码审计阶段本身未运行调度器；本轮所有九法编译与tiny机制门已经另行通过。']
core=(OUT/'algorithm_and_complexity.md').read_text(encoding='utf-8');core=core[core.index('## 2. 真实活动路径'):core.index('## 8. 七方向')]
import re
core=re.sub(r'^## (\d+)\.',r'### 源码审计\1.',core,flags=re.M)
lines += ['',core,'','## 11. 结论边界与可交付材料','',
'最终Full对本轮同批Naive有上述可复核主分，但消融表并不保证七个设计在每套都增益：负向移除、无影响、raw损失和尾部已完整列出。NoStructure观察到的物理零差异如实记零，不包装为创新贡献。对方截图所需的说明与Naive对照已提供，但本地合成数据不替代组织方用例、没有首次原创/理论最优证据、没有隐藏集或创新加分保证。','',
'这份是固定恢复后、多批来源的完整分析；原attempt仍INCOMPLETE，不能改写成原一次846格成功。所有selected方法/用例只有一次被预定采用的D，原case09八条成功不用于挑选。没有后续算法或参数优化，没有引入BuildBestFit，没有自动替换最终main。','',
'独立复核JSON：../r81_ablation_audit_20261031/ablation_result_review.json。完整846行CSV：REVIEWED_PER_CASE.csv；所有成本坏例CSV：REVIEWED_NEGATIVE_CASES.csv；分族与split：REVIEWED_GROUPS.csv。原runner冻结产物和原stat nullaggregate均未改。原证据保存在本目录及../r81_ablation_recovery_20261031/；恢复publication绑定输出与source_mapping，逐格标明原批或恢复批。','',
'逐格原始指标/计数与输出哈希严格核对；聚合跨运行时求和末位差按相对2×10^-15、绝对10^-9容差核对，不改变显示位数。独立审计全过程0次native、0次输入正文扫描。','']
report=ORIG/'REVIEWED_REPORT.md';assert not report.exists();report.write_text('\n'.join(lines),encoding='utf-8')
review=dict(status='PASS_INDEPENDENT_MULTIBATCH_ANALYSIS_AUDIT',original_attempt_complete=False,original_attempt_valid=845,original_attempt_invalid=1,original_attempt_terminal=846,
    selected_valid_cells=846,selected_original=837,selected_recovery=9,excluded_original_valid=8,excluded_original_invalid=1,total_measurement_attempts=855,
    original_valid_raw_reparsed=845,recovery_valid_raw_reparsed=9,failed_raw_hashed=1,historical_controls_reparsed=188,
    original_release_sha256=sha(ORIG/'release.preparation.json'),recovery_release_sha256=sha(REC/'release.json'),recovery_publication_sha256=sha(REC/'publication.json'),
    source_mapping_sha256=sha(REC/'source_mapping.json'),authority_cost='stdout Total_Score; not reconstructed',input_body_scans=0,native_runs=0,
    reports={p.name:sha(p) for p in [report,ORIG/'REVIEWED_PER_CASE.csv',ORIG/'REVIEWED_GROUPS.csv',ORIG/'REVIEWED_NEGATIVE_CASES.csv']},
    original_failed_cell=bad,phase_artifact_hashes=artifact_hashes,suite_results=suite_results,primary_equal_dataset_results=primary,
    original_status_preserved='INCOMPLETE',stat_original_aggregate_preserved=None,multibatch_provenance_verified=True,raw_csv846_matches_metrics=True,
    no_structure_physical_same={mode:suite_results[mode]['NoStructurePolicy']['physical_identical_cases'] for mode in COUNTS},
    main_not_replaced=True,BuildBestFit_included=False,individual_removal_effects_additive=False,single_selected_D=True,
    float_aggregation_tolerance=dict(relative=2e-15,absolute=1e-9,last_bit_differences=roundoff),
    limits=['local observed synthetic datasets','no official hidden-case evidence','no originality or innovation-score guarantee','no stable timing superiority from single D','original attempt remains incomplete','no automatic promotion'])
(OUT/'ablation_result_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=review['status'],report=str(report),report_sha256=sha(report),selected_cells=846,raw_valid_outputs_reparsed=checked_valid,historical_controls=188,
    primary_scores={n:primary[n]['equal_dataset_mean_score'] for n in NAMES},stat_scores={n:suite_results['stat'][n]['mean_score'] for n in NAMES},
    no_structure_physical_identical=review['no_structure_physical_same']),ensure_ascii=False,indent=2))
