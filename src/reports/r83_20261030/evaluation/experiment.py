"""R83 frozen-method coverage diagnostic. Reuse execution only; score independently."""
from pathlib import Path
import copy,importlib.util,statistics
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r83_frozen_execution_core',ROOT/'tmp/r80_eval/experiment.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core);core.HERE=HERE
read,save,sha,path=core.read,core.save,core.sha,core.path
CORE_SHA='ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0'
PLAN='docs/superpowers/plans/2026-10-30-r83-coverage-panel.md'
PLAN_SHA='fc97bdffd6df2c068dde80b3813c865dea2e25f18869d3dca161a8990152d5c0'
AMENDMENT='docs/superpowers/plans/2026-10-30-r83-full-evaluation-amendment.md'
AMENDMENT_SHA='5e69b82e2f444f7452d4815fa6f094136b86ee97f5f4c3678af0b4879e52c893'
PARENT='R80_next_hier_fast100';R75='R75_dense_switch'
CANDIDATES=['R79_adaptive','R80_paired_hier_fast100','R81_op256_cond2048','R82_singlefit025','R82_write1']
NAMES=['Naive',R75,'R79_adaptive',PARENT,'R80_paired_hier_fast100','R81_op256_cond2048','R82_singlefit025','R82_write1']
DATA='tmp/r83_data_panel/data_manifest.json'
FRAMEWORK_SHA='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'

def score(cost,baseline):
    return max(0.,min(10.,10.*(1.-cost/baseline))) if cost>0 and baseline>0 else 0.

