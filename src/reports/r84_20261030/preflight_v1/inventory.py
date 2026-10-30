"""Metadata-only inventories; no solver and no full input hashing in static stage."""
from pathlib import Path
import argparse,collections,hashlib,json,os
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PROOF='tmp/pub82/latest_eval_metadata.json'
PROOF_SHA='8281b8cb6816589e4aa1d436169118ea9dcc3f6a98929efadf36e50712242b1a'
BASE_REFERENCE='tmp/r81_regression_eval/final/selection.json'
BASE_REFERENCE_SHA='5e86c6ed7670c7eb987ab90fba6a2adfeba822a104b4ff6a277ccd771db6c797'
DYNA_REFERENCE='tmp/r77_dyna_contract/cases.prepared.json'
DYNA_REFERENCE_SHA='428bc04f1aa19536cee068ff79d012f81e44e80c29cbc965f12c9e42da4165ac'
AMENDMENT='docs/superpowers/plans/2026-10-30-r83-full-evaluation-amendment.md'
AMENDMENT_SHA='5e69b82e2f444f7452d4815fa6f094136b86ee97f5f4c3678af0b4879e52c893'
BASE_NAMES=['Naive','R75_dense_switch','R79_adaptive','R80_next_hier_fast100','R80_paired_hier_fast100','R81_op256_cond2048']
FRAMEWORK_SHA='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda:f.read(1<<20),b''):h.update(part)
    return h.hexdigest()
def path(s):
    s=str(s).replace('\\','/')
    if len(s)>1 and s[1]==':' and os.name!='nt':s='/mnt/'+s[0].lower()+s[2:]
    elif s.startswith('/mnt/') and os.name=='nt':s=s[5].upper()+':'+s[6:]
    p=Path(s);return p if p.is_absolute() else ROOT/p
def linux(p):return '${WORKSPACE}/'+Path(p).relative_to(ROOT).as_posix()
def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def verify_source(m,elf=False):
    assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
    fields=[('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256')]
    if elf:fields.append(('binary','binary_sha256'))
    for field,key in fields:assert sha(path(m[field]))==m[key],m['name']+'/'+field
    source=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(source)==1
    assert hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==FRAMEWORK_SHA

