"""Freeze small rules, methods and a score-blind 24-case selection; never run solvers."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
COMMIT='f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246';SEED='r79-final-sample-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def main():
 assert not (HERE/'config.json').exists(),'freeze once; no silent overwrite'
 files=['evaluation/evaluate.py','evaluation/scripts/audit_datasets.py','evaluation/scripts/summarize_member_scores.py','evaluation/README.md','evaluation/MEMBER_SCORING.md','final_dataset/eval/VERSION','final_dataset/README.md']
 snapshots={}
 for path in files:
  raw=subprocess.check_output(['git','-C',str(ROOT/'github-project'),'show',COMMIT+':'+path]);p=HERE/'dependencies'/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);snapshots[path]=sha(p)
 assert (HERE/'dependencies/final_dataset/eval/VERSION').read_text().strip()=='2.1.0'
 old=json.loads((ROOT/'tmp/r77_dyna_full_eval/selection.json').read_text());producer=ROOT/'tmp/r79_adaptive_operator/producer.json';assert sha(producer)=='6522a912da33450e8b5f7dfd6a9ae12b4439adf35ff1deec05926d9bbd9df4a4'
 methods=old['methods']+json.loads(producer.read_text())['variants'];assert len(methods)==5
 for m in methods:
  source=ROOT/m['source_path'];tu=ROOT/m['translation_unit_path'];assert sha(source)==m['source_sha256'] and sha(tu)==m['translation_unit_sha256']
  text=tu.read_text(encoding='utf-8-sig');policy=source.read_text(encoding='utf-8-sig');assert text.count(policy)==1
  assert hashlib.sha256(text.replace(policy,'<SCHEDULER>').encode()).hexdigest()==old['framework_skeleton_sha256']
  assert m['instrumented'] is False and m['compile_flags']==['-std=c++14','-O2']
 helper=ROOT/old['process_helper_path'];assert sha(helper)==old['process_helper_sha256'];(HERE/'process_helper.py').write_bytes(helper.read_bytes())
 dataset=ROOT/'tmp/d70/final_dataset';manifest=dataset/'manifest.json';assert sha(manifest)=='217e8e24ad6fcf6c1c057bb2031d5cde23fe2e2b35595b095d119922a47aee87'
 assert sha(dataset/'eval/VERSION')=='c89b87c262e9d5ffd20e73aac74a1772adcc9f5a21682cc33adcf5086e5fef5c'
 data=json.loads(manifest.read_text());allcases=[c for c in data['cases'] if c['split']=='eval'];assert len(allcases)==72 and sum(c['operations'] for c in allcases)==22528629
 picked=[];strata=[]
 for family,expected,take in [('random_zipf',28,3),('random_hotspot',28,3),('random_lognormal',16,2)]:
  group=sorted([c for c in allcases if c['family']==family],key=lambda c:(c['operations'],Path(c['path']).stem));assert len(group)==expected
  for j in range(3):
   chunk=group[j*len(group)//3:(j+1)*len(group)//3]
   scored=sorted([(hashlib.sha256((SEED+Path(c['path']).stem).encode()).hexdigest(),c) for c in chunk],key=lambda pair:(pair[0],pair[1]['path']))
   selected=scored[:take];strata.append(dict(family=family,size_tertile=j,population=len(chunk),take=take,members=[Path(c['path']).stem for c in chunk],selected=[Path(c['path']).stem for _,c in selected]))
   for h,c in selected:
    inp=dataset/c['path'];meta=inp.with_suffix('.meta.json');assert sha(meta)==c['metadata_sha256'];md=json.loads(meta.read_text());spec=md['spec'];rel=inp.relative_to(ROOT).as_posix()
    picked.append(dict(case_id=inp.stem,case=inp.name,source_path='final_dataset/'+c['path'],family=family,size_tertile=j,selection_hash=h,split='eval',input_path=rel,input_path_linux='${WORKSPACE}/'+rel,input_sha256=c['sha256'],metadata_path=meta.relative_to(ROOT).as_posix(),metadata_sha256=c['metadata_sha256'],stats={'probe_count':c['probe_count'],'penalty':spec['penalty'],'operations':c['operations']},parameters=spec))
 picked.sort(key=lambda c:c['case_id']);assert len(picked)==24
 identity={'member':'final_dataset','version':'2.1.0','files':sorted([{'path':c['case'],'sha256':c['input_sha256']} for c in picked]+[{'path':Path(c['case']).with_suffix('.meta.json').as_posix(),'sha256':c['metadata_sha256']} for c in picked],key=lambda v:v['path'])}
 identity['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();identity['case_count']=24
 config=dict(scope='r79_final_v21_stratified_sample24',dataset_commit=COMMIT,dataset_version='2.1.0',full_population_cases=72,case_count=24,method_count=5,intended_cells=120,repeats=1,per_case_wall_limit_seconds=60,controller_watchdog_seconds=180,controller_watchdog_is_official=False,scoring_version='case-mean-v1',protocol='official-2026-10-26',sampling_seed=SEED,sampling_rule='family N ascending then case_id; tertile j uses floor(j*n/3):floor((j+1)*n/3); choose smallest SHA256(UTF8(seed+case_id)); zipf/hotspot3 per tertile, lognormal2; no outcomes',order_rule='case_id ascending; method order rotated left by case_index modulo5',ranking_scope='sample24 only; no full72 ranking or extrapolation',initial_measurement=True,failures='retain all120 planned cells; missing/failure makes main mean unavailable; optional failure-zero diagnostic fixed24 denominator only when all baselines valid',methods=[m['name'] for m in methods],framework_skeleton_sha256=old['framework_skeleton_sha256'],dependency_sha256=snapshots,process_helper_sha256=sha(HERE/'process_helper.py'),producer_sha256=sha(producer),dataset_manifest_sha256=sha(manifest),panel_release_path='tmp/r79_adaptive_eval/cpu_released.json',training=False,gpu=False)
 save(HERE/'config.json',config);save(HERE/'selection.prepared.json',dict(config_sha256=sha(HERE/'config.json'),methods=methods,cases=picked,strata=strata,dataset_identity=identity,selected_before_native=True,input_full_contract_pending=True))
 print(json.dumps({'status':'PREPARED_AWAITING_INPUT_CONTRACT','cases':24,'methods':5,'cells':120,'selection_sha256':sha(HERE/'selection.prepared.json')}))
if __name__=='__main__':main()
