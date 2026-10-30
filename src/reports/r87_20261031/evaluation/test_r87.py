"""Pure protocol tests. No scheduler, compiler, input-body scan or live producer."""
import copy,json,uuid,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
NAMES=['Naive','R75_dense_switch','R80_next_hier_fast100','R81_op256_cond2048','Van_latest','R85_fast_prior8','R85_hier_anchor','R87_fixedshare_op']
def load_scorer(p):
    spec=importlib.util.spec_from_file_location('score_under_test',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def fixed_candidate_test(s):
    cases=[dict(case_id=str(i),family='synthetic',original_split='eval',group='final',stats=dict(operations=1,probe_count=1,penalty=3)) for i in range(72)]
    selection=dict(mode='final',scope='synthetic',cases=cases,methods=[dict(name=x) for x in NAMES])
    rows=[]
    for c in cases:
        for name in NAMES:
            cost=10 if name=='Naive' else 8 if name=='R85_fast_prior8' else 7
            rows.append(dict(case_id=c['case_id'],method=name,valid=True,status='PASS',metrics=dict(Total_Score=cost,Total_IO_Time=cost-5,Total_Decision_Time=2,Miss_Count=1,Hit_Count=0)))
    result=s.summarize(selection,rows)
    assert result['complete'] and len(result['per_case'])==576
    entry=next(x for x in result['aggregate'] if x['method']=='R87_fixedshare_op')
    assert entry['direct_parent']=='R85_fast_prior8'
    assert abs(entry['average_score']-3)<1e-12
    assert abs(entry['references']['R85_fast_prior8']['mean_score_delta']-1)<1e-12
    return dict(selection=selection,rows=rows)
def rejects(fn):
    try:fn()
    except (AssertionError,ValueError):return
    raise AssertionError('invalid contract accepted')
def tests():
    import scoring,inventory as inv,regression as ex,test_full_contract
    fixed_candidate_test(scoring)
    inherited=test_full_contract.tests()
    # Fixed dataset identity is checked even when selection and supplied frozen
    # inventory are consistently changed to final3 (not merely mismatched).
    for mode,n in [('dyna',12),('final',72)]:
        inv.verify_dataset_identity(dict(dataset_commit=inv.COMMIT,dataset_tree=inv.TREES[mode],dataset_version=inv.VERSIONS[mode],case_count=n),mode)
        for key,value in [('dataset_commit','later'),('dataset_tree','changed'),('dataset_version','3.0.0'),('case_count',n-1)]:
            bad=dict(dataset_commit=inv.COMMIT,dataset_tree=inv.TREES[mode],dataset_version=inv.VERSIONS[mode],case_count=n);bad[key]=value
            rejects(lambda:inv.verify_dataset_identity(bad,mode))
    # Parent source/TU/ELF identity and old control dictionaries must survive.
    old=[]
    for name in NAMES[:-1]:old.append(dict(name=name,source_sha256=name+'src',translation_unit_sha256=name+'tu',binary_sha256=name+'elf'))
    p=next(x for x in old if x['name']=='R85_fast_prior8')
    candidate=dict(name=NAMES[-1],parent_name=p['name'],parent_sha256=p['source_sha256'],parent_translation_unit_sha256=p['translation_unit_sha256'],parent_binary_sha256=p['binary_sha256'])
    methods=ex.validate_method_contract(old,[candidate]);assert methods[:-1]==old
    for field in ['parent_sha256','parent_translation_unit_sha256','parent_binary_sha256']:
        bad=dict(candidate);bad[field]='changed';rejects(lambda:ex.validate_method_contract(old,[bad]))
    rejects(lambda:ex.validate_method_contract(old,[candidate,candidate]))
    rejects(lambda:ex.validate_method_contract(old,[dict(candidate,name='R80_paired_hier_fast100')]))
    return dict(status='PASS',candidate_actual_score_and_parent_delta=True,hard_fixed_dataset_identity=True,producer_parent_and_single_variant_guards=True,inherited=inherited,native_runs=0,compile_runs=0,input_body_scans=0)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--parent-red',action='store_true');a=p.parse_args()
    if a.parent_red:fixed_candidate_test(load_scorer(ROOT/'tmp/r85_full_eval/scoring.py'))
    else:print(json.dumps(tests(),indent=2))