def build_inventory(mode):
    assert sha(ROOT/PROOF)==PROOF_SHA and sha(ROOT/AMENDMENT)==AMENDMENT_SHA
    proof=read(ROOT/PROOF);assert proof['remote_commit']==proof['local_commit']=='01e9de234cc735bc442f020c8b1b503d961543db'
    dataset='dyna_dataset' if mode=='dyna' else 'final_dataset';binding=proof['datasets'][dataset]
    assert binding['local_tree_equal'] and binding['tree_equal_f25']
    folder=ROOT/'tmp/d70'/dataset;mf=folder/'manifest.json';manifest=read(mf)
    assert sha(mf)==binding['manifest_sha256']
    cases=[];deps={PROOF:PROOF_SHA,AMENDMENT:AMENDMENT_SHA,str(mf.relative_to(ROOT)):sha(mf)}
    if mode=='dyna':
        assert sha(ROOT/DYNA_REFERENCE)==DYNA_REFERENCE_SHA
        deps[DYNA_REFERENCE]=DYNA_REFERENCE_SHA
        refs={c['case_id']:c for c in read(ROOT/DYNA_REFERENCE)['cases']}
        ds=read(folder/'dataset.json');assert ds['version']==binding['version']=='1.0.0' and ds['cases']==12
        assert ds['generator_manifest_sha256']==sha(mf)
        published={c['case_id']:c for c in ds['inputs']}
        assert set(refs)==set(published)=={c['case_id'] for c in manifest['cases']}
        assert (folder/'VERSION').read_text().strip()=='1.0.0'
        for f in ['dataset.json','VERSION']:deps[str((folder/f).relative_to(ROOT))]=sha(folder/f)
        for entry in sorted(manifest['cases'],key=lambda c:c['case_id']):
            cid=entry['case_id'];ref=refs[cid];meta=ROOT/ref['metadata'];m=read(meta);inp=path(ref['input_linux']);par=entry['parameters']
            assert ref['input_sha256']==entry['sha256']==published[cid]['input_sha256']
            assert ref['metadata_sha256']==entry['metadata_sha256']==sha(meta)==sha(folder/entry['metadata'])
            assert ref['parameters']==par and m['operations']==par['n']==5000000
            assert inp.stat().st_size==entry['bytes']==ref['bytes']==published[cid]['raw_bytes']
            assert m['penalty']==par['penalty'] and m['seed']==par['seed'] and m['max_partition_bytes']<=par['memory']
            build=sum(m['actual_build_counts']);probe=sum(m['actual_probe_counts']);assert build+probe+par['k']==5000000
            assert probe==ref['stats']['probe_count'] and entry['split']==ref['original_split']==published[cid]['split']
            cases.append(dict(case_id=cid,case=cid+'.txt',input_path=linux(inp),input_path_linux=linux(inp),input_sha256=entry['sha256'],metadata_path=linux(meta),metadata_sha256=entry['metadata_sha256'],bytes=entry['bytes'],
                stats=dict(operations=5000000,build_count=build,probe_count=probe,penalty=m['penalty']),parameters=par,
                family=par['profile']+'_'+par['phase'],original_split=entry['split'],split=entry['split'],group='dyna12',training_allowed=False,original_holdout=entry['split']=='holdout',untouched_holdout=False,
                published_input_path=dataset+'/'+entry['input'],published_archive_path=dataset+'/'+entry['archive'],published_archive_sha256=entry['archive_sha256'],full_input_sha_verified_in_static=False))
        assert collections.Counter(c['original_split'] for c in cases)==dict(train=6,dev=3,holdout=3)
    else:
        assert manifest['version']==binding['version']=='2.1.0' and manifest['summary']['eval']['cases']==72
        assert (folder/'eval/VERSION').read_text().strip()=='2.1.0'
        deps[str((folder/'eval/VERSION').relative_to(ROOT))]=sha(folder/'eval/VERSION')
        entries=sorted([c for c in manifest['cases'] if c['split']=='eval'],key=lambda c:c['path'])
        assert len(entries)==72
        for entry in entries:
            inp=folder/entry['path'];meta=inp.with_suffix('.meta.json');m=read(meta);cid=inp.stem
            assert sha(meta)==entry['metadata_sha256'] and m['sha256']==entry['sha256']
            assert inp.stat().st_size==entry['file_bytes'] and m['operations']==entry['operations']
            assert m['split']=='eval' and m['family']==entry['family'] and m['probe_count']==entry['probe_count']
            assert m['insert_count']==entry['insert_count'] and m['insert_count']+m['probe_count']+m['k']==m['operations']
            assert m['max_partition_bytes']<=m['memory'] and m['spec']['penalty']==m['penalty']
            cases.append(dict(case_id=cid,case=inp.name,input_path=linux(inp),input_path_linux=linux(inp),input_sha256=entry['sha256'],metadata_path=linux(meta),metadata_sha256=entry['metadata_sha256'],bytes=entry['file_bytes'],
                stats=dict(operations=m['operations'],build_count=m['insert_count'],probe_count=m['probe_count'],penalty=m['penalty']),parameters=m['spec'],
                family=entry['family'],original_split='eval',split='eval',group='final72',training_allowed=False,untouched_holdout=False,
                published_input_path=dataset+'/'+entry['path'],operation_stream_sha256=entry['operation_stream_sha256'],full_input_sha_verified_in_static=False))
        assert collections.Counter(c['family'] for c in cases)==dict(random_hotspot=28,random_zipf=28,random_lognormal=16)
    assert len(cases)==binding['case_count']==(12 if mode=='dyna' else 72)
    assert len({c['case_id'] for c in cases})==len({c['input_sha256'] for c in cases})==len(cases)
    return dict(status='METADATA_AND_SIZE_PASS_INPUT_BODY_HASH_DEFERRED_TO_PREPARE',mode=mode,dataset=dataset,dataset_version=binding['version'],dataset_commit=proof['remote_commit'],dataset_tree=binding['tree'],latest_confirmation_scope='Master metadata proof at this fixed commit; no claim about later remote movement',
        remote_confirmation_path=PROOF,remote_confirmation_sha256=PROOF_SHA,dependencies=deps,case_count=len(cases),cases=cases,
        input_bytes=sum(c['bytes'] for c in cases),operations=sum(c['stats']['operations'] for c in cases),full_input_hashes_computed=0,native_runs=0)

def static():
    assert sha(ROOT/BASE_REFERENCE)==BASE_REFERENCE_SHA
    reference=read(ROOT/BASE_REFERENCE);assert [m['name'] for m in reference['methods']]==BASE_NAMES
    for m in reference['methods']:verify_source(m)
    for mode in ['dyna','final']:save(HERE/(mode+'.inventory.json'),build_inventory(mode))
    save(HERE/'base_methods.prepared.json',dict(status='SIX_HISTORICAL_SOURCE_TU_PASS_ELF_RECHECK_AT_PREPARE_VAN_PENDING',source_reference=BASE_REFERENCE,source_reference_sha256=BASE_REFERENCE_SHA,methods=reference['methods']))
    print(json.dumps(dict(status='PASS_STATIC_INVENTORY',dyna_cases=12,final_cases=72,historical_source_tu=6,Van='pending independent frozen identity',input_body_hashes=0,solver_runs=0)))
if __name__=='__main__':static()
