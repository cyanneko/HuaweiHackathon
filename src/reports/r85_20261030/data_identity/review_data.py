"""Post-generation small-artifact review; never rerun the generator or scan input bodies."""
from pathlib import Path
import collections,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
def read(n):return json.loads((H/n).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (H/n).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def local(s):
 prefix='${WORKSPACE}/';assert s.startswith(prefix);return ROOT/s[len(prefix):]
cfg=read('config.json');sel=read('selection.json');man=read('data_manifest.json');cpu=read('cpu_released.json');reg=read('prior_registry.json')
for file,digest in read('artifacts.pre_generation.json').items():assert sha(H/file)==digest
assert man['status']=='COMPLETE_MIXED_COVERAGE_NO_POLICY_RUN' and not man['failures']
assert man['config_sha256']==sha(H/'config.json') and man['selection_sha256']==sha(H/'selection.json')
assert cpu['status']=='RELEASED' and cpu['active_child_processes']==cpu['scheduler_runs']==0 and cpu['seconds']==man['elapsed_seconds']<90
assert len(man['cases'])==man['case_count']==man['planned_cases']==18 and man['replacement_seeds']==0
for rel,digest in cfg['source_hashes'].items():assert sha(ROOT/rel)==digest
for rel,digest in cfg['prior_contracts'].items():assert sha(ROOT/rel)==digest
planned={c['case_id']:c for c in cfg['cases']};actual={c['case_id']:c for c in man['cases']};assert set(planned)==set(actual)
cases=man['cases'];train=[c for c in cases if c['split']=='train'];dev=[c for c in cases if c['split']=='dev']
assert len(train)==12 and len(dev)==6
assert {c['case_id'] for c in read('train_manifest.json')['cases']}=={c['case_id'] for c in train}
assert {c['case_id'] for c in read('reserved_dev_manifest.json')['cases']}=={c['case_id'] for c in dev}
assert len({c['parameters']['seed'] for c in cases})==len({c['lineage_id'] for c in cases})==len({c['input_sha256'] for c in cases})==18
assert not {c['parameters']['seed'] for c in cases}&{r['seed'] for r in reg['entries'] if r['seed'] is not None}
assert not {c['input_sha256'] for c in cases}&{r['input_sha256'] for r in reg['entries'] if r['input_sha256']}
for c in cases:
 p=planned[c['case_id']]
 for field in p:assert c[field]==p[field],(c['case_id'],field)
 st=c['stats'];assert c['status']=='FULL_INPUT_AUDIT_PASS' and all(c['validation'].values())
 assert st['operations']==st['actual_operations']==150000 and st['build_count']+st['probe_count']+st['switch_count']==150000
 assert st['switch_count']==c['parameters']['k'] and st['penalty']==c['parameters']['penalty'] and st['max_partition_bytes']<=c['parameters']['memory']
 assert sha(local(c['metadata_path']))==c['metadata_sha256']==c['meta_sha256']
 folder=local(c['metadata_path']).parent
 for stream in ['stdout','stderr']:assert sha(folder/('generate.'+stream))==c['generation'][stream+'_sha256']
 assert c['generation']['returncode']==0 and local(c['input_path']).stat().st_size==c['bytes']
 for trace in c['trace_identity'].values():assert sha(local(trace['path']))==trace['sha256']
 assert c['training_allowed']==(c['split']=='train') and not c['paired_input'] and c['independent_seed'] and not c['policy_results_observed']
phase_pressure={phase:sorted({c['parameters']['pressure'] for c in train if c['track']=='dynamic' and c['parameters']['phase']==phase}) for phase in ['shared','staggered']}
assert phase_pressure==dict(shared=[1.25],staggered=[3])
boundary='Dynamic TRAIN shared cases all request pressure1.25 and staggered all request pressure3. Phase and pressure are confounded; pressure×bandwidth balance does not remove this. DEV uses different seeds/parameters and is not a matched phase intervention. Do not infer phase causality.'
audit_fields=['full streamed N/counts and per-op phase/K SWITCH','key0..1e9 and tuple1..1MiB bounds','global header K/P/M/W/R/penalty and N/period vs config/metadata','per-op build/probe counts','per-partition build/probe counts and bytes','max partition bytes<=M','requested/realized pressure without correction','dynamic seed/profile/phase/rare/speeds/windows/build-fraction or exact IID spec','full input SHA + metadata/body/operation/partition-stream SHA','dynamic trace SHA','18 independent seeds and inputSHA disjoint from named prior registry']
details=[dict(case_id=c['case_id'],split=c['split'],track=c['track'],family=c['family'],seed=c['parameters']['seed'],input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256'],body_sha256=c['body_sha256'],operation_stream_sha256=c['operation_stream_sha256'],partition_stream_sha256=c['partition_stream_sha256'],stats=c['stats'],requested_pressure=c['parameters']['pressure'],pressure_relative_deviation=c['stats']['actual_pressure']/c['parameters']['pressure']-1) for c in cases]
largest=max(cases,key=lambda c:c['stats']['max_partition_to_M'])
audit=dict(status='PASS',cases=18,train_cases=12,dev_cases=6,independent_seeds=18,total_operations=sum(c['stats']['operations'] for c in cases),total_input_bytes=sum(c['bytes'] for c in cases),elapsed_seconds=man['elapsed_seconds'],
 max_partition_to_M=largest['stats']['max_partition_to_M'],max_partition_case=largest['case_id'],max_partition_bytes=largest['stats']['max_partition_bytes'],actual_pressure_range=[min(c['stats']['actual_pressure'] for c in cases),max(c['stats']['actual_pressure'] for c in cases)],
 actual_max_abs_relative_pressure_deviation=max(abs(c['stats']['actual_pressure']/c['parameters']['pressure']-1) for c in cases),full_audit_fields=audit_fields,per_case=details,failures=[],replacement_seeds=0,
 train_phase_pressure=phase_pressure,phase_pressure_boundary=boundary,model_boundary=cfg['model_boundary'],
 review_scope='Complete input bodies were streamed during generation using pinned audit code. This separate review verifies small artifacts, stats, metadata/log/trace hashes and contracts; it does not claim a second independent body scan.',
 prior_registry_scope=reg['scope'],prior_registry_entries=len(reg['entries']),split_seed_and_lineage_disjoint=True,all18_input_sha_unique=True,prior_registered_seed_and_input_sha_disjoint=True)
save('generation_audit_summary.json',audit)
save('source_review.json',dict(status='PASS_STATIC_FROZEN_GENERATOR_AND_AUDIT_IDENTITY',source_hashes=cfg['source_hashes'],source_changed=False,original_dynamic_sampling_unchanged=True,IID_preallocated_bytes_and_counts_explicit=True,model_boundary=cfg['model_boundary'],scheduler_source_review_in_scope=False))
review=dict(status='PASS',data_status='PASS_FULL_INPUT_AUDIT',source_status='PASS_STATIC_FROZEN_GENERATOR_AND_AUDIT_IDENTITY',data_manifest_sha256=sha(H/'data_manifest.json'),generation_audit_summary_sha256=sha(H/'generation_audit_summary.json'),source_review_sha256=sha(H/'source_review.json'),
 config_sha256=sha(H/'config.json'),selection_sha256=sha(H/'selection.json'),script_sha256=sha(H/'prepare_data.py'),review_script_sha256=sha(Path(__file__)),cpu_released_sha256=sha(H/'cpu_released.json'),cases=18,train_cases=12,dev_cases=6,independent_seed_lineages=18,
 failures=0,replacement_seeds=0,full_audit_fields=audit_fields,split_seed_and_lineage_disjoint=True,prior_registered_seed_and_input_sha_disjoint=True,phase_pressure_boundary=boundary,
 model_boundary=cfg['model_boundary'],DEV_boundary='Independent seeds under predeclared same families, reserved until candidate identity freeze; not OOD/official blind test. Complete planned DEV diagnostic is required later.',scheduler_runs=0,policy_results_read=False,cpu_status='RELEASED',active_child_processes=0)
save('review.json',review)
lines=['# R85 data review','',f"PASS 18/18: TRAIN12 + reserved DEV6, 18 independent seeds. Generation+streaming audit {man['elapsed_seconds']:.6f}s /90s. CPU RELEASED, active0. No solver/training.",'',f"Operations {audit['total_operations']:,}; input bytes {audit['total_input_bytes']:,}; max partition/M {audit['max_partition_to_M']:.9f} at {audit['max_partition_case']}. Actual pressure range {audit['actual_pressure_range']}. Zero failures/replacements; requested seeds and all frozen parameters retained.",'',boundary,'',cfg['model_boundary'],'','Requested and actual pressure differences are natural realizations, preserved without correction. Dynamic rare-hot affects build sizes as well as probe traffic. The two tracks are distinct models. This fractional coverage is not a matched causal experiment; independent seed DEV is not independent distribution/OOD or a fresh official blind test.','',audit['review_scope'],'','|Case|Build|Probe|Actual pressure|Max partition/M|','|---|---:|---:|---:|---:|']
for c in cases:
 s=c['stats'];lines.append(f"|{c['case_id']}|{s['build_count']}|{s['probe_count']}|{s['actual_pressure']:.9f}|{s['max_partition_to_M']:.9f}|")
(H/'DATA_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
files=['prepare_data.py','review_data.py','config.json','commands.json','prior_registry.json','selection.json','TABLE.md','preparation_review.json','artifacts.pre_generation.json','generation_started.json','data_manifest.json','train_manifest.json','reserved_dev_manifest.json','cpu_released.json','generation_audit_summary.json','source_review.json','review.json','DATA_REVIEW.md']
art={name:sha(H/name) for name in files};save('artifacts.json',art)
release=dict(status='RELEASED',ready=True,final=True,active_child_processes=0,scheduler_runs=0,training_runs=0,elapsed_seconds=man['elapsed_seconds'],cases=18,train_cases=12,dev_cases=6,
 data_manifest_sha256=sha(H/'data_manifest.json'),review_sha256=sha(H/'review.json'),generation_audit_summary_sha256=sha(H/'generation_audit_summary.json'),artifacts_sha256=sha(H/'artifacts.json'),cpu_released_sha256=sha(H/'cpu_released.json'),source_hashes=cfg['source_hashes'])
save('release.json',release)
print(json.dumps(dict(status='FINAL_READY',manifest_sha256=release['data_manifest_sha256'],review_sha256=release['review_sha256'],audit_sha256=release['generation_audit_summary_sha256'],artifacts_sha256=release['artifacts_sha256'],release_sha256=sha(H/'release.json'),bytes=audit['total_input_bytes'],max_partition_to_M=audit['max_partition_to_M'],max_partition_case=audit['max_partition_case'],pressure_range=audit['actual_pressure_range'])))