def summarize(selection,rows):
    cases=selection['cases'];names=[m['name'] for m in selection['methods']]
    index={(r['case_id'],r['method']):r for r in rows}
    assert len(index)==len(rows),'duplicate cell'
    expected={(c['case_id'],n) for c in cases for n in names}
    assert set(index)<=expected,'unknown cell'
    complete=bool(cases) and set(index)==expected and all(r['valid'] for r in rows)
    result=dict(complete=complete,phase=selection['mode'],scope=selection['scope'],planned_cells=len(expected),observed=len(rows),valid=sum(r['valid'] for r in rows),groups={},per_case=[],generation_accounting=selection.get('generation_accounting',{}),paired_bandwidth=[],lineage_statistics=[])
    result['exposure']='observed development validation; all eight frozen methods, not untouched evidence' if selection['mode']=='dev' else 'TRAIN coverage diagnostic; not official/member score'
    if not complete:return result
    assert 'Naive' in names and PARENT in names
    per={}
    for c in cases:
        cid=c['case_id'];penalty=c['stats']['penalty']
        naive=index[cid,'Naive']['metrics']['Total_Score'];parent=index[cid,PARENT]['metrics']
        parent_physical=parent['Total_IO_Time']+penalty*parent['Miss_Count']
        for name in names:
            m=index[cid,name]['metrics'];cost=m['Total_Score'];physical=m['Total_IO_Time']+penalty*m['Miss_Count']
            row=dict(case_id=cid,method=name,group=c['group'],family=c['family'],track=c['track'],lineage_id=c['lineage_id'],bandwidth_scale=c['bandwidth_scale'],block=c['block'],N=c['stats']['operations'],penalty=penalty,cost=cost,physical=physical,D=m['Total_Decision_Time'],score=score(cost,naive),raw_improvement=1.-cost/naive if naive>0 else None,ratio_to_Naive=cost/naive if naive>0 else None,ratio_to_parent=cost/parent['Total_Score'] if parent['Total_Score']>0 else None,physical_ratio_to_parent=physical/parent_physical if parent_physical>0 else None,D_ratio_to_parent=m['Total_Decision_Time']/parent['Total_Decision_Time'] if parent['Total_Decision_Time']>0 else None)
            row['score_delta_parent']=row['score']-score(parent['Total_Score'],naive)
            result['per_case'].append(row);per[cid,name]=row
    masks={'all':cases}
    for field,prefix in [('group','group:'),('track','track:'),('family','family:'),('bandwidth_scale','bandwidth:'),('lineage_id','lineage:')]:
        for value in sorted({c[field] for c in cases}):masks[prefix+str(value)]=[c for c in cases if c[field]==value]
    # Keep a direct phase-group alias for downstream reports.
    for value in sorted({c['group'] for c in cases}):masks[value]=[c for c in cases if c['group']==value]
    for group,cc in masks.items():
        entries=[]
        for name in names:
            pp=[per[c['case_id'],name] for c in cc];raw=[p['raw_improvement'] for p in pp if p['raw_improvement'] is not None]
            d=sum(p['D'] for p in pp);parent_d=sum(per[c['case_id'],PARENT]['D'] for c in cc)
            entries.append(dict(method=name,cases=len(cc),average_score=statistics.mean(p['score'] for p in pp),uncapped_sum=sum(p['score'] for p in pp),mean_unclipped_cost_reduction=statistics.mean(raw) if raw else None,mean_raw_unclipped_points=10*statistics.mean(raw) if raw else None,defined_naive_denominators=len(raw),mean_score_delta_parent=statistics.mean(p['score_delta_parent'] for p in pp),cost_to_parent=core.ratios([p['ratio_to_parent'] for p in pp]),physical_to_parent=core.ratios([p['physical_ratio_to_parent'] for p in pp]),ratio_to_Naive=core.ratios([p['ratio_to_Naive'] for p in pp]),D_total_us=d,D_mean_us=d/len(cc),D_ratio_parent=d/parent_d if parent_d>0 else None))
        result['groups'][group]=entries
    lineages=sorted({c['lineage_id'] for c in cases})
    planned_train=selection.get('planned_train_cases',cases if selection['mode']=='train' else [])
    planned_lineages=sorted({c['lineage_id'] for c in planned_train})
    if selection['mode']=='train':
        for lineage in planned_lineages:
            cc=[c for c in cases if c['lineage_id']==lineage];bybw={c['bandwidth_scale']:c for c in cc}
            assert len(bybw)==len(cc),'duplicate bandwidth in lineage'
            pair=dict(lineage_id=lineage,complete=set(bybw)=={1,64},present_scales=sorted(bybw),methods=[])
            if pair['complete']:
                low,high=bybw[1],bybw[64]
                assert low.get('body_sha256')==high.get('body_sha256') and low.get('operation_stream_sha256')==high.get('operation_stream_sha256'),'pair bodies differ'
                for name in names:
                    a,b=per[low['case_id'],name],per[high['case_id'],name]
                    pair['methods'].append(dict(method=name,low_case_id=low['case_id'],high_case_id=high['case_id'],score_delta_high_minus_low=b['score']-a['score'],raw_improvement_delta_high_minus_low=b['raw_improvement']-a['raw_improvement'] if a['raw_improvement'] is not None and b['raw_improvement'] is not None else None,cost_ratio_parent_delta_high_minus_low=b['ratio_to_parent']-a['ratio_to_parent'] if a['ratio_to_parent'] is not None and b['ratio_to_parent'] is not None else None,physical_ratio_parent_delta_high_minus_low=b['physical_ratio_to_parent']-a['physical_ratio_to_parent'] if a['physical_ratio_to_parent'] is not None and b['physical_ratio_to_parent'] is not None else None,D_delta_high_minus_low=b['D']-a['D'],low_score=a['score'],high_score=b['score']))
            result['paired_bandwidth'].append(pair)
    complete_pairs=sum(p['complete'] for p in result['paired_bandwidth'])
    for name in names:
        entries=[next(m for m in result['groups']['lineage:'+l] if m['method']==name) for l in lineages]
        lineage_scores=[m['average_score'] for m in entries]
        lineage_costs=[m['cost_to_parent']['mean'] for m in entries]
        result['lineage_statistics'].append(dict(method=name,actual_lineages=len(lineages),planned_train_lineages=len(planned_lineages),point_cases=len(cases),complete_bandwidth_pairs=complete_pairs,paired_change_denominator=complete_pairs,equal_lineage_mean_score=statistics.mean(lineage_scores),lineage_mean_score_p50=core.quant(lineage_scores,.5),lineage_mean_score_p90=core.quant(lineage_scores,.9),lineage_mean_score_worst=min(lineage_scores),lineage_mean_cost_to_parent=core.ratios(lineage_costs),point_equal_lineage_weights=selection['mode']=='train' and complete_pairs==len(planned_lineages)>0 and len(cases)==2*len(planned_lineages)))
    return result

