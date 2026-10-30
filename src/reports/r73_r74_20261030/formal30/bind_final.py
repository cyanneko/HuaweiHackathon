"""Bind Root's final reviewed candidates and release. Never compile/run a policy."""
import argparse,re
from common import O,ROOT,load,sha,locate,save,fixed,validate_release,verify_sources

def main():
 a=argparse.ArgumentParser();a.add_argument('--producer',required=True);a.add_argument('--release-evidence',required=True);args=a.parse_args()
 producer_path=locate(args.producer);producer=load(producer_path);evidence=locate(args.release_evidence);release=load(evidence)
 validate_release(release);template=load(O/'precommit.template.json');controls=load(O/'controls.frozen.json')
 assert release['scope']==template['scope'] and release['producer_sha256']==sha(producer_path)
 assert sha(O/'controls.frozen.json')==template['source_control_sha256']
 assert sha(O/'cases.r72_frozen.json')==template['case_manifest_sha256']
 assert sha(O/'normalization_reference.r72.json')==template['normalization_reference_sha256']
 candidates=producer['candidates'];assert [m['name'] for m in candidates]==['R74_operator','R74_coverage','R74_size']
 repeats=producer.get('repeats',1);assert type(repeats) is int and repeats==1
 methods=list(controls['controls']);pending=[]
 for m in candidates:
  m=dict(m);assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',m['name']) and m['name'] not in [r['name'] for r in methods]
  m['framework_sha256']=controls['controls'][0]['framework_sha256']
  for key in ['source','translation_unit']:
   source=locate(m[key+'_path']);assert sha(source)==m[key+'_sha256']
   target=O/'sources/final'/(m['name']+('.policy.cpp' if key=='source' else '.cpp'))
   pending.append((m,key,target,source))
  methods.append(m)
 selection={k:controls[k] for k in ['framework_skeleton_sha256','process_helper_path','process_helper_sha256','parser_path','parser_sha256']}
 selection['methods']=methods;verify_sources(selection)
 for m,key,target,source in pending:
  target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():assert target.read_bytes()==source.read_bytes()
  else:target.write_bytes(source.read_bytes())
  m[key+'_path']=target.relative_to(ROOT).as_posix()
 verify_sources(selection);fixed(O/'selection.json',selection)
 p=dict(template);p.update(status='final_frozen_before_policy_launch',methods=[m['name'] for m in methods],candidate_slots=[m['name'] for m in candidates],
  repeats=repeats,repeats_status='Root final frozen repeat count',intended_cells=6*len(methods)*repeats,
  selection_sha256=sha(O/'selection.json'),producer_path=args.producer,producer_sha256=sha(producer_path))
 fixed(O/'precommit.json',p)
 release.update(selection_sha256=sha(O/'selection.json'),precommit_sha256=sha(O/'precommit.json'),runner_sha256=sha(O/'run_formal.py'),
  common_sha256=sha(O/'common.py'),max_cells=p['intended_cells'],repeats=repeats,release_evidence_path=args.release_evidence,release_evidence_sha256=sha(evidence))
 fixed(O/'cpu_release.json',release)
 print(f'Final R74 frozen: {len(methods)} methods x 6 cases x {repeats} repeats = {p["intended_cells"]} cells. Policy launches0, compiles0.')
if __name__=='__main__':main()
