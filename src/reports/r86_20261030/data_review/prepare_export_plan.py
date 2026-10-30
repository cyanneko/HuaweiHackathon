"""Read fixed Git trees/small metadata only; do not export or scan inputs."""
from pathlib import Path,PurePosixPath
import collections,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;REPO=ROOT/'github-project'
COMMIT='e6613435d59690d6dd768813332387108f7e83c2';TREE='35d4f98b7464e62a9a89b606e41d192380788e76'
CACHE=ROOT/'tmp/r86_final3_cache'
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args])
def blob(p):return git('show',COMMIT+':final_dataset/'+p)
def sha(b):return hashlib.sha256(b).hexdigest()
assert git('rev-parse',COMMIT+':final_dataset').decode().strip()==TREE
assert CACHE.resolve().is_relative_to((ROOT/'tmp').resolve()) and not CACHE.exists()
raw=blob('manifest.json');manifest=json.loads(raw);recipe_raw=blob('recipe.json');recipe=json.loads(recipe_raw)
assert manifest['version']==recipe['version']=='3.0.0' and manifest['recipe_sha256']==sha(recipe_raw)
assert manifest['schema_version']==recipe['schema_version']==4
rows=manifest['cases'];ev=[r for r in rows if r['split']=='eval'];assert len(rows)==612 and len(ev)==72
assert sum(r['operations'] for r in ev)==22528629 and sum(r['file_bytes'] for r in ev)==474874682
assert dict(collections.Counter(r['family'] for r in ev))==dict(random_hotspot=28,random_zipf=28,random_lognormal=16)
entries=[];input_rows={r['path']:r for r in ev};metadata_rows={str(PurePosixPath(r['path']).with_suffix('.meta.json')):r for r in ev}
for line in git('ls-tree','-rl',COMMIT+':final_dataset').decode().splitlines():
    info,p=line.split('\t',1);mode,kind,oid,size=info.split()
    if p.startswith('train/'):continue
    assert mode=='100644' and kind=='blob' and not PurePosixPath(p).is_absolute() and '..' not in PurePosixPath(p).parts
    e=dict(path='final_dataset/'+p,package_relative_path=p,git_blob=oid,bytes=int(size))
    if p in input_rows:e.update(role='eval_input',declared_sha256=input_rows[p]['sha256'])
    elif p in metadata_rows:e.update(role='eval_sidecar',declared_sha256=metadata_rows[p]['metadata_sha256'])
    else:
        data=blob(p);assert len(data)==int(size)
        e.update(role='small_contract_tool_or_published_evidence',sha256=sha(data))
        if p.startswith('tools/'):assert sha(data)==recipe['tool_sha256'][p[6:]]
    entries.append(e)
assert len(entries)==161 and sum(e['bytes'] for e in entries)==479972156
assert {e['package_relative_path'] for e in entries if e['role']=='eval_input'}==set(input_rows)
assert {e['package_relative_path'] for e in entries if e['role']=='eval_sidecar'}==set(metadata_rows)
published=json.loads(blob('reports/validation.json'))
assert published['status']=='passed' and published['summary']['passed_cases']==612 and published['manifest_sha256']==sha(raw) and published['recipe_sha256']==sha(recipe_raw)
plan=dict(status='AWAITING_ROOT_EXPORT_AUDIT_WINDOW',commit=COMMIT,tree=TREE,dataset_version='3.0.0',manifest_schema=4,recipe_schema=4,
    repo_windows=str(REPO),cache_windows=str(CACHE),package_windows=str(CACHE/'final_dataset'),package_linux='${WORKSPACE}<LOCAL_TEMP>',
    scope='All eval72 and sidecars; full published metadata/tools/provenance/reports; no train540 inputs or sidecars',
    archive_argv=['git','-C',str(REPO),'archive','--format=tar',COMMIT,'final_dataset/eval','final_dataset/.gitattributes','final_dataset/README.md','final_dataset/VERSION','final_dataset/manifest.json','final_dataset/recipe.json','final_dataset/tools','final_dataset/provenance','final_dataset/reports'],
    safety='New cache root only; no overwrite, checkout/reset/worktree/config mutation. Stream regular whitelisted tar members to exclusive files; reject links, unexpected paths and traversal; Git blob SHA and declared SHA during write. No duplicate tar file.',
    files=entries,file_count=161,total_bytes=479972156,input_count=72,metadata_count=72,input_bytes=474874682,total_operations=22528629,family_counts=dict(collections.Counter(r['family'] for r in ev)),
    manifest_sha256=sha(raw),recipe_sha256=sha(recipe_raw),verifier_sha256=recipe['tool_sha256']['verify.py'],
    verifier_scope='Original CLI audit hard-requires all612 and has no eval-only option. Use unchanged verify_case/scan_input/certificate functions for all72; independently supplement eval inventory, recipe/provenance/hash and split duplicate checks. Do not claim local full612 validation.',
    stored_full_report=dict(path='final_dataset/reports/validation.json',sha256=sha(blob('reports/validation.json')),status='passed',cases=612,role='publisher supplied additional evidence, not locally repeated'),
    proposed_wall_budget_seconds=120,on_failure='Keep partial export/audit and unprocessed cases; no automatic retry or replacement',
    checks=['exact eval inventory and file sizes; no train extracted','fixed tree/blob/manifest/recipe/VERSION/tools byte identity','full input raw/operation/partition hashes and same metadata hashes','K/P/M/W/R/penalty/N/period header ranges and exact per-op INSERT/PROBE counts','all phases/keys/tuples/single SWITCH and complete positive partition sizes<=M','per-op joint/conditional probability positivity, uniqueness, normalization, target TV>=.20 and hot/cold>=2, mass>=.5/K','actual per-op PROBE TV>=.10, visited>=2; actual counts can tie/zero','recipe spec/build_seed/probe_seed/parent BUILD sizes and source identity','raw/op/partition duplicate check within eval and against declared train and parent manifest; train and parent raw not rescanned'],
    offline_only='Probability certificates, future counts and stats used only by offline audit/evaluator; scheduler receives input file/public callbacks only',scheduler_runs=0,compile_runs=0,generator_runs=0,training_runs=0)
OUT.mkdir(exist_ok=True)
with (OUT/'export_plan.json').open('x',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(dict(status=plan['status'],export_plan_sha256=sha((OUT/'export_plan.json').read_bytes()),files=161,input_cases=72,bytes=479972156,ops=22528629)))
