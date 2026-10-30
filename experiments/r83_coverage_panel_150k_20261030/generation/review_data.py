"""Small-artifact review; does not rescan input bodies or execute a generator."""
from pathlib import Path
import hashlib,json,statistics
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def local(s):
    prefix='${WORKSPACE}/'
    return ROOT/s[len(prefix):] if s.startswith(prefix) else Path(s)
def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
cfg=read(HERE/'config.json');sel=read(HERE/'selection.json');man=read(HERE/'data_manifest.json')
release=read(HERE/'cpu_released.json');registry=read(HERE/'prior_registry.json')['entries']
assert man['status']=='COMPLETE_MIXED_COVERAGE_NO_POLICY_RUN' and not man['failures']
assert man['case_count']==18 and man['train_cases']==12 and man['dev_cases']==6
assert release['active_child_processes']==0 and release['seconds']<90
for key,file in [('config_sha256','config.json'),('commands_sha256','commands.json'),('script_sha256','prepare_data.py'),('prior_registry_sha256','prior_registry.json')]:
    assert sha(HERE/file)==sel[key]
assert sha(ROOT/'docs/superpowers/plans/2026-10-30-r83-coverage-panel.md')==cfg['plan_sha256']
assert sha(ROOT/'tmp/r83_reference/coverage_design.json')==cfg['design_sha256']
source_bindings={}
for name,g in cfg['generators'].items():
    assert sha(ROOT/g['source'])==g['source_sha256']
    source_bindings[name]=dict(source=g['source'],sha256=g['source_sha256'],semantics=g['semantics'])
    if 'binary' in g:
        assert sha(ROOT/g['binary'])==g['binary_sha256']
        source_bindings[name].update(binary=g['binary'],binary_sha256=g['binary_sha256'])
for rel,digest in cfg['prior_contracts'].items(): assert sha(ROOT/rel)==digest
assert sha(ROOT/cfg['old38_reference_path'])==cfg['old38_reference_sha256']
cases=man['cases'];train=[c for c in cases if c['split']=='train'];dev=[c for c in cases if c['split']=='dev']
assert len(train)==12 and len(dev)==6 and {c['group'] for c in train}=={'new_train'} and {c['group'] for c in dev}=={'dev6'}
assert {c['case_id'] for c in read(HERE/'train_manifest.json')['cases']}=={c['case_id'] for c in train}
assert {c['case_id'] for c in read(HERE/'reserved_dev_manifest.json')['cases']}=={c['case_id'] for c in dev}
assert len({c['lineage_id'] for c in train})==6 and len({c['lineage_id'] for c in dev})==6
assert not {c['lineage_id'] for c in train}&{c['lineage_id'] for c in dev}
assert not {c['parameters']['seed'] for c in cases}&{r['seed'] for r in registry if r['seed'] is not None}
assert len({c['input_sha256'] for c in cases})==18
assert not {c['input_sha256'] for c in cases}&{r['input_sha256'] for r in registry}
for c,planned in zip(cases,cfg['cases']):
    assert c['case_id']==planned['case_id'] and c['parameters']==planned['parameters']
    assert c['status']=='FULL_INPUT_AUDIT_PASS' and all(c['validation'].values())
    st=c['stats'];assert st['operations']==150000 and st['build_count']+st['probe_count']+st['switch_count']==150000
    assert st['max_partition_bytes']<=c['parameters']['memory'] and st['penalty']==c['parameters']['penalty']
    assert sha(local(c['metadata_path']))==c['metadata_sha256']==c['meta_sha256']
    folder=local(c['metadata_path']).parent
    for suffix in ['stdout','stderr']:
        assert sha(folder/('generate.'+suffix))==c['generation'][suffix+'_sha256']
    assert local(c['input_path']).stat().st_size==c['bytes']
    assert not c['policy_results_observed'] and c['training_allowed']==(c['split']=='train')
for pair in man['pair_checks']:
    assert pair['complete'] and pair['only_bandwidth_header_diff']
    a,b=sorted([c for c in train if c['block']==pair['block']],key=lambda c:c['bandwidth_scale'])
    assert a['body_sha256']==b['body_sha256']==pair['body_sha256']
    assert a['operation_stream_sha256']==b['operation_stream_sha256'] and a['partition_stream_sha256']==b['partition_stream_sha256']
    assert a['parameters']['seed']==b['parameters']['seed']
    assert a['parameters']['write']*64==b['parameters']['write'] and a['parameters']['read']*64==b['parameters']['read']
    d=next(c for c in dev if c['block']==a['block'])
    assert a['parameters']['write']*8==d['parameters']['write'] and a['parameters']['read']*8==d['parameters']['read']
