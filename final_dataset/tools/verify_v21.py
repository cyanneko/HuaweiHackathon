"""Validate the expanded skew-focused release without running a solver or fetching data."""
import json
from pathlib import Path
import sys

from release_v21 import (PACKAGE, VERSION, PARENT, PARENT_HASHES, EVAL_COUNTS,
                         TRAIN_COUNTS, FINAL_EVAL_COUNTS, FINAL_TRAIN_COUNTS,
                         encoded, load, select, sha, summary)
from verify import HASH_KEYS, no_local_paths, observed_skew, relative_target, signatures

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'evaluation'))
from evaluate import object_hash
from scripts.audit_datasets import audit_case


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_contract(package):
    """Check lineage, immutable selection/specs and exact recursive file sets."""
    package = Path(package)
    history = package/'provenance/v2.0.0'
    for name, digest in PARENT_HASHES.items():
        require(sha(history/name)==digest, 'Frozen parent changed: '+name)
    parent, previous = load(history/'manifest.json'), load(history/'recipe.json')
    old_validation = load(history/'validation.json')
    require(old_validation['status']=='passed' and not old_validation['errors'], 'Parent audit failed')
    require(old_validation['manifest_sha256']==PARENT_HASHES['manifest.json'] and
            old_validation['recipe_sha256']==PARENT_HASHES['recipe.json'], 'Parent audit binding differs')
    active, retired, diagnostic, training = select(parent)
    train = [r for r in parent['cases'] if r['split']=='train']
    diag = [dict(r,path='diagnostics/'+Path(r['path']).name,split='diagnostics',parent_path=r['path'])
            for r in diagnostic]
    manifest, recipe, selection = (load(package/name) for name in ('manifest.json','recipe.json','selection.json'))
    from expand_v21 import check_plan
    plan, expansion = load(package/'expansion.json'), load(package/'expansion_manifest.json')
    check_plan(plan)
    initial_plan = load(package/'provenance/v2.1-initial-plan/expansion.json')
    require(sha(package/'provenance/v2.1-initial-plan/expansion.json')==plan['initial_plan_sha256'] and
            initial_plan['master_seed']==plan['master_seed'] and
            initial_plan['generated_cases']==plan['generated_cases'], 'Initially frozen specifications changed')
    require(expansion['expansion_sha256']==sha(package/'expansion.json'), 'Expansion plan binding differs')
    require(len(expansion['cases'])==len(plan['generated_cases'])==306, 'Expansion count differs')
    for row,request in zip(expansion['cases'],plan['generated_cases']):
        require(all(row[key]==request[key] for key in ('path','split','family')) and
                row['source_member']=='new_synthetic' and not row['is_edge'], 'Expansion identity differs')
    added_train = [r for r in expansion['cases'] if r['split']=='train']
    added_eval = [r for r in expansion['cases'] if r['split']=='eval']
    require(len(added_train)==270 and len(added_eval)==36, 'Expansion split counts differ')
    base_train, base_active = train, active
    train, active, training = train+added_train, active+added_eval, training+added_train

    require(no_local_paths([manifest,recipe,selection]), 'Nonportable local path in release metadata')
    require((package/'eval/VERSION').read_text().strip()==manifest['version']==recipe['version']==
            selection['version']==VERSION, 'Release versions differ')
    require(manifest['recipe_sha256']==sha(package/'recipe.json'), 'Recipe hash differs')
    require(recipe['expansion_sha256']==manifest['expansion_sha256']==sha(package/'expansion.json'), 'Expansion plan hash differs')
    require(manifest['expansion_manifest_sha256']==sha(package/'expansion_manifest.json'), 'Expansion records hash differs')
    require(manifest['selection_sha256']==recipe['selection_sha256']==sha(package/'selection.json'),
            'Selection hash differs')
    require(manifest['previous_release_revision']==recipe['previous_release_revision']==
            selection['parent_revision']==PARENT, 'Parent revision differs')
    require(selection['parent_hashes']==PARENT_HASHES and manifest['parent_manifest_sha256']==
            recipe['parent_manifest_sha256']==PARENT_HASHES['manifest.json'], 'Parent hash binding differs')
    require(manifest['cases']==train+active and manifest['diagnostics']==diag,
            'Manifest is not exactly the parent subset, frozen expansion and diagnostic relocation')
    expected_summary = {'train':summary(train),'eval':summary(active),'diagnostics':summary(diag)}
    require(manifest['summary']==expected_summary, 'Manifest summary differs')
    require(selection['retained_eval_paths']==[r['path'] for r in base_active] and
            selection['added_eval_paths']==[r['path'] for r in added_eval] and
            selection['added_training_paths']==[r['path'] for r in added_train], 'Eval selection differs')
    expected_retired = [(r['path'],r['sha256'],r['metadata_sha256']) for r in retired]
    require([(r['path'],r['sha256'],r['metadata_sha256']) for r in selection['retired_eval']]==expected_retired,
            'Retired selection differs')
    require(selection['diagnostic_moves']==[dict(from_path=r['path'],to_path=d['path'],
            sha256=r['sha256'],metadata_sha256=r['metadata_sha256']) for r,d in zip(diagnostic,diag)],
            'Diagnostic relocation differs')
    require(selection['recommended_training_paths']==[r['path'] for r in training] and
            selection['recommended_training_family_counts']==FINAL_TRAIN_COUNTS, 'Training profile differs')
    require(selection['eval_family_counts']==FINAL_EVAL_COUNTS and
            selection['family_weights']=={k:v/72 for k,v in FINAL_EVAL_COUNTS.items()}, 'Eval weights differ')
    require(selection['prior_results_exposed'] is True and recipe['prior_results_exposed'] is True,
            'Public regression subset cannot be relabelled as blind holdout')
    require(selection['new_seeds']==recipe['new_seeds']==306, 'Expansion must have exactly 306 new seeds')
    wanted = {r['path'] for r in base_train+base_active}
    require(recipe['generated_cases']==[r for r in previous['generated_cases'] if r['path'] in wanted]+plan['generated_cases'],
            'Frozen specs/seeds differ from parent and expansion')
    require(recipe['diagnostic_specs']==[r for r in previous['generated_cases']
            if r['path'] in {d['path'] for d in diagnostic}], 'Diagnostic spec differs')
    require(recipe['reused_training_paths']==previous['reused_training_paths'], 'Training lineage differs')
    require(recipe['generator_sha256']==previous['generator_sha256']==sha(REPO/'final_dataset/tools/random_workloads.py'),
            'Original generator changed')
    require(recipe['original_builder_sha256']==previous['builder_sha256']==sha(REPO/'final_dataset/tools/build_v2.py'),
            'Original builder changed')
    require(recipe['builder_sha256']==sha(REPO/'final_dataset/tools/release_v21.py'), 'Current exporter changed')
    for key, expected in {'train_cases':770,'train_regular':750,'train_edge':20,'eval_cases':72,
            'eval_regular':72,'eval_edge':0,'generated_training_cases':650,'generated_eval_cases':72,
            'diagnostic_cases':1}.items():
        require(recipe[key]==expected, 'Recipe count differs: '+key)
    rows = manifest['cases']+manifest['diagnostics']
    for split in ('train','eval','diagnostics'):
        expected = {r['path'] for r in rows if r['split']==split}
        for suffix in ('.txt','.meta.json'):
            wanted = {str(Path(p).with_suffix(suffix)) for p in expected}
            actual = {p.relative_to(package).as_posix() for p in (package/split).rglob('*'+suffix)}
            require(actual==wanted, 'Unexpected/missing '+suffix+' files in '+split)
    for row in rows:
        for suffix in ('.txt','.meta.json'):
            path = relative_target(package,str(Path(row['path']).with_suffix(suffix)))
            require(not path.is_symlink(), 'Symlink in frozen inputs: '+row['path'])
    for key in HASH_KEYS:
        values = [r[key] for r in rows]
        require(len(set(values))==len(values), 'Duplicate input signature: '+key)
    for key in HASH_KEYS:
        require(not ({r[key] for r in expansion['cases']}&{r[key] for r in parent['cases']}),
                'Expansion collides with parent, including retired cases: '+key)
    return manifest, recipe, selection


