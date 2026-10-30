"""Reproduce the frozen strict partition-skew package using Python standard library."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import base_random_workloads as base
from fast_allocation import allocate
from strict_weights import make_weights

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def validate_case_meta(meta,item):
    if (meta['spec']!=item['spec'] or meta['seed']!=item['build_seed'] or meta['probe_seed']!=item['probe_seed']):
        raise ValueError('Case seed/spec differs from frozen recipe: '+item['path'])
    expected_sizes=hashlib.sha256(json.dumps(meta['partition_sizes'],separators=(',',':')).encode()).hexdigest()
    if expected_sizes!=item['parent_partition_sizes_sha256'] or meta['insert_count']!=item['parent_insert_count']:
        raise ValueError('Reconstructed BUILD sizes changed for '+item['path'])
    k,p=meta['k'],meta['p'];counts=meta['probe_counts']
    if len(counts)!=k*p or sum(counts)!=item['spec']['probe_count'] or any(type(x) is not int or x<0 for x in counts):
        raise ValueError('Invalid observed counts: '+item['path'])
    cert=meta['probability_certificate'];joint=cert['joint_probabilities']
    if len(joint)!=k*p or len(set(joint))!=k*p or not all(math.isfinite(x) and x>0 for x in joint) or abs(math.fsum(joint)-1)>1e-12:
        raise ValueError('Target joint probability contract failed: '+item['path'])
    for op in range(k):
        values=counts[op*p:(op+1)*p];total=sum(values)
        if total==0 or sum(x>0 for x in values)<2 or .5*math.fsum(abs(x/total-1/p) for x in values)<.10:
            raise ValueError('Observed skew contract failed; no seed retry: '+item['path'])
        target=cert['conditional_probabilities'][op]
        if len(set(target))!=p or .5*math.fsum(abs(x-1/p) for x in target)<.20 or max(target)/min(target)<2:
            raise ValueError('Target conditional skew contract failed: '+item['path'])

def make_case(args):
    package_s,item,recipe_sha,tool_sha,resume=args
    package=Path(package_s);path=package/item['path'];meta_path=path.with_suffix('.meta.json')
    if path.exists() or meta_path.exists():
        if not(resume and path.is_file() and meta_path.is_file()):raise ValueError('Refusing to overwrite '+item['path'])
        meta=load(meta_path)
        if meta['recipe_sha256']!=recipe_sha or meta['sha256']!=digest(path):raise ValueError('Resume bytes/recipe mismatch')
        validate_case_meta(meta,item)
        return row_from_meta(item,path,meta_path,meta)
    captured={}
    def new_weights(spec,unused_base_rng,q):
        weights,certificate=make_weights(spec,random.Random(item['probe_seed']),q)
        captured['certificate']=certificate
        return weights
    base._allocate=allocate
    base._probe_weights=new_weights
    data,meta=base.construct(item['spec'],item['build_seed'])
    expected_sizes=hashlib.sha256(json.dumps(meta['partition_sizes'],separators=(',',':')).encode()).hexdigest()
    if expected_sizes!=item['parent_partition_sizes_sha256'] or meta['insert_count']!=item['parent_insert_count']:
        raise ValueError('Reconstructed BUILD sizes changed for '+item['path'])
    cert=captured['certificate'];p=meta['p'];observed=[]
    for op in range(meta['k']):
        counts=meta['probe_counts'][op*p:(op+1)*p];total=sum(counts)
        if total==0:raise ValueError('No observed PROBE for operator '+str(op))
        tv=0.5*math.fsum(abs(value/total-1/p) for value in counts)
        observed.append(dict(op_id=op,probes=total,tv_from_uniform=tv,
            distinct_observed_partitions=sum(value>0 for value in counts),zero_count_partitions=sum(value==0 for value in counts)))
    meta.update(schema_version=4,version='3.0.0',recipe_sha256=recipe_sha,
        generator_source='final_dataset/tools/generate.py',generator_sha256=tool_sha['generate.py'],
        base_generator_sha256=tool_sha['base_random_workloads.py'],strict_weights_sha256=tool_sha['strict_weights.py'],
        generation_method='Parent BUILD recipe; independently seeded strict per-operator conditional PROBE probabilities; IID joint draws.',
        probability_certificate=cert,observed_partition_heat=observed,probe_seed=item['probe_seed'],
        source_member='strict_partition_synthetic',parent=dict(commit=load(package/'recipe.json')['source_data_commit'],
            path=item['parent_path'],sha256=item['parent_input_sha256'],metadata_sha256=item['parent_metadata_sha256']),
        no_score_based_selection=True,actual_production_trace=False,official_distribution_claim=False,
        per_operator_target_tv_min=min(x['tv_from_uniform'] for x in cert['per_operator']),
        per_operator_observed_tv_min=min(x['tv_from_uniform'] for x in observed))
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data)
    with meta_path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(meta,stream,ensure_ascii=False,indent=2);stream.write('\n')
    validate_case_meta(meta,item)
    return row_from_meta(item,path,meta_path,meta)

def row_from_meta(item,path,meta_path,meta):
    return dict(path=item['path'],split=item['split'],family=item['family'],sha256=meta['sha256'],metadata_sha256=digest(meta_path),
        operation_stream_sha256=meta['operation_stream_sha256'],partition_stream_sha256=meta['partition_stream_sha256'],
        file_bytes=path.stat().st_size,k=meta['k'],p=meta['p'],memory=meta['memory'],operations=meta['operations'],
        insert_count=meta['insert_count'],probe_count=meta['probe_count'],build_bytes=meta['build_bytes'],
        pressure=meta['realized_pressure'],max_partition_bytes=meta['max_partition_bytes'],
        per_operator_target_tv_min=meta['per_operator_target_tv_min'],per_operator_observed_tv_min=meta['per_operator_observed_tv_min'],
        positive_partition_size_ratio=max(meta['partition_sizes'])/min(meta['partition_sizes']),parent_path=item['parent_path'])

def run(args):
    package=args.package.resolve();recipe_path=package/'recipe.json';recipe=load(recipe_path);recipe_sha=digest(recipe_path)
    if recipe['version']!='3.0.0' or len(recipe['generated_cases'])!=612:raise ValueError('Unexpected frozen recipe')
    for name,expected in recipe['tool_sha256'].items():
        if digest(package/'tools'/name)!=expected:raise ValueError('Frozen tool changed: '+name)
    cases=[];failures=[]
    tasks=[(str(package),item,recipe_sha,recipe['tool_sha256'],args.resume) for item in recipe['generated_cases']]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures={pool.submit(make_case,task):task[1]['path'] for task in tasks}
        for future in as_completed(futures):
            try:cases.append(future.result())
            except Exception as exc:failures.append(dict(path=futures[future],error=str(exc)))
            if (len(cases)+len(failures))%12==0 or failures:
                print(json.dumps(dict(generated=len(cases),failed=len(failures),expected=len(tasks))),flush=True)
    if failures:
        save(package/'reports/generation_failures.json',dict(status='failed',failures=failures));return 1
    cases.sort(key=lambda item:item['path'])
    for key in ('sha256','operation_stream_sha256','partition_stream_sha256'):
        if len({row[key] for row in cases})!=len(cases):raise ValueError('Duplicate '+key)
    summary={}
    for split in ('train','eval'):
        rows=[row for row in cases if row['split']==split]
        summary[split]=dict(cases=len(rows),families=dict(Counter(row['family'] for row in rows)),
            total_operations=sum(row['operations'] for row in rows),file_bytes=sum(row['file_bytes'] for row in rows),
            operations_min=min(row['operations'] for row in rows),operations_max=max(row['operations'] for row in rows),
            minimum_target_tv=min(row['per_operator_target_tv_min'] for row in rows),
            minimum_observed_tv=min(row['per_operator_observed_tv_min'] for row in rows),
            minimum_build_size_ratio=min(row['positive_partition_size_ratio'] for row in rows))
    manifest=dict(schema_version=4,name='final_dataset',version='3.0.0',source_revision=recipe['source_data_commit'],
        previous_release_version='2.1.0',recipe_sha256=recipe_sha,summary=summary,cases=cases,
        probability_contract=recipe['probability_contract'],strict_partition_heat_all_cases=True,
        official_hidden_distribution_claim=False,independent_blind_test=False,algorithm_runs=0,
        eval_exposure='New PROBE streams reuse previously exposed BUILD specs; no solver scores used and no blind-generalization claim.')
    save(package/'manifest.json',manifest)
    print(json.dumps(dict(status='generated',summary=summary,manifest_sha256=digest(package/'manifest.json'))),flush=True)
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--jobs',type=int,default=2);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if not 1<=args.jobs<=8:parser.error('--jobs must be1..8')
    raise SystemExit(run(args))

if __name__=='__main__':main()