fields=['full input SHA256','body SHA excluding first header line','operation/partition stream SHA','N/count/phase and K SWITCH','key and tuple legality','header vs config and metadata','per-operator build/probe counts','per-partition bytes and probe counts','max partition <= M','realized pressure','seed/profile/phase/rare or exact IID spec','source and metadata SHA','bandwidth-only pair equality','prior manifest SHA/seed separation']
audit=dict(status='PASS',audit_method='Generation-stage complete input streaming audit, then independent small-artifact consistency review; input bodies not scanned a second time.',cases=18,train_cases=12,dev_cases=6,train_lineages=6,dev_lineages=6,total_operations=sum(c['stats']['operations'] for c in cases),total_input_bytes=sum(c['bytes'] for c in cases),elapsed_seconds=man['elapsed_seconds'],max_partition_to_M=max(c['stats']['max_partition_to_M'] for c in cases),actual_pressure_range=[min(c['stats']['actual_pressure'] for c in cases),max(c['stats']['actual_pressure'] for c in cases)],full_audit_fields=fields,pair_checks=man['pair_checks'],failures=[],replacement_seeds=0,prior_registry_entries=len(registry),prior_registry_scope=cfg['prior_registry_scope'],per_case=[{k:c[k] for k in ['case_id','split','group','track','lineage_id','input_sha256','metadata_sha256','body_sha256','operation_stream_sha256','partition_stream_sha256','parameters','stats']} for c in cases])
save('generation_audit_summary.json',audit)
save('source_review.json',dict(status='PASS_STATIC_NO_BLOCKER',source_bindings=source_bindings,model_boundary=cfg['model_boundary'],scope='Frozen generator source/binary identity and documented interface only. No scheduler source or native strategy execution involved.',iid_preallocation_explicit=True,original_dynamic_generator_unchanged=True))
review=dict(status='PASS',data_status='PASS_FULL_INPUT_AUDIT',source_status='PASS_STATIC_NO_BLOCKER',data_manifest_sha256=sha(HERE/'data_manifest.json'),generation_audit_summary_sha256=sha(HERE/'generation_audit_summary.json'),source_review_sha256=sha(HERE/'source_review.json'),config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),script_sha256=sha(HERE/'prepare_data.py'),review_script_sha256=sha(Path(__file__)),cpu_released_sha256=sha(HERE/'cpu_released.json'),cases=18,train_cases=12,dev_cases=6,train_independent_seed_lineages=6,dev_independent_seed_lineages=6,full_audit_fields=fields,failures=0,replacement_seeds=0,scheduler_runs=0,policy_results_read=False,cpu_status='RELEASED',active_child_processes=0,old38_reference_path=cfg['old38_reference_path'],old38_reference_sha256=cfg['old38_reference_sha256'],model_boundary=cfg['model_boundary'])
save('review.json',review)
lines=['# R83 mixed coverage panel data review','',f"PASS: 18/18 cases, 12 TRAIN + 6 reserved DEV; {man['elapsed_seconds']:.6f}s of 90s budget. CPU RELEASED / active0. No scheduler run or policy result read.",'',f"Total {audit['total_operations']:,} operations, {audit['total_input_bytes']:,} input bytes. Maximum partition/M={audit['max_partition_to_M']:.9f}. Actual pressure range={audit['actual_pressure_range']}.",'','TRAIN has six independent seed lineages with bandwidth 1/64 body-identical pairs, not twelve independent seeds. DEV has six separate seeds and bandwidth8. All six TRAIN body/operation/partition-stream comparisons pass. No failures or replacement seeds.','',cfg['model_boundary'],'','This is an explicitly separate coverage track: nine dynamic files and nine IID files. IID exact build-byte/count allocation must not be described as the original naturally sampled dynamic model. Rare hot affects INSERT and PROBE and therefore bytes, not a pure access-only intervention.','', 'Complete input streaming validation occurred in generation. This review checks its recorded counts/identities, small metadata/log hashes, frozen sources and paired contracts; it does not claim an independent second full-body scan. Prior checks use recorded SHA/seed/lineage from named manifests, not a new scan of historical inputs. DEV is reserved until candidate freeze; no policy outcome exists in this data work.','','| Case | Build | Probe | Actual pressure | Max part/M |','|---|---:|---:|---:|---:|']
for c in cases:
    s=c['stats'];lines.append(f"| {c['case_id']} | {s['build_count']} | {s['probe_count']} | {s['actual_pressure']:.8f} | {s['max_partition_to_M']:.8f} |")
with (HERE/'DATA_REVIEW.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
files=['config.json','commands.json','selection.json','prior_registry.json','prepare_data.py','review_data.py','data_manifest.json','train_manifest.json','reserved_dev_manifest.json','generation_audit_summary.json','source_review.json','review.json','DATA_REVIEW.md','cpu_released.json']
save('artifacts.json',{name:sha(HERE/name) for name in files})
print(json.dumps(dict(status='PASS',review_sha256=sha(HERE/'review.json'),artifacts_sha256=sha(HERE/'artifacts.json'),total_input_bytes=audit['total_input_bytes'],max_partition_to_M=audit['max_partition_to_M'],actual_pressure_range=audit['actual_pressure_range'])))
