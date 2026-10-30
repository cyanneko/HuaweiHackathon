"""Explicit performance follow-up; user removed the hard D-ratio gate before validation."""
from pathlib import Path
import importlib.util, json, sys
BASE=Path(__file__).resolve().parent/'experiment.py'
spec=importlib.util.spec_from_file_location('r80_frozen_base',BASE);ex=importlib.util.module_from_spec(spec);spec.loader.exec_module(ex)
ROOT=ex.ROOT;HERE=ROOT/'tmp/r80_lazy_eval';ex.HERE=HERE
PARENTS={'R80_next_hier_fast100':'R80_next_hier100','R80_paired_hier_fast100':'R80_paired_hier100'}
read,save,sha,path=ex.read,ex.save,ex.sha,ex.path

def check_method(m):
 assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
 for f,k in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(m[f]))==m[k]
 source=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
 assert tu.count(source)==1
 assert ex.hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==read(ex.OLD/'config.json')['framework_skeleton_sha256']

def prepare(mode):
 old=read(ROOT/'tmp/r80_eval/train/selection.json');pp=ROOT/'tmp/r80_lazy_transfer/producer.json';prod=read(pp);release=read(pp.parent/'release.json')
 assert prod['status']=='READY' and release['final'] and release['ready'] and release['active_child_processes']==0 and release['producer_sha256']==sha(pp)
 assert read(pp.parent/'test_summary.json')['status']=='PASS'
 variants=prod['variants'];assert [m['name'] for m in variants]==list(PARENTS)
 deps=dict(old['dependencies'])
 for rel in ['tmp/r80_eval/train/selection.json','tmp/r80_eval/train/rows.json','tmp/r80_eval/train/summary.json','tmp/r80_eval/lazy_followup.py','tmp/r80_lazy_transfer/producer.json','tmp/r80_lazy_transfer/release.json','tmp/r80_lazy_transfer/test_summary.json']:
  deps[rel]=sha(ROOT/rel)
 if mode=='train':
  cases=old['cases'];methods=[next(m for m in old['methods'] if m['name']=='R79_adaptive')]+variants
  scope='26 frozen valid TRAIN, fresh R79 baseline plus2 lazy derivatives; compare physical observables to original156 cells'
 else:
  ds=read(ROOT/'tmp/r80_final_sample/selection.json');assert ds['case_count']==24 and ds['dataset_commit']=='f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246' and ds['dataset_version']=='2.1.0'
  original=read(ex.OLD/'selection.json');assert ds['excluded_old_selection_sha256']==sha(ex.OLD/'selection.json') and sha(ROOT/ds['input_contract_path'])==ds['input_contract_sha256']
  assert ds['family_counts']=={'random_zipf':9,'random_hotspot':9,'random_lognormal':6}
  assert not ({c['case_id'] for c in ds['cases']}&{c['case_id'] for c in original['cases']})
  assert not ({c['input_sha256'] for c in ds['cases']}&{c['input_sha256'] for c in original['cases']})
  chosen=read(HERE/'train/advance.json');assert chosen['complete'] and chosen['selected']
  assert chosen['training_summary_sha256']==sha(HERE/'train/summary.json')
  cases=ds['cases']
  for c in cases:c['input_path']=str(path(c['input_path_linux']));c['metadata_path']=str(path(c['metadata_path']));c['group']='final24'
  allmethods={m['name']:m for m in original['methods']+old['methods']+variants}
  methods=[allmethods[n] for n in ['Naive','R79_adaptive','Van_paired_penalty100']+chosen['selected']]
  assert 3<len(methods)<=5
  for rel in ['tmp/r80_final_sample/selection.json','tmp/r80_lazy_eval/train/advance.json',ds['input_contract_path']]:deps[rel]=sha(ROOT/rel)
  scope='final2.1.0 disjoint sample24 only; at most2 trained candidate families; no hard D-ratio veto per user instruction'
 for m in methods:check_method(m)
 for c in cases:assert sha(path(c['input_path']))==c['input_sha256'] and sha(path(c['metadata_path']))==c['metadata_sha256']
 selection=dict(old,mode=mode,scope=scope,cases=cases,methods=methods,dependencies=deps,planned_cells=len(cases)*len(methods),score='case-mean-v1' if mode=='final' else None,user_revision='Prioritize final Total_Score including D; D ratio is reported, not a hard elimination criterion. Revision before any R80 final run.',probability_math_changed=False)
 if mode=='final':selection.update(dataset_commit=ds['dataset_commit'],dataset_identity=ds['dataset_identity'])
 save(HERE/mode/'selection.json',selection);print(json.dumps(dict(prepared=mode,cases=len(cases),methods=len(methods),cells=selection['planned_cells'],selection_sha256=sha(HERE/mode/'selection.json'))))

