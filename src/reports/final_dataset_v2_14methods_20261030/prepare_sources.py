"""Freeze reviewed source inputs; no compilation, solver, or shared Git writes."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

O=Path(__file__).resolve().parent
ROOT=O.parents[2]
REPO=ROOT/'github-project'
CY='336291b14976b3f0c58c3f3213ef444bc20fb5d8'
VAN='9c755a71b26f5a0937dbbfc7edf68272b3510e72'
LIU='0c6d963a1fcc364ecdf763c638571358928bab42'
DATA='33ab5af221069fe8b8832fd77e85563e9997633a'
SIDE=ROOT/'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030'
REF=ROOT/'hashjoin_lab/reports/collaboration_20261020/round49_latency_baseline/reference_compilable.cpp'

def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args])
def blob(ref,path):return git('show',ref+':'+path)
def put(path,raw):
    path=O/path;path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=raw:raise ValueError('Frozen file differs: '+str(path))
    path.write_bytes(raw)
def save(path,x):put(path,(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())

reference=REF.read_bytes()
text=reference.decode('utf-8').replace('\r\n','\n')
a=text.index('class NaiveSpillScheduler');z=text.index('/* ===== 执行引擎',a)
prefix,suffix=text[:a],text[z:]
assert suffix.count('std::make_unique<NaiveSpillScheduler>()')==1
put(Path('sources/framework.cpp'),reference)

definitions=[
 ('Naive','official baseline',CY,'src/methods/r49/official_naive.cpp'),
 ('VanLegacy','historical pure reference',VAN,'src/Vanius0525/level1/MySpillScheduler.cpp'),
 ('VanBest','author current preferred candidate',VAN,'src/Vanius0525/level1/MySpillSchedulerBest.cpp'),
 ('VanRobust','author robustness alternative',VAN,'src/Vanius0525/level1/round4/pure_set025_all_probe_routecount.cpp'),
 ('VanAI2048','author current AI alternative',VAN,'src/Vanius0525/level1/round4/ai_prefetch_budget2048.cpp'),
 ('LiuFinal','historical rule reference',LIU,'design/MySpillScheduler_final.cpp'),
 ('LiuTree','author current preferred candidate',LIU,'design/MySpillScheduler_tree.cpp'),
 ('LiuNeural','author retained NN alternative',LIU,'design/MySpillScheduler_neural.cpp'),
 ('SingleFit','established rule reference',CY,'src/experts/single_fit_phase/reference.cpp'),
 ('R63','experimental predecessor',CY,'src/experiments/r63_ghost_refault64/scheduler_snapshot.cpp'),
 ('R65','experimental current rule',CY,'src/experiments/r65_turnover_risk/MySpillScheduler.cpp'),
 ('Clean','experimental same-family ablation','local-frozen',str(SIDE/'vanius_analysis/variants/Clean.cpp')),
 ('FitTie','experimental same-family ablation','local-frozen',str(SIDE/'vanius_analysis/variants/FitTie.cpp')),
 ('BBP','experimental diagnostic comparison','local-frozen',str(SIDE/'MySpillScheduler.cpp')),
]
methods=[]
expected={'VanBest':'2cd6440fb6e78a406a9abac1cab642a98ec94bd07f46f2e55f641d04a23ae1db',
 'LiuTree':'9b9238d7e9d7a1e65e4f37789c8c770673cc38beadc5db76c65ddae6e545b253',
 'R65':'f9eebb4dc44fc2059ed79879334a7bc5c6960d57f0b2453273be64accd617355',
 'Clean':'c4710e0de3e0928420dcfd2af658c8ca49a1a38f83bde45bc10c1b45ae63548a',
 'FitTie':'b59313d5f60aa8478f84bf576ea5e674b67191e59b0bd27783ea2126b59a90a5',
 'BBP':'4ff9618b68e31f305222da964b406be4dad06191f211c333ccd5f738a44af6f2'}
for name,role,ref,path in definitions:
    raw=Path(path).read_bytes() if ref=='local-frozen' else blob(ref,path)
    if name in expected:assert sha(raw)==expected[name],(name,sha(raw))
    body=raw.decode('utf-8-sig').replace('\r\n','\n')
    assert 'class HashJoinEngine' not in body and not re.search(r'\bint\s+main\s*\(',body),name
    assert not re.search(r'^\s*#\s*include\s*"',body,re.M),(name,'external dependency')
    assert not re.search(r'\b(?:fopen|ifstream|freopen|system|popen|setenv|getenv)\s*\(',body),(name,'side effect requires review')
    full=(prefix+body+'\n'+suffix.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<MySpillScheduler>()')).encode('utf-8')
    source_rel=Path('sources')/(name+'.policy.cpp');full_rel=Path('sources')/(name+'.cpp')
    put(source_rel,raw);put(full_rel,full)
    methods.append(dict(name=name,role=role,source_commit=ref,source_path=path,
        source_sha256=sha(raw),policy=str(source_rel).replace('\\','/'),
        translation_unit=str(full_rel).replace('\\','/'),translation_unit_sha256=sha(full),
        framework_sha256=sha(reference),binary_sha256=None))

updates=[]
for owner,old,new,docs in [
 ('Vanius0525','32fbc8a069ac13a7ba98856e1a25888b6cb50060',VAN,
  ['src/Vanius0525/level1/CURRENT_CANDIDATE.json','src/Vanius0525/level1/README.md','src/Vanius0525/level1/round4/HANDOFF.md']),
 ('liunianwww','d25e10ca99a163e122e60225907805c8db44b310',LIU,
  ['design/CURRENT_SOLUTION.txt','design/README.txt','design/portfolio_iter_20261029/published_checkpoint.json'])]:
    changed=git('diff','--name-only',old,new).decode().splitlines()
    for path in docs:put(Path('recommendation_sources')/owner/path,blob(new,path))
    stable=[]
    for m in methods:
        if m['source_commit']!=new:continue
        try:previous=blob(old,m['source_path'])
        except subprocess.CalledProcessError:previous=None
        stable.append(dict(name=m['name'],path=m['source_path'],sha256=m['source_sha256'],
                           previous_sha256=sha(previous) if previous is not None else None,
                           changed=previous!= (O/m['policy']).read_bytes()))
    updates.append(dict(owner=owner,previous_snapshot=old,current_snapshot=new,
        changed_file_count=len(changed),changed_cpp=[p for p in changed if p.endswith('.cpp')],
        selected_method_changes=stable))
save(Path('teammate_updates.json'),updates)
save(Path('selection.json'),dict(scope='final_dataset_v2_50_online',data_commit=DATA,
    data_version='2.0.0',eval_cases=50,method_count=len(methods),repeats=3,
    intended_cells=50*len(methods)*3,methods=methods,
    compiler_flags=['-std=c++14','-O2'],framework_source=str(REF),framework_sha256=sha(reference),
    preparation_only=True,source_freezer_sha256=sha(Path(__file__).read_bytes())))
print(json.dumps(dict(methods=len(methods),intended_cells=50*len(methods)*3,
    source_hashes={m['name']:m['source_sha256'] for m in methods},compiler_runs=0,solver_runs=0),ensure_ascii=False))
