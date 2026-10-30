"""Saved native Q_R75 evidence audit and label export; no new branch execution."""
from collections import Counter,defaultdict
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import struct

OUT=Path(__file__).resolve().parent
WS=OUT.parents[2]
STAGE=WS/'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030/corner_r75_v1'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def main():
    config=read(OUT/'config.json');report=read(OUT/'report.json');selection=read(OUT/'selection.json')
    results=read(OUT/'results.json');baseline_reports=read(OUT/'baseline_reports.json')
    assert report['status']=='complete' and report['fatal_error'] is None
    assert sha(OUT/'config.json')==report['config_sha256']
    assert sha(STAGE/'teacher_handoff.json')==config['teacher_handoff_sha256']
    handoff=read(STAGE/'teacher_handoff.json');entries={row['case_id']:row for row in handoff['cases']}
    assert sha(STAGE/'config.json')==config['handler_config_sha256']==handoff['config_sha256']
    assert sha(STAGE/'source_manifest.json')==handoff['source_manifest_sha256']
    for name,expected in read(STAGE/'source_manifest.json')['sources'].items():assert sha(STAGE/name)==expected
    assert sha(handoff['adapter_binary_windows'])==handoff['adapter_binary_sha256']
    for name,expected in config['sources'].items():assert sha(WS/name)==expected,name
    assert selection['selection_hash']==digest(selection['anchors'])
    assert len(results)==len(selection['anchors'])==16
    labels=[];details=[];hash_checks=0;forced_count=0;alias_conflicts=0;zero_wins=zero_losses=zero_ties=0
    grouped=defaultdict(list)
    for result,anchor in zip(results,selection['anchors']):
        assert result['anchor']==anchor and result['complete_matrix'] and result['control_valid']
        cid=anchor['case_id'];entry=entries[cid]
        assert entry['split']=='train' and sha(entry['input_path_windows'])==anchor['input_sha256']
        assert sha(entry['baseline_trace_windows'])==entry['parity']['trace_sha256']
        snapshot=anchor['anchor_snapshot'];initial=anchor['initial_ledger']
        assert digest(snapshot)==anchor['anchor_snapshot_sha256']
        assert all(snapshot[key]==initial[other] for key,other in [('write','write_bytes'),('read','read_bytes'),('miss','misses'),('hit','hits')])
        with Path(entry['input_path_windows']).open(encoding='utf-8') as source:
            k,p,m,w,r,pen=map(int,source.readline().split())
        assert (k,p,m,w,r,pen)==(8,64,67108864,100,80,100)
        assert initial['G']==initial['write_bytes']*r+initial['read_bytes']*w+pen*initial['misses']*w*r
        native=anchor['native_anchor'];ai=anchor['r75_index']
        assert anchor['plans'][ai]['actions']==native['actions']
        assert native['q']==snapshot['hit']+snapshot['miss']
        assert len({frozenset(plan['spill']) for plan in anchor['plans']})==len(anchor['plans'])
        assert anchor['selection_hash']==digest([config['anchor_seed'],anchor['input_sha256'],
                anchor['callback_index'],native['kind'],anchor['raw'],anchor['stage']])
        assert len(result['branches'])==len(anchor['plans'])
        values=[];export_plans=[];groups={}
        for pi,(plan,branch) in enumerate(zip(anchor['plans'],result['branches'])):
            folder=OUT/'runs'/anchor['anchor_id']/('p%02d'%pi)
            assert read(folder/'result.json')==branch
            assert branch['status']=='complete' and branch['plan_index']==pi and branch['override_count']==1
            assert branch['actions']==plan['actions'] and branch['initial_ledger']==initial
            assert branch['native_binary_sha256']==handoff['adapter_binary_sha256']
            assert branch['reached_eof'] and branch['full_physical_entry_hashes_compared']
            ends=re.findall(r'\bHANDLER_END\s+(\d+)\s+(\d+)',(folder/'stderr.log').read_text(encoding='utf-8',errors='replace'))
            assert ends==[(str(branch['callbacks']),'1')]
            force=(folder/'force.txt').read_text(encoding='utf-8').split()
            header=[native[key] for key in ('index','kind','op','pid','need','q','physical_hash','private_pre_hash')]+[len(plan['actions'])]
            expected=[str(item) for item in header]+[str(item) for action in plan['actions'] for item in action]
            assert force==expected and sha(folder/'force.txt')==branch['force_sha256']
            assert sha(folder/'native.trace')==branch['native_trace_sha256'];hash_checks+=1
            final=branch['final_ledger'];delta=branch['cost']['delta_ledger']
            assert all(final[key]-initial[key]==delta[key] for key in initial)
            g=delta['write_bytes']*r+delta['read_bytes']*w+pen*delta['misses']*w*r
            assert g==delta['G']==branch['cost']['G_delta']
            assert final['G']==final['write_bytes']*r+final['read_bytes']*w+pen*final['misses']*w*r
            assert sha(branch['full_witness_path'])==branch['full_witness_sha256'];hash_checks+=1
            witness=read(branch['full_witness_path']);assert len(witness)==branch['callbacks']
            suffix=witness[anchor['callback_index']:]
            assert suffix[0]['raw']==anchor['raw'] and suffix[0]['stage']==anchor['stage']
            assert suffix[0]['actions']==plan['actions']
            if pi==ai:
                assert branch['baseline_control'] and branch['baseline_control_full_trace_parity']
                assert branch['native_trace_sha256']==entry['parity']['trace_sha256']
                assert final==anchor['baseline_final_ledger'] and g==anchor['baseline_suffix_G']
            forced_count+=1;values.append(g)
            item=copy.deepcopy(plan)
            item.update(cost=dict(status='complete',G_delta=g,write_bytes=delta['write_bytes'],
                                  read_bytes=delta['read_bytes'],misses=delta['misses'],
                                  suffix_sha256=digest(suffix),full_witness_path=branch['full_witness_path'],
                                  full_witness_sha256=branch['full_witness_sha256'],
                                  native_trace_path=str(folder/'native.trace'),native_trace_sha256=branch['native_trace_sha256'],
                                  actual_native_execution=True,independent_python_physical_hash_and_ledger_parity=True,
                                  override_count=1,private_post_is_pre_engine=True),valid_cost=True)
            export_plans.append(item)
            groups.setdefault(struct.pack('<32f',*plan['x']),set()).add(g)
        low=min(values);scale=max(values)-low
        for plan,g in zip(export_plans,values):
            plan.update(regret_integer=g-low,target=float(Fraction(g-low,scale)) if scale else 0.)
        best=min(range(len(values)),key=lambda i:(values[i],anchor['plans'][i]['tie']))
        zero=min(range(len(values)),key=lambda i:(anchor['plans'][i]['x'][13],anchor['plans'][i]['tie']))
        assert result['best_plan_index']==best and result['best_G']==low
        assert result['r75_first_action_G']==values[ai] and result['regret_G']==values[ai]-low
        zg=values[zero]-values[ai];zero_wins+=zg<0;zero_losses+=zg>0;zero_ties+=zg==0
        conflicts=sum(len(value)>1 for value in groups.values());alias_conflicts+=conflicts
        label=dict(schema_version=1,label_protocol_version='corner-true-native-r75-one-deviation-v1',
                   case_id=cid,split='train',family=entry['mechanism'],seed=entry['parameters']['seed'],
                   pressure=entry['parameters']['pressure'],input_sha256=anchor['input_sha256'],
                   anchor_snapshot=snapshot,anchor_snapshot_sha256=anchor['anchor_snapshot_sha256'],
                   callback_index=anchor['callback_index'],raw=anchor['raw'],stage=anchor['stage'],
                   rollin='actual_frozen_R75_with_true_periodic_actions',continuation='native-r75-propose-once-commit-actual-v1',
                   candidate_pool_version=anchor['pool_version'],observer_version=anchor['observer_version'],
                   feature_version=anchor['feature_version'],feature_names=anchor['feature_names'],
                   label_kind='fixed_true_R75_native_complete_suffix_cost',r75_plan_index=ai,
                   r75_action_key=anchor['plans'][ai]['action_key'],integer_gap_scale=scale,
                   normalization='integer_subtraction_before_state_maxgap',all_cost_tie=scale==0,
                   conflicting_identical_feature_groups=conflicts,plans=export_plans,
                   initial_ledger=initial,anchor_miss_already_counted=native['kind']=='M',
                   R75_private_state_source='full native input-prefix replay, not Python observer or private-state port',
                   private_post_is_pre_engine=True,formal_D=None)
        labels.append(label)
        detail=dict(anchor_id=anchor['anchor_id'],case_id=cid,kind=native['kind'],raw=anchor['raw'],plans=len(values),
                    r75_index=ai,best_index=best,zero_index=zero,r75_G=values[ai],best_G=low,zero_G=values[zero],
                    regret_G=values[ai]-low,regret_us=(values[ai]-low)/(w*r),
                    relative_improvement_vs_R75_suffix=(values[ai]-low)/values[ai] if values[ai] else None,
                    zero_minus_R75_us=zg/(w*r),zero_regret_to_best_us=(values[zero]-low)/(w*r),
                    all_tie=scale==0,feature_alias_conflicts=conflicts)
        details.append(detail);grouped[(entry['mechanism'],entry['parameters']['pressure'])].append(detail)
    assert forced_count==report['planned_branches']==89
    assert sum(item['regret_G']>0 for item in details)==report['improved_first_action_rows']==12
    for check in report['reverse_check']:
        row=next(row for row in results if row['anchor']['anchor_id']==check['anchor_id'])
        original=row['branches'][check['plan_index']]
        repeated=read(OUT/'reverse'/('p%02d'%check['plan_index'])/'result.json')
        assert check['same_cost_and_trace'] and repeated['status']=='complete'
        assert repeated['cost']==original['cost'] and repeated['native_trace_sha256']==original['native_trace_sha256']
    with (OUT/'labels.jsonl').open('w',encoding='utf-8') as target:
        for label in labels:target.write(json.dumps(label,allow_nan=False)+'\n')
    artifact=dict(status='saved_native_Q_R75_artifact_audit_passed',rows=len(labels),primary_branches=forced_count,
                  full_witness_and_native_trace_hash_checks=hash_checks,force_hits_exactly_one=forced_count,
                  exact_original_R75_full_trace_controls=16,reverse_repeats=len(report['reverse_check']),
                  improved_first_action_rows=12,all_tie_rows=sum(item['all_tie'] for item in details),
                  feature_alias_conflict_groups=alias_conflicts,
                  zero_rule_single_deviation_wins_losses_ties_vs_R75=[zero_wins,zero_losses,zero_ties],
                  details=details,labels_sha256=sha(OUT/'labels.jsonl'),report_sha256=sha(OUT/'report.json'),
                  results_sha256=sha(OUT/'results.json'),selection_sha256=sha(OUT/'selection.json'),
                  scope='saved integer ledgers, action identity and hashes; no new native/solver/training',
                  stdout_rounded_IO_never_used_to_derive_G=True,private_post_is_pre_engine=True,
                  direct_all_partition_values_compared=False,private_R75_python_port_claimed=False,formal_D=None)
    (OUT/'artifact_audit.json').write_text(json.dumps(artifact,indent=2)+'\n',encoding='utf-8')
    lines=['# Corner stage0：真实R75续接下的首动作改进空间','',
           '8个新train输入，4机制×压力3/12；同机制压力兄弟共用seed，因此是4条训练seed谱系。每输入按预声明hash选一个O、一个M，共16起点。8000操作/输入，仅接口与局部空间诊断；dev未读取或评分。','',
           f"统一执行墙时{report['execution_seconds']:.4f}秒/180秒，89/89候选完整，16/16原R75动作force控制复现全轨迹/private hash/精确账；6个预声明逆序重复一致。所有候选HANDLER_END overrides=1，无替补样本或续有利样本。CPU已释放。",'',
           '| 机制 | 压力 | 改善起点/选定 | 最大条件剩余代价降幅 |',
           '|---|---:|---:|---:|']
    for (mechanism,pressure),items in grouped.items():
        maximum=max(item['relative_improvement_vs_R75_suffix'] or 0 for item in items)
        lines.append('| {} | {} | {}/{} | {:.4%} |'.format(mechanism,pressure,sum(item['regret_G']>0 for item in items),len(items),maximum))
    lines+=['','12/16起点存在更好的当前动作，随后仍由同一个真实R75继续。最大30.6112%是该起点剩余suffix的条件差，不能当完整输入加速、多个决策叠加收益或AI模型改善。Q是固定合法候选池内的一次动作偏离，不是Q*。','',
            '候选union始终包含真实R75完整动作；同spill集合只按R75原顺序保留，不改变执行顺序。非空periodic按真实ordered SPILL/LOAD产生IO，不增hit/miss/q；只重置明确版本的辅助R65 observer，不重置或冒称恢复R75 private history。','',
            f'同池零残差规则（当前x13+原tie）在这些已算分支中的一次偏离Q_R75胜/负/平为{zero_wins}/{zero_losses}/{zero_ties}；这是现有矩阵查表诊断，不是闭环运行或新模型结果。full32相同输入异cost组为{alias_conflicts}。','',
            '## 精确账与验证边界','',
            'G严格来自真实ordered动作/输入字节的整数write/read/miss账；stdout两位IO只做舍入容差交叉检查，未反推G。M起点账已含触发miss，不重复计罚。','',
            '8条baseline的31226个callback entry物理hash和显式kind/参数/q已逐条验证，包含22个真实非空P。每候选native从原输入重放同一真实prefix；prefix全部动作、物理和private pre/post hashes逐条与baseline相同。强制点之后的每个callback物理entry hash/动作/整数账由Python独立核对，且明确命中一次强制。','',
            'physical hash未包含BW及显式operator/partition ID，这些另由完整输入SHA、固定header/config、canonical IDs及callback参数锁定。private_post为policy commit后、engine执行前；没有跨实现重建R75私有历史，也没有声称直接输出每步所有partition值。','',
            'R75保持原cab5源码不变，实际运行的是经no-override parity和intent反例验证的诊断副本，保留真实观察、只重绑最终实际动作意图。所有日志/哈希/teacher墙时不当正式D；将来hybrid若每次计算R75候选，该真实成本仍须计入部署D。','',
            '## 交付与下一步边界','',
            'labels.jsonl包含16条train监督、89个完整候选代价/原32维因果特征，1条全tie需零训练权重。只白名单读取x/target/mask/权重，raw、private hashes、case/seed/continuation等仅审计使用。artifact_audit.json保留整数账/178次witness与trace哈希/控制与反序核验。','',
            '这批仅8000操作，没有训练或dev评估，不能声称corner AI已超过R75；按预声明规模门，至少需要另冻新>=100k输入验证后，才能提出corner性能结论。后续训练/扩样由Root与Handler决定，本轮不自动执行。','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({key:value for key,value in artifact.items() if key!='details'}))


if __name__=='__main__':main()
