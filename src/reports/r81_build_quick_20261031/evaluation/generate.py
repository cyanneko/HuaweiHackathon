"""Three frozen sources for the isolated one-shot BUILD experiment."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PARENT=ROOT/'tmp/r81_named_20261031/MySpillScheduler.cpp'
PARENT_SHA='2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617'
ORIGINAL=ROOT/'tmp/r81_two_timescale/R81_op256_cond2048/MySpillScheduler.cpp'
ORIGINAL_TU=ORIGINAL.with_name('main.cpp')
NAIVE=ROOT/'tmp/r77_dyna_full_eval/sources/Naive.policy.cpp'
NAMES=['Naive','Full','BuildBestFit']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def generate():
    binding=json.loads((HERE/'candidate.binding.json').read_text(encoding='utf-8-sig'))
    assert sha(PARENT)==PARENT_SHA and binding['parent_sha256']==PARENT_SHA
    candidate=ROOT/binding['source_path'];assert sha(candidate)==binding['source_sha256']
    before,after=ORIGINAL_TU.read_bytes().split(ORIGINAL.read_bytes());records=[]
    for name,origin in [('Naive',NAIVE),('Full',PARENT),('BuildBestFit',candidate)]:
        folder=HERE/'sources'/name;folder.mkdir(parents=True,exist_ok=True)
        src=folder/'MySpillScheduler.cpp';unit=folder/'main.cpp';src.write_bytes(origin.read_bytes());unit.write_bytes(before+origin.read_bytes()+after)
        records.append(dict(name=name,source_path=src.relative_to(ROOT).as_posix(),source_sha256=sha(src),translation_unit_path=unit.relative_to(ROOT).as_posix(),translation_unit_sha256=sha(unit),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_source_sha256=PARENT_SHA if name!='Naive' else None))
    result=dict(status='TEXT_GENERATED_AWAIT_ROOT_GO',parent_path=PARENT.relative_to(ROOT).as_posix(),parent_sha256=PARENT_SHA,framework_prefix_sha256=hashlib.sha256(before).hexdigest(),framework_suffix_sha256=hashlib.sha256(after).hexdigest(),original_tu_sha256=sha(ORIGINAL_TU),original_policy_sha256=sha(ORIGINAL),methods=records,compile_runs=0,native_runs=0,input_body_scans=0,candidate_binding_sha256=sha(HERE/'candidate.binding.json'))
    (HERE/'source_manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result