def validate(package):
    manifest, recipe, selection = validate_contract(package)
    rows = manifest['cases']+manifest['diagnostics']
    # A raw recheck binds unchanged training inputs to the frozen full v2 audit.
    for row in rows:
        for suffix,key in (('.txt','sha256'),('.meta.json','metadata_sha256')):
            relative = str(Path(row['path']).with_suffix(suffix))
            require(sha(package/relative)==row[key], 'Frozen bytes changed: '+relative)
    print('Verified bytes and sidecars: 843/843 (770 train, 72 eval, 1 diagnostic)',flush=True)
    added = set(selection['added_training_paths']+selection['added_eval_paths'])
    frozen = {r['path']:r for r in recipe['generated_cases']}
    details = []
    for row in rows:
        if row['split']=='train' and row['path'] not in added:
            continue
        path = package/row['path']
        meta = load(path.with_suffix('.meta.json'))
        observed = audit_case(path,meta,enforce_limits=True)
        if row['path'] in added:
            fixed = frozen[row['path']]
            require(meta['spec']==fixed['spec'] and meta['seed']==fixed['seed'] and
                    meta['split']==row['split'] and meta['family']==row['family'] and
                    meta['generator_sha256']==recipe['generator_sha256'], 'New metadata/seed/spec differs')
        hashes = signatures(path)
        for key in HASH_KEYS:
            require(hashes[key]==row[key], 'Recomputed signature differs: '+row['path']+' '+key)
        for key in ('operations','insert_count','probe_count','build_bytes','k','p','memory',
                    'pressure','phase_overlap','file_bytes','max_probe_partition_share'):
            require(observed[key]==row[key], 'Observed statistic differs: '+row['path']+' '+key)
        require(observed['operation_stream_sha256']==hashes['operation_stream_sha256'],
                'Independent operation hashes disagree: '+row['path'])
        if row['split']=='eval':
            require(observed['operations']>=65536 and observed['pressure']>1, 'Eval scale contract failed')
        details.append(dict(path=row['path'],family=row['family'],operations=observed['operations'],
                            pressure=observed['pressure'],**observed_skew(observed)))
        if len(details)%10==0 or len(details)==343:
            print(f'Independent input audit: {len(details)}/343',flush=True)
    files = []
    for row in manifest['cases']:
        if row['split']=='eval':
            for suffix,key in (('.txt','sha256'),('.meta.json','metadata_sha256')):
                files.append(dict(path=Path(row['path']).with_suffix(suffix).name,sha256=row[key]))
    identity = dict(member='final_dataset',version=VERSION,files=sorted(files,key=lambda r:r['path']))
    dataset_hash = object_hash(identity)
    suite_id = object_hash([dict(member='final_dataset',version=VERSION,sha256=dataset_hash)])
    return dict(schema_version=3,version=VERSION,status='passed',errors=[],
        manifest_sha256=sha(package/'manifest.json'),recipe_sha256=sha(package/'recipe.json'),
        selection_sha256=sha(package/'selection.json'),validator_sha256=sha(Path(__file__)),
        signature_validator_sha256=sha(Path(__file__).with_name('verify.py')),
        input_auditor_sha256=sha(REPO/'evaluation/scripts/audit_datasets.py'),
        checked_raw_inputs=843,checked_sidecars=843,independently_audited_eval_inputs=72,
        independently_audited_new_training_inputs=270,
        independently_audited_diagnostic_inputs=1,training_legality_inherited_after_raw_recheck=500,
        parent_validation_sha256=PARENT_HASHES['validation.json'],
        dataset_sha256=dataset_hash,suite_id_if_only_final_dataset=suite_id,summary=manifest['summary'],
        recommended_training_cases=540,details=details,
        checks=['exact recursive input/sidecar sets; diagnostics outside eval',
                'all retained parent bytes and metadata identical to frozen v2.0.0; new inputs bound to expansion plan',
                'original 500 training rows unchanged; 270 train and 36 eval added with independent seeds',
                '343 inputs independently audited with official bounds and ascending headers',
                'raw, operation and modulo-P signatures unique across surviving splits',
                '306 frozen new seeds; no eval promoted into training; new cases distinct from all 550 parent cases'],
        limitations=['Original 500 training cases inherit the fixed v2 audit after raw-byte recheck; all 270 added training cases are independently audited. Historical-source isolation is inherited only for retained parent cases; expansion is checked against all 550 parent cases, not every historical source trace.',
            'Contains 36 already exposed eval cases plus 36 new traces; the combined suite is not a fresh blind holdout.',
            'This validator runs no solver; separate official-reference runtime smoke checks do not establish arbitrary candidate speed or score attainability.',
            'No interleaved BUILD/PROBE phases or 5M-operation limit cases; distribution weights are engineering choices; family also affects build-size distribution.'])


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--out',type=Path,help='default: PACKAGE/validation.json')
    args = parser.parse_args(argv)
    package = args.package.resolve()
    try:
        report = validate(package)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        report = dict(schema_version=3,version=VERSION,status='failed',errors=[
            {'error':type(exc).__name__+': '+str(exc).replace(str(package),'<package>').replace(str(REPO),'<repo>')}])
    target = args.out or package/'validation.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(encoded(report))
    print(json.dumps(dict(status=report['status'],error_count=len(report['errors']))),flush=True)
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
