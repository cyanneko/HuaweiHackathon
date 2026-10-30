"""Deterministic text-only children; no compiler, native process or benchmark IO."""
from pathlib import Path
import difflib,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PARENT=ROOT/'tmp/r81_named_20261031/MySpillScheduler.cpp'
PARENT_SHA='2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617'
ORIGINAL=ROOT/'tmp/r81_two_timescale/R81_op256_cond2048/MySpillScheduler.cpp'
ORIGINAL_TU=ORIGINAL.with_name('main.cpp')
NAIVE=ROOT/'tmp/r77_dyna_full_eval/sources/Naive.policy.cpp'
NAMES=['Naive','Full','FixedShare075','UnifiedSlow2048','NoPeriodicPrefetch','NoNextProtection','UnitMissCost','NoStructurePolicy','UniformOperatorMarginal']
EDITS={
 'FixedShare075':[('g.share = .75 / (1. + strength);','g.share = .75; // Ablation: fixed operator-internal sharing.')],
 'UnifiedSlow2048':[('#define HASHJOIN_OPERATOR_HALF_LIFE 256','#define HASHJOIN_OPERATOR_HALF_LIFE 2048')],
 'NoPeriodicPrefetch':[('        release(s, op, pid, part.data_size, a);\n        pruneSpills(s, s.operators[op].partitions[pid].data_size, a);\n        a.emplace_back(Action::LOAD, op, pid);\n        record(s, a);',
                         '        // Ablation: retain update and analysis, return no periodic actions.')],
 'NoNextProtection':[('if ((o == op && pa == pid) || (o == next_op && pa == next_pid))','if ((o == op && pa == pid))'),
                      ('                if (o.op_id == next_op && part.partition_id == next_pid)\n                    priority += 1e12;',
                       '                // Ablation: no next-request priority protection.')],
 'UnitMissCost':[('double priority = reuse * (1.0 / s.read_bandwidth\n                    + 1.0 / s.write_bandwidth + 100.0 / part.data_size);',
                  'double priority = reuse / part.data_size; // Ablation: unit miss-cost density.'),
                 ('loss += v.priority * v.bytes\n                            + 0.25 * static_cast<double>(v.bytes) / s.write_bandwidth;',
                  'loss += v.priority * v.bytes; // Ablation: no extra write-cost term.')],
 'NoStructurePolicy':[('uniform_cycle_ = (j == n);','uniform_cycle_ = false; // Ablation: disable cycle policy, retain observations.'),
                       ('const bool scan = streak_ >= 6 && stride_ > 0 && observed_count_ * 2 > now;',
                        'const bool scan = false; // Ablation: disable scan policy, retain observations.')],
 'UniformOperatorMarginal':[('const double marginal = (fast_operator_[op].mass + op_prior) / fast_denom;',
                              'const double marginal = 1. / k; // Ablation: uniform operator marginal.')],
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def transform(parent,edits):
    result=parent
    for old,new in edits:
        assert result.count(old)==1,(old,result.count(old))
        result=result.replace(old,new,1)
    return result
def generate():
    assert sha(PARENT)==PARENT_SHA
    original=ORIGINAL.read_bytes();tu=ORIGINAL_TU.read_bytes();assert tu.count(original)==1
    prefix,suffix=tu.split(original);parent=PARENT.read_text(encoding='utf-8')
    oldnaive=json.loads((ROOT/'tmp/r87_eval/methods.prepared.json').read_text(encoding='utf-8-sig'))['methods'][0]
    assert oldnaive['name']=='Naive' and sha(NAIVE)==oldnaive['source_sha256']
    records=[]
    for name in NAMES:
        policy=NAIVE.read_bytes() if name=='Naive' else PARENT.read_bytes() if name=='Full' else transform(parent,EDITS[name]).encode('utf-8')
        folder=HERE/'sources'/name;folder.mkdir(parents=True,exist_ok=True)
        source=folder/'MySpillScheduler.cpp';unit=folder/'main.cpp'
        source.write_bytes(policy);unit.write_bytes(prefix+policy+suffix)
        records.append(dict(name=name,source_path=source.relative_to(ROOT).as_posix(),source_sha256=sha(source),translation_unit_path=unit.relative_to(ROOT).as_posix(),translation_unit_sha256=sha(unit),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_source_sha256=PARENT_SHA if name!='Naive' else None,approved_edits=[dict(before=a,after=b) for a,b in EDITS.get(name,[])]))
        if name in EDITS:
            patch=HERE/'patches'/(name+'.diff');patch.parent.mkdir(exist_ok=True)
            patch.write_text(''.join(difflib.unified_diff(parent.splitlines(True),policy.decode().splitlines(True),fromfile='Full/MySpillScheduler.cpp',tofile=name+'/MySpillScheduler.cpp')),encoding='utf-8')
    # Test-only declarations expose internal state; namespaces/classes are unique.
    # These transformations never touch timing sources above.
    test_prefix=prefix
    tests=[test_prefix.decode('utf-8')]
    for rec in records[1:]:
        name=rec['name'];src=(ROOT/rec['source_path']).read_text(encoding='utf-8')
        tests.extend(['\n#undef HASHJOIN_OPERATOR_HALF_LIFE\n#undef HASHJOIN_REUSE_ESTIMATOR\n#undef HASHJOIN_ADAPTIVE_RISK_SHARING\n#undef HASHJOIN_REFAULT_MODEL\n#undef HASHJOIN_SIZE_BIAS\n',
          src.replace('namespace r74 {','namespace '+name+'Risk {').replace('r74::',name+'Risk::').replace('namespace r75op {','namespace '+name+'OpRisk {').replace('r75op::',name+'OpRisk::').replace('class MySpillScheduler : public SpillScheduler {','class '+name+' : public SpillScheduler {\npublic:')])
    (HERE/'effectiveness.generated.hpp').write_text(''.join(tests),encoding='utf-8')
    manifest=dict(status='TEXT_GENERATED_AWAIT_ROOT_GO',parent_path=PARENT.relative_to(ROOT).as_posix(),parent_sha256=PARENT_SHA,framework_prefix_sha256=hashlib.sha256(prefix).hexdigest(),framework_suffix_sha256=hashlib.sha256(suffix).hexdigest(),original_tu_sha256=sha(ORIGINAL_TU),original_policy_sha256=sha(ORIGINAL),methods=records,compile_runs=0,native_runs=0,input_body_scans=0)
    save(HERE/'source_manifest.json',manifest);return manifest
if __name__=='__main__': print(json.dumps(dict(status=generate()['status'],methods=len(NAMES),native_runs=0)))
