"""Verify append-only v1.1; carry forward byte-identical v1 input audits."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
from generate import sha,dump,FAMILIES
from verify_v1 import extra_audit

HERE=Path(__file__).resolve().parent
KEYS=['sha256','operation_stream_sha256','partition_stream_sha256']
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=HERE.parent);args=parser.parse_args();root=args.root
    if not (root/'long_recipe.json').exists():
        import verify_v1
        verify_v1.main();return
    base=read(root/'versions/1.0.0/manifest.json');oldcheck=read(root/'versions/1.0.0/validation.json')
    plan=read(root/'long_recipe.json');old_recipe=read(root/'recipe.json')
    assert oldcheck['status']=='passed' and oldcheck['suite_id']==base['suite_id']
    assert plan['new_cases']==20 and plan['operation_target']==2_000_000
    assert sha(HERE/'generate.py')==old_recipe['generator_sha256']==plan['base_generator_sha256']
    assert sha(HERE/'append_long.py')==plan['generator_sha256']
    for split,n in [('train',500),('eval',70)]:
        assert len(list((root/split).glob('*.txt')))==len(list((root/split).glob('*.meta.json')))==n
    rows=[];seen={key:set() for key in KEYS}
    for row in base['cases']:
        path=root/row['path'];assert sha(path)==row['sha256'] and sha(path.with_suffix('.meta.json'))==row['metadata_sha256']
        for key in KEYS:assert row[key] not in seen[key];seen[key].add(row[key])
        rows.append(row)
    assert len(rows)==550;print('Original 550 input and metadata byte hashes unchanged.',flush=True)
    auditor_path=HERE.parents[1]/'evaluation/scripts/audit_datasets.py'
    spec=importlib.util.spec_from_file_location('public_long_auditor',auditor_path)
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    prior=read(root/'long_prior_hashes.json');historical={k:set(v) for k,v in prior['hashes'].items()};windows=[]
    for s in plan['cases']:
        path=root/'eval'/(s['id']+'.txt');meta=read(path.with_suffix('.meta.json'))
        assert meta['recipe']==s and meta['case_kind']=='long_eval' and meta['version']=='1.1.0'
        actual=auditor.audit_case(path,metadata=meta,enforce_limits=True)
        assert actual['operations']==2_000_000 and actual['sha256']==meta['input_sha256']
        assert actual['probe_count']==s['total_probes'] and actual['insert_count']==s['planned_insert_count']
        assert 2<=actual['pressure']<=8 and actual['max_partition_bytes']<=.7*actual['memory']
        assert actual['file_bytes']<50*1024**2
        extra=extra_audit(path,meta)
        for key in KEYS:
            value=extra[key] if key in extra else actual[key]
            assert value not in seen[key] and value not in historical[key],(path.name,key,'duplicate stream')
            seen[key].add(value)
        rows.append({'path':path.relative_to(root).as_posix(),'split':'eval','family':s['family'],'seed':s['seed'],
                     'case_kind':'long_eval','schedule':s['schedule'],'size_heat_relation':s['size_heat_relation'],
                     'metadata_sha256':sha(path.with_suffix('.meta.json')),**actual,
                     **{k:v for k,v in extra.items() if k!='probe_window_counts'}})
        windows.append({'path':path.relative_to(root).as_posix(),'counts':extra['probe_window_counts']})
        print(f'Audited long {len(windows)}/20: N={actual["operations"]}',flush=True)
    summaries={}
    for split in ['train','eval']:
        group=[r for r in rows if r['split']==split]
        s={'cases':len(group),'families':dict(Counter(x['family'] for x in group)),
           'operations_total':sum(x['operations'] for x in group),'operations_min':min(x['operations'] for x in group),
           'operations_median':statistics.median(x['operations'] for x in group),'operations_max':max(x['operations'] for x in group),
           'input_bytes':sum(x['file_bytes'] for x in group),'build_bytes_total':sum(x['build_bytes'] for x in group),
           'mixed_phase_cases':sum(x['phase_overlap'] for x in group),
           'schedule_counts':dict(Counter(x['schedule'] for x in group)),
           'relation_counts':dict(Counter(x['size_heat_relation'] for x in group))}
        for field,label in [('build_bytes','build_bytes'),('memory','memory_bytes'),('pressure','pressure')]:
            s[label+'_min']=min(x[field] for x in group);s[label+'_max']=max(x[field] for x in group)
        assert set(s['families'])==set(FAMILIES) and set(s['families'].values())==({50} if split=='train' else {7})
        summaries[split]=s
    suite=hashlib.sha256(''.join(x['path']+' '+x['sha256']+'\n' for x in rows).encode()).hexdigest()
    manifest={'schema_version':2,'name':'inde_dataset','version':'1.1.0','suite_id':suite,
              'base_version':'1.0.0','base_suite_id':base['suite_id'],'base_manifest_sha256':sha(root/'versions/1.0.0/manifest.json'),
              'recipe_sha256':sha(root/'recipe.json'),'long_recipe_sha256':sha(root/'long_recipe.json'),
              'generator_sha256':sha(HERE/'generate.py'),'long_generator_sha256':sha(HERE/'append_long.py'),
              'summary':summaries,'cases':rows,'all_new_synthetic':True,
              'exposure':'Original eval50 previously measured; new long eval20 fixed before member measurement. No score-based filtering.'}
    validation={'status':'passed','version':'1.1.0','cases':570,'new_long_cases':20,'errors':[],
                'suite_id':suite,'verifier_sha256':sha(Path(__file__)),'independent_auditor_sha256':sha(auditor_path),
                'base_preservation':'550 original inputs and metadata byte-identical; carry forward their frozen independent audit.',
                'new_checks':['exactly 20 x 2000000 operations including SWITCH','official range/phase/count/capacity audit',
                              'ascending headers and actual hotspot window check','new/base/historical byte, operation and partition-stream uniqueness'],
                'prior_hashes_sha256':sha(root/'long_prior_hashes.json'),'summary':summaries}
    for name,value in [('manifest.json',manifest),('validation.json',validation)]:
        target=root/name
        if read(target).get('version')=='1.1.0':assert read(target)==value,'Frozen audit changed'
        else:dump(target,value)
    (root/'VERSION').write_bytes(b'1.1.0\n');(root/'eval/VERSION').write_bytes(b'1.1.0\n')
    dest=root/'long_probe_windows.json'
    if dest.exists():assert read(dest)==windows
    else:dest.write_bytes((json.dumps(windows,separators=(',',':'))+'\n').encode())
    print(json.dumps({'status':'passed','suite_id':suite,'summary':summaries},indent=2),flush=True)


if __name__=='__main__':main()