def choose(summary):
    assert summary['complete'],'incomplete/invalid matrices cannot advance'
    entries={m['method']:m for m in summary['groups']['all']};choices=[]
    for name in CANDIDATES:
        assert name in entries
        m=entries[name];defined=m['cost_to_parent']['n']==m['cases']==m['defined_naive_denominators']
        guards=dict(all_parent_and_naive_denominators_defined=defined)
        if defined:guards.update(mean_score_strictly_above_parent=m['mean_score_delta_parent']>0,worst_cost_parent_le_1_25=m['cost_to_parent']['worst']<=1.25)
        choices.append(dict(method=name,eligible=all(guards.values()),guards=guards,mean_score=m['average_score'],score_delta_parent=m['mean_score_delta_parent'],worst_cost_parent=m['cost_to_parent']['worst'],D_total_us=m['D_total_us'],D_hard_veto=False))
    eligible=sorted([c for c in choices if c['eligible']],key=lambda x:(-x['mean_score'],x['D_total_us'],x['method']))
    return dict(complete=True,selected=[c['method'] for c in eligible[:2]],choices=choices,rule='five declared candidates only; same-run Naive mean score strictly above R80 hierarchy, all denominators defined, worst cost/parent<=1.25; top two by score then lower D then name; no old38 or D veto',reserved_dev_results_consulted=False,diagnostic_only_no_default_promotion=True)

def advance(summary,out):
    choice=choose(summary);choice['training_summary_sha256']=sha(out/'summary.json');save(out/'advance.json',choice)

def verify_cases(cases):
    assert len({c['case_id'] for c in cases})==len(cases),'duplicate case ID'
    assert len({c['input_sha256'] for c in cases})==len(cases),'duplicate input SHA'

def verify_dev_identity(tr,methods,data_digest,selected):
    assert 0<=len(selected)<=2 and len(set(selected))==len(selected) and all(n in CANDIDATES for n in selected)
    assert [m['name'] for m in methods]==NAMES,'user amendment requires all eight DEV methods'
    trained={m['name']:m for m in tr['methods']}
    for m in methods:assert m==trained[m['name']],'method identity changed after TRAIN'
    assert data_digest==tr['dependencies'][DATA],'data contract changed after TRAIN'

def verify_method(m):
    assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
    for file,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(m[file]))==m[key],m['name']+'/'+file
    source=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(source)==1 and core.hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==FRAMEWORK_SHA

