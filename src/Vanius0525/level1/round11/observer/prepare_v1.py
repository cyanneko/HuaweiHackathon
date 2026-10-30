"""Create/reverse-check the instrumented source; never compiles or runs a solver."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def put(p,data):
    if p.exists():assert p.read_bytes()==data,p
    else:p.write_bytes(data)


def save(p,data):put(p,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())


def main():
    reference=ROOT/'round10/R80_next_hier_fast100_reference.cpp';raw=reference.read_bytes()
    assert sha(reference)=='0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d'
    old=b'class MySpillScheduler : public SpillScheduler {';new=b'class R80ObservedReference : public SpillScheduler {'
    assert raw.count(old)==1 and raw.endswith(b'};\r\n')
    support=(HERE/'log_support_v1.hpp').read_bytes();helper=(HERE/'copy_observer_v1.hpp').read_bytes();wrapper=(HERE/'wrapper_v1.hpp').read_bytes()
    renamed=raw.replace(old,new,1);body=renamed[:-4]+helper+b'};\r\n'
    # Add includes first; support uses public reference declarations, already supplied by the unchanged engine TU.
    includes=b'#include <algorithm>\n#include <cmath>\n#include <vector>\n#include <cstdint>\n'
    source=includes+support+b'\n'+body+b'\n'+wrapper
    recovered=source[len(includes+support+b'\n'):-(len(b'\n'+wrapper))]
    assert recovered.endswith(helper+b'};\r\n')
    recovered=recovered[:-(len(helper)+4)]+b'};\r\n'
    recovered=recovered.replace(new,old,1);assert recovered==raw
    policy=HERE/'r80_observer_v1.cpp';put(policy,source)
    diff=''.join(difflib.unified_diff(raw.decode().splitlines(keepends=True),source.decode().splitlines(keepends=True),
               fromfile='round10/R80_next_hier_fast100_reference.cpp',tofile='round11/observer/r80_observer_v1.cpp'))
    put(HERE/'INSTRUMENTATION_V1.patch',diff.encode())
    save(HERE/'SOURCE_RECOVERY_V1.json',{'reference_sha256':sha(reference),'instrumented_sha256':sha(policy),
       'reverse_recovers_original_exact_bytes':True,'original_crlf_count':raw.count(b'\r\n'),'instrumented_crlf_count':source.count(b'\r\n'),
       'original_callback_release_propose_prune_record_bytes_unchanged':True,
       'only_original_code_change':'Class renamed; helper inserted at class end; wrapper appended.'})
    oldplan=ROOT/'round10/PLAN_V1.json';p=json.loads(oldplan.read_text());cases=[c for c in p['cases'] if c['family']=='random_zipf'][:2]
    assert [Path(c['case']).stem.split('_')[1] for c in cases]==['548','593']
    resultpath=ROOT/'round10/RESULTS_V1.json';results=json.loads(resultpath.read_text());bycase={r['case']:r for r in results['records']}
    bound=[]
    for c in cases:
        path=ROOT/c['input'];assert sha(path)==c['input_sha256'];record=bycase[c['case']]
        prefix=ROOT/'build/round10_r80_v1'/Path(c['case']).stem/'r80'
        stdout=Path(str(prefix)+'.stdout');stderr=Path(str(prefix)+'.stderr')
        assert sha(stdout)==record['runs']['r80']['stdout_sha256'] and sha(stderr)==record['runs']['r80']['stderr_sha256']
        bound.append(dict(c,reference_run=record['runs']['r80'],reference_stdout=str(stdout.relative_to(ROOT)),
                          reference_stderr=str(stderr.relative_to(ROOT))))
    names=['CONTRACT_V1.md','.gitattributes','prepare_v1.py','log_support_v1.hpp','copy_observer_v1.hpp','wrapper_v1.hpp',
           'r80_observer_v1.cpp','INSTRUMENTATION_V1.patch','SOURCE_RECOVERY_V1.json','run_v1.py','audit_v1.py']
    for n in ('prepare_v1.py','run_v1.py','audit_v1.py'):ast.parse((HERE/n).read_text())
    dependencies=[oldplan,resultpath,reference,ROOT/'round10/EXECUTION_FREEZE_V1.json',ROOT/'round10/diagnostic/FINAL_FREEZE_V2.json',
                  HERE.parent/'MECHANISM_NOTES_V1.md',ROOT/'build.py',ROOT/'workflow.py']
    save(HERE/'BUILD_FREEZE_V1.json',{'stage':'fixed-two-R80-copy-observer-v1','cases':bound,'thresholds':[256,1024,4096],
       'files':{n:sha(HERE/n) for n in names},'dependencies':{str(p.relative_to(ROOT)):sha(p) for p in dependencies},
       'maximum_instrumented_solver_runs':2,'new_reference_solver_runs':0,'new_performance_runs':0,
       'new_teacher_runs':0,'dev_eval_dyna_inputs':0,'status':'Source prepared only; root pre-run review required.'})
    print('prepared without compiling/running',sha(HERE/'BUILD_FREEZE_V1.json'))


if __name__=='__main__':main()