def advance(summary,out):
 oldrows=read(ROOT/'tmp/r80_eval/train/rows.json');newrows=read(out/'rows.json');previous={(r['case_id'],r['method']):r for r in oldrows}
 checks=[]
 for r in newrows:
  parent=PARENTS.get(r['method'],r['method']);b=previous[r['case_id'],parent]
  checks.append(dict(case_id=r['case_id'],method=r['method'],parent=parent,input_same=r['input_sha256']==b['input_sha256'],IO_equal=r['metrics']['Total_IO_Time']==b['metrics']['Total_IO_Time'],hits_equal=r['metrics']['Hit_Count']==b['metrics']['Hit_Count'],misses_equal=r['metrics']['Miss_Count']==b['metrics']['Miss_Count']))
 good={m:all(c['input_same'] and c['IO_equal'] and c['hits_equal'] and c['misses_equal'] for c in checks if c['method']==m) for m in ['R79_adaptive']+list(PARENTS)}
 save(out/'equivalence.json',dict(status='PASS' if all(good.values()) else 'FAIL',checks=checks,per_method=good,scope='26 identical inputs per method: exact printed IO plus hit/miss counts, and separate400-step callback-action tests; not an every-action trace of all26'))
 groups={g:{m['method']:m for m in ms} for g,ms in summary['groups'].items()}
 previous_summary=read(ROOT/'tmp/r80_eval/train/summary.json');pg={g:{m['method']:m for m in ms} for g,ms in previous_summary['groups'].items()}
 choices=[]
 for fast,parent in PARENTS.items():
  # Choose the faster measured equivalent implementation of this already tested family.
  fast_ok=good[fast] and good['R79_adaptive']
  use_fast=fast_ok and groups['all'][fast]['D_ratio']<=pg['all'][parent]['D_ratio']
  chosen=fast if use_fast else parent;gg=groups if use_fast else pg
  new,old,all_=[gg[g][chosen] for g in ['new10','old16','all']]
  defined=new['cost_ratio']['n']==10 and old['cost_ratio']['n']==16 and all_['cost_ratio']['n']==26
  eligible=defined and new['cost_ratio']['mean']<1 and old['cost_ratio']['mean']<=1.05 and all_['cost_ratio']['worst']<=1.25
  choices.append(dict(method=chosen,parent_family=parent,eligible=eligible,implementation_reason='lazy physical observables matched and lower normalized D' if use_fast else 'retain frozen parent implementation',new10_mean=new['cost_ratio']['mean'],old16_mean=old['cost_ratio']['mean'],worst=all_['cost_ratio']['worst'],D_ratio=all_['D_ratio'],D_hard_veto=False))
 selected=[c['method'] for c in sorted(choices,key=lambda c:(c['new10_mean'],c['method'])) if c['eligible']][:2]
 save(out/'advance.json',dict(complete=True,selected=selected,choices=choices,training_summary_sha256=sha(out/'summary.json'),parent_training_summary_sha256=sha(ROOT/'tmp/r80_eval/train/summary.json'),equivalence_sha256=sha(out/'equivalence.json'),user_revision='Decision time may be longer; prioritize final score including D. Remove only the hard2x D gate before validation; retain cost/regression guards.',no_final_scores_consulted=True))

if __name__=='__main__':
 p=ex.argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('mode',choices=['train','final']);p.add_argument('--cpu-window-released',action='store_true');args=p.parse_args()
 if args.action=='prepare':prepare(args.mode)
 else:
  assert args.cpu_window_released;ex.advance=advance;ex.run(args.mode)
