"""Score-blind, pinned-release validation24 selection. Headers and small JSON only."""
from pathlib import Path
import hashlib,json,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
COMMIT='f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246';SEED='r80-final-sample-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def main():
 assert not (HERE/'config.json').exists() and not (HERE/'selection.json').exists(),'never overwrite frozen selection'
 dataset=ROOT/'tmp/d70/final_dataset';manifest=dataset/'manifest.json';oldpath=ROOT/'tmp/r79_final_eval/selection.json';contractpath=ROOT/'tmp/r79_final_eval/root_input_contract.json'
 old=read(oldpath);contract=read(contractpath);data=read(manifest)
 assert contract['status']=='ROOT_INPUT_SHA_PASS' and contract['commit']==COMMIT and contract['version']=='2.1.0'
 assert contract['cases_verified']==72 and contract['all_input_metadata_hashes_match']
 assert sha(manifest)==contract['manifest_sha256']=='217e8e24ad6fcf6c1c057bb2031d5cde23fe2e2b35595b095d119922a47aee87'
 assert (dataset/'eval/VERSION').read_text().strip()=='2.1.0'
 assert old['input_contract_sha256']==sha(contractpath) and len(old['cases'])==24
 excluded={x['case_id'] for x in old['cases']};oldsha={x['input_sha256'] for x in old['cases']}
 population=[c for c in data['cases'] if c['split']=='eval'];assert len(population)==72
 remaining=[c for c in population if Path(c['path']).stem not in excluded];assert len(remaining)==48
 config=dict(status='FROZEN_SELECTION_RULE_BEFORE_CANDIDATE_RESULTS',dataset_commit=COMMIT,dataset_version='2.1.0',manifest_path=manifest.relative_to(ROOT).as_posix(),manifest_sha256=sha(manifest),version_sha256=sha(dataset/'eval/VERSION'),old_selection_path=oldpath.relative_to(ROOT).as_posix(),old_selection_sha256=sha(oldpath),excluded_case_ids=sorted(excluded),input_contract_path=contractpath.relative_to(ROOT).as_posix(),input_contract_sha256=sha(contractpath),full_population=72,excluded_count=24,remaining_count=48,sample_cases=24,seed=SEED,rule='Within each remaining family sort (operations,case_id); tertile j=floor(j*n/3):floor((j+1)*n/3); ascending SHA256(UTF8(seed+case_id)), ties by case_id. Select3 per Zipf/hotspot tertile and2 per lognormal tertile.',quotas={'random_zipf':9,'random_hotspot':9,'random_lognormal':6},prepare_script_sha256=sha(Path(__file__)),input_hash_scope='Reuse prior Root all72 full-input SHA contract; this preparation reads input headers only and rehashes metadata, not full inputs.',training=False,scheduler_runs=0,scope='New disjoint sample for this experiment, not guaranteed historically unseen. No threshold tuning on validation; no latest dataset-head tracking.')
 save(HERE/'config.json',config)
 contractrows={x['path']:x for x in contract['cases']};cases=[];strata=[]
 for family,expected,take in [('random_zipf',19,3),('random_hotspot',19,3),('random_lognormal',10,2)]:
  group=sorted([x for x in remaining if x['family']==family],key=lambda x:(x['operations'],Path(x['path']).stem));assert len(group)==expected
  for j in range(3):
   chunk=group[j*len(group)//3:(j+1)*len(group)//3]
   ranked=sorted(chunk,key=lambda x:(hashlib.sha256((SEED+Path(x['path']).stem).encode('utf8')).hexdigest(),Path(x['path']).stem));selected=ranked[:take]
   strata.append(dict(family=family,size_tertile=j,remaining_population=len(chunk),take=take,members=[dict(case_id=Path(x['path']).stem,N=x['operations'],selection_hash=hashlib.sha256((SEED+Path(x['path']).stem).encode()).hexdigest()) for x in chunk],selected=[Path(x['path']).stem for x in selected]))
   for x in selected:
    inp=dataset/x['path'];meta=inp.with_suffix('.meta.json');assert sha(meta)==x['metadata_sha256'];md=read(meta);spec=md['spec'];cr=contractrows[x['path']]
    assert cr['input_sha256']==x['sha256'] and cr['metadata_sha256']==x['metadata_sha256']
    with inp.open() as f:
     k,p,mem,w,r,penalty=map(int,f.readline().split());n,period=map(int,f.readline().split());headers=[list(map(int,f.readline().split())) for _ in range(k)]
    assert [h[0] for h in headers]==list(range(k)) and (k,p,mem,w,r,penalty,period)==tuple(spec[key] for key in ['k','p','memory','write','read','penalty','period'])
    assert n==x['operations']==md['operations'] and sum(h[2] for h in headers)==x['probe_count']==md['probe_count']
    assert sum(h[1] for h in headers)==md['insert_count'] and md['family']==spec['family']==family and md['split']=='eval'
    rel=inp.relative_to(ROOT).as_posix();cid=inp.stem
    assert cid not in excluded and x['sha256'] not in oldsha
    cases.append(dict(case_id=cid,case=inp.name,source_path='final_dataset/'+x['path'],family=family,size_tertile=j,selection_hash=hashlib.sha256((SEED+cid).encode()).hexdigest(),split='eval',input_path=rel,input_path_linux='${WORKSPACE}/'+rel,input_sha256=x['sha256'],metadata_path=meta.relative_to(ROOT).as_posix(),metadata_sha256=x['metadata_sha256'],stats={'probe_count':x['probe_count'],'penalty':penalty,'operations':n,'build_count':sum(h[1] for h in headers)},parameters=spec,header_validation=dict(k=k,p=p,memory=mem,write=w,read=r,penalty=penalty,period=period,operations=n,per_operator_counts=headers),full_input_sha_rehashed_here=False))
 cases.sort(key=lambda x:x['case_id']);assert len(cases)==len({x['case_id'] for x in cases})==24
 assert collections.Counter(x['family'] for x in cases)==config['quotas']
 identity=dict(member='final_dataset',version='2.1.0',files=sorted([dict(path=x['case'],sha256=x['input_sha256']) for x in cases]+[dict(path=Path(x['case']).with_suffix('.meta.json').as_posix(),sha256=x['metadata_sha256']) for x in cases],key=lambda x:x['path']))
 identity['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();identity['case_count']=24
 selection=dict(status='FROZEN_SAMPLE24_HEADERS_AND_METADATA_PASS',config_sha256=sha(HERE/'config.json'),dataset_commit=COMMIT,dataset_version='2.1.0',sampling_seed=SEED,cases=cases,strata=strata,dataset_identity=identity,case_count=24,family_counts=dict(collections.Counter(x['family'] for x in cases)),excluded_old_selection_sha256=sha(oldpath),old_case_overlap=0,old_input_sha_overlap=0,input_contract_path=config['input_contract_path'],input_contract_sha256=sha(contractpath),selected_before_r80_candidate_results=True,input_full_hash_inherited=True,input_full_hash_recomputed=False,semantic_validation=contract['semantic_validation'],scheduler_runs=0,training=False)
 save(HERE/'selection.json',selection)
 save(HERE/'audit.json',dict(status='PASS',cases=24,headers_checked=24,metadata_sha_checked=24,input_contract_bindings_checked=24,old_case_overlap=0,old_input_sha_overlap=0,full_input_hash_recomputed=False,selection_sha256=sha(HERE/'selection.json'),config_sha256=sha(HERE/'config.json'),total_selected_operations=sum(x['stats']['operations'] for x in cases),scheduler_runs=0))
 print(json.dumps(read(HERE/'audit.json'),indent=2))
if __name__=='__main__':main()