def prepare(mode):
    assert mode in ['train','dev'] and not (HERE/mode/'selection.json').exists(),'selection is immutable'
    assert sha(ROOT/PLAN)==PLAN_SHA and sha(ROOT/'tmp/r80_eval/experiment.py')==CORE_SHA
    assert sha(ROOT/AMENDMENT)==AMENDMENT_SHA
    reference_file=ROOT/'tmp/r81_regression_eval/final/selection.json';reference=read(reference_file)
    assert reference['dependencies']['tmp/r80_eval/experiment.py']==CORE_SHA
    prodfile=ROOT/'tmp/r82_victim_search/producer.json';prod=read(prodfile);release=read(prodfile.parent/'release.json')
    assert prod['status']=='READY' and prod['framework_unchanged'] and release['status']=='RELEASED' and release['ready'] and release['final'] and release['active_child_processes']==0 and release['producer_sha256']==sha(prodfile)
    assert release['test_summary_sha256']==sha(prodfile.parent/'test_summary.json') and read(prodfile.parent/'test_summary.json')['status']=='PASS'
    method_map={m['name']:m for m in reference['methods']+prod['variants']}
    declared=read(HERE/'method_identities.json')['methods']
    assert [x['identity']['name'] for x in declared]==NAMES
    for entry in declared:
        assert method_map[entry['identity']['name']]==entry['identity']
        assert sha(ROOT/entry['source_artifact_path'])==entry['source_artifact_sha256']
    assert method_map[R75]['source_sha256']=='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
    assert method_map[PARENT]['source_sha256']=='0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d'
    datafile=ROOT/DATA;data=read(datafile);cfg=read(datafile.parent/'config.json');data_release=read(datafile.parent/'cpu_released.json')
    assert data_release['status']=='RELEASED' and data_release['active_child_processes']==0 and data_release['scheduler_runs']==0
    assert data['config_sha256']==sha(datafile.parent/'config.json') and data['selection_sha256']==sha(datafile.parent/'selection.json') and cfg['plan_sha256']==PLAN_SHA
    data_review=read(datafile.parent/'review.json')
    assert data_review['status']=='PASS' and data_review['data_manifest_sha256']==sha(datafile)
    assert data_review['generation_audit_summary_sha256']==sha(datafile.parent/'generation_audit_summary.json') and data_review['cpu_released_sha256']==sha(datafile.parent/'cpu_released.json')
    assert data['planned_cases']==18 and data['replacement_seeds']==0
    planned={c['case_id']:c for c in cfg['cases']};assert len(planned)==18
    allcases=data['cases'];verify_cases(allcases);assert all(c['case_id'] in planned for c in allcases)
    for c in allcases:
        assert c['status']=='FULL_INPUT_AUDIT_PASS' and c['validation'] and all(c['validation'].values())
        for key in ['split','group','track','lineage_id','bandwidth_scale','block','parameters']:assert c[key]==planned[c['case_id']][key]
        assert c['split'] in ['train','dev'] and c['stats']['operations']==150000
    train=[c for c in allcases if c['split']=='train'];dev=[c for c in allcases if c['split']=='dev']
    assert len(train)==data['train_cases'] and len(dev)==data['dev_cases'] and len(allcases)==data['case_count']
    assert not ({c['lineage_id'] for c in train}&{c['lineage_id'] for c in dev})
    missing=[cid for cid in planned if cid not in {c['case_id'] for c in allcases}]
    assert not missing or data['failures'],'missing generated cases must retain failure evidence'
    for check in data['pair_checks']:
        if check.get('complete'):assert check['only_bandwidth_header_diff'],check
    deps={}
    evaluator_config=core.OLD/'config.json'
    deps[str(evaluator_config.relative_to(ROOT)).replace('\\','/')]=sha(evaluator_config)
    for rel,digest in read(evaluator_config)['dependency_sha256'].items():
        frozen=core.OLD/'dependencies'/rel
        assert sha(frozen)==digest
        deps[str(frozen.relative_to(ROOT)).replace('\\','/')]=digest
    required=['tmp/r80_eval/experiment.py','tmp/r79_final_eval/process_helper.py','tmp/r79_final_eval/dependencies/evaluation/evaluate.py','tmp/r81_regression_eval/final/selection.json','tmp/r82_victim_search/producer.json','tmp/r82_victim_search/release.json','tmp/r82_victim_search/test_summary.json','tmp/r83_eval/experiment.py','tmp/r83_eval/test_protocol.py',PLAN,DATA]
    required+=['tmp/r83_data_panel/'+name for name in ['config.json','selection.json','commands.json','prior_registry.json','prepare_data.py','cpu_released.json','review.json','generation_audit_summary.json','artifacts.json']]
    required+=['tmp/r83_review/runner_review.json','tmp/r83_eval/release.json']
    required.append('tmp/r83_eval/method_identities.json')
    required.append(AMENDMENT)
    required+=['tmp/r82_eval/train/selection.json','tmp/r82_eval/train/summary.json','tmp/r81_eval/train/summary.json']
    for rel in required:deps[rel]=sha(ROOT/rel)
    own=read(HERE/'release.json');assert own['ready'] and own['final'] and own['runner_sha256']==sha(Path(__file__)) and own['test_protocol_sha256']==sha(HERE/'test_protocol.py')
    ownreview=read(ROOT/'tmp/r83_review/runner_review.json');assert ownreview['status']=='PASS' and ownreview['runner_sha256']==sha(Path(__file__))
    assert own['runner_review_sha256']==sha(ROOT/'tmp/r83_review/runner_review.json') and own['test_summary_sha256']==sha(HERE/'test_summary.json')
    assert own['method_identities_sha256']==sha(HERE/'method_identities.json')
    assert read(HERE/'test_summary.json')['status']=='PASS'
    if mode=='train':cases=copy.deepcopy(train);names=NAMES
    else:
        tr=read(HERE/'train/selection.json');decision=read(HERE/'train/advance.json');summary=read(HERE/'train/summary.json');completion=read(HERE/'train/completion.json')
        assert decision['training_summary_sha256']==sha(HERE/'train/summary.json') and completion['summary_sha256']==sha(HERE/'train/summary.json') and completion['rows_sha256']==sha(HERE/'train/rows.json')
        assert read(HERE/'train/campaign.json')['selection_sha256']==sha(HERE/'train/selection.json') and completion['valid']==completion['planned']==tr['planned_cells']
        expected=choose(summary);assert all(decision[k]==v for k,v in expected.items())
        cases=copy.deepcopy(dev);names=NAMES
        for name in ['selection.json','advance.json','summary.json','completion.json','campaign.json','rows.json']:deps['tmp/r83_eval/train/'+name]=sha(HERE/'train'/name)
    assert cases,'no valid cases for this phase'
    methods=[method_map[n] for n in names]
    if mode=='dev':verify_dev_identity(tr,methods,sha(datafile),decision['selected'])
    for m in methods:verify_method(m)
    for c in cases:
        c['input_path']=str(path(c.get('input_path_linux',c['input_path'])));c['metadata_path']=str(path(c['metadata_path']))
        assert path(c['input_path']).is_file() and sha(path(c['metadata_path']))==c['metadata_sha256']
    cases.sort(key=lambda c:core.hashlib.sha256(('r83-'+mode+'-order-v1'+c['case_id']).encode()).hexdigest())
    selection=dict(mode=mode,scope='R83 mixed dynamic/IID development coverage diagnostic; frozen historical methods, not official/member score or default promotion',cases=cases,methods=methods,dependencies=deps,planned_cells=len(cases)*len(methods),repeats=1,active_controller_budget_seconds=180,official_per_case_seconds=60,order='fixed case hash order; rotate method order left by case index',protocol='official-2026-10-26',percentiles='nearest-rank ceil(q*n)',score='case-mean-v1',gpu=False,D_policy='measured D included in score; no hard D veto',planned_train_cases=[c for c in cfg['cases'] if c['split']=='train'],generation_accounting=dict(expected_total=18,expected_train=12,expected_dev=6,valid_total=len(allcases),valid_train=len(train),valid_dev=len(dev),missing_case_ids=missing,failures=copy.deepcopy(data['failures']),status=data['status'],pair_checks=copy.deepcopy(data['pair_checks'])),model_boundary=data['model_boundary'],historical_train38_reference='tmp/r82_eval/train/summary.json',input_verification='full input audit inherited; prepare verifies metadata; frozen execution core hashes each input before and after execution',candidate_pool=CANDIDATES)
    selection.update(dev_method_policy='all eight frozen methods irrespective of TRAIN choose; user requested complete panel',dev_exposure='development validation becomes observed when executed; not untouched after run',train_choice_role='diagnostic only, does not gate or subset DEV',user_amendment_path=AMENDMENT,user_amendment_sha256=AMENDMENT_SHA)
    save(HERE/mode/'selection.json',selection);print(core.json.dumps(dict(prepared=mode,cases=len(cases),methods=len(methods),cells=selection['planned_cells'],selection_sha256=sha(HERE/mode/'selection.json'))))

if __name__=='__main__':
    p=core.argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summary']);p.add_argument('mode',choices=['train','dev']);p.add_argument('--cpu-window-released',action='store_true');args=p.parse_args()
    if args.action=='prepare':prepare(args.mode)
    elif args.action=='run':
        assert args.cpu_window_released;core.summarize,core.advance=summarize,advance;core.run(args.mode)
    else:
        result=summarize(read(HERE/args.mode/'selection.json'),read(HERE/args.mode/'rows.json'))
        target=HERE/args.mode/'summary.json'
        if target.exists():assert read(target)==result
        else:save(target,result)
        print(core.json.dumps(result,indent=2))
