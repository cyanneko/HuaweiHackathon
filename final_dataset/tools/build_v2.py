"""Build v2: random large/skewed Hash Join inputs with 4% corners."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import secrets
import statistics
import sys

TOOLS=Path(__file__).resolve().parent
REPO=TOOLS.parents[1]
SOURCE_REVISION='750618cead2d8f9d815a47fd8217fdab23d786dd'
PREVIOUS_RELEASE='ee2ed4d5b10ac88b08d02a9d0fe10aefb09d38aa'
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')

def write_once(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=data:
        raise RuntimeError('Refuse to replace different frozen file: '+path.name)
    if not path.exists():path.write_bytes(data)

def signature(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        k,p=map(int,stream.readline().split()[:2]);h.update(f'{k} {p}\n'.encode())
        stream.readline()
        for _ in range(k):stream.readline()
        for line in stream:
            fields=line.split()
            if not fields:continue
            if fields[0] in (b'INSERT',b'PROBE'):fields[2]=str(int(fields[2])%p).encode()
            h.update(b' '.join(fields)+b'\n')
    return h.hexdigest()

def seed_for(master,label):
    return int.from_bytes(hashlib.sha256(f'final-dataset-v2/{master}/{label}'.encode()).digest()[:8],'big')

def make_specs(master):
    requests=[]
    family_counts={'train':{'random_uniform':90,'random_zipf':108,'random_hotspot':108,'random_lognormal':54},
        'eval':{'random_uniform':12,'random_zipf':14,'random_hotspot':14,'random_lognormal':8}}
    for split,counts in family_counts.items():
        rng=random.Random(seed_for(master,split+'/parameters'))
        families=[f for f,n in counts.items() for _ in range(n)];rng.shuffle(families)
        if split=='train':
            sizes=[rng.randint(32768,65535) for _ in range(100)]
            sizes += [rng.randint(65536,110000) for _ in range(200)]
            sizes += [rng.randint(110001,220000) for _ in range(52)]
            sizes += [rng.randint(262144,524288) for _ in range(8)]
        else:
            sizes=[rng.randint(65536,98303) for _ in range(12)]
            sizes += [rng.randint(98304,196607) for _ in range(24)]
            sizes += [rng.randint(196608,327679) for _ in range(10)]
            sizes += [rng.randint(327680,524287) for _ in range(2)]
        rng.shuffle(sizes)
        corners=20 if split=='train' else 2
        families += ['one_byte_over']*(corners//2)+['empty_partition_probe']*(corners//2)
        sizes += [rng.randint(32768,49152) for _ in range(corners)]
        for i,(family,n) in enumerate(zip(families,sizes)):
            edge=family in ('one_byte_over','empty_partition_probe')
            k=rng.choices([1,2,4,8],weights=[2,4,3,1])[0];p=rng.choice([8,16,32,64])
            if edge:k=1;p=rng.choice([8,16])
            memory=rng.choices([64,128,256,512],weights=[2,4,3,1])[0]*2**20
            nb=max(12000,int((n-k)*rng.uniform(.40,.65)))
            spec=dict(family=family,k=k,p=p,memory=memory,write=rng.randint(200,8000),
                read=rng.randint(200,8000),penalty=rng.randint(10,500),period=rng.randint(8,1000),
                build_count=nb,probe_count=n-k-nb,pressure=round(rng.uniform(1.15,4.0),6),
                tuple_cv=round(rng.uniform(.3,1.2),6),shape_alpha=round(rng.uniform(.9,1.65),6),
                hot_fraction=round(rng.uniform(.05,.25),6),hot_probability=round(rng.uniform(.70,.95),6))
            ident=i+(120 if split=='train' else 0)
            requests.append(dict(path=f'{split}/{split}_{ident:03d}_{family}.txt',split=split,
                family=family,seed=seed_for(master,f'{split}/{i}/{family}'),spec=spec))
    assert len(requests)==430
    return requests

def record_for(package,path,meta):
    a=audit_case(path,meta,enforce_limits=True);positive=[x for x in a['partition_sizes'] if x]
    return dict(path=path.relative_to(package).as_posix(),split=meta['split'],
        source_member=meta.get('source_member','new_synthetic'),source_path=meta.get('source_path'),
        source_sha256=meta.get('source_sha256'),family=meta['family'],business_scenario=meta['business_scenario'],
        is_edge=meta['is_edge'],edge_reason=meta['edge_reason'],sha256=a['sha256'],
        metadata_sha256=sha(path.with_suffix('.meta.json').read_bytes()),
        operation_stream_sha256=a['operation_stream_sha256'],partition_stream_sha256=signature(path),
        **{key:a[key] for key in ('operations','insert_count','probe_count','build_bytes','k','p','memory','pressure','phase_overlap','file_bytes')},
        positive_partition_size_ratio=max(positive)/min(positive) if positive else 0,
        max_probe_partition_share=a['max_probe_partition_share'])

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=TOOLS.parent)
    package=parser.parse_args(argv).out.resolve()
    if package.parent!=REPO:raise ValueError('Output package must be directly inside repository')
    package.mkdir(exist_ok=True)
    selection_path=TOOLS/'source_selection_v2.json'
    selection=json.loads(selection_path.read_text(encoding='utf-8'));source_paths=selection['paths']
    assert len(source_paths)==120
    recipe_path=package/'recipe.json'
    if recipe_path.exists():
        recipe=json.loads(recipe_path.read_text(encoding='utf-8'))
        if recipe.get('version')!='2.0.0':raise ValueError('Build v2 into a new directory; do not overwrite v1')
    else:
        master=secrets.token_hex(24)
        recipe=dict(schema_version=2,name='final_dataset',version='2.0.0',source_revision=SOURCE_REVISION,
            previous_release_revision=PREVIOUS_RELEASE,master_seed=master,frozen_before_generation=True,
            no_solver_or_scores=True,train_cases=500,eval_cases=50,train_regular=480,train_edge=20,eval_regular=48,eval_edge=2,
            edge_definition='Only explicit one-byte-over and empty-partition diagnostics; random skew and large volume are ordinary.',
            reused_training_source_counts={'cyanneko':2,'liunianwww':70,'Vanius0525':48},
            reused_training_paths=source_paths,source_selection_sha256=sha(selection_path.read_bytes()),
            generated_training_cases=380,generated_eval_cases=50,
            selection_policy='120 ordinary source train cases plus new iid random/skewed inputs; no old eval in training.',
            business_assumption='Synthetic large/skewed Hash Join inputs; not measured production traffic.',
            family_semantics={'random_uniform':'iid uniform partition requests','random_zipf':'iid permuted-rank Zipf requests',
                'random_hotspot':'iid hot/cold mixture','random_lognormal':'iid randomized lognormal probabilities'},
            scale_policy='All new ordinary N>=32768; at least 250/500 train and 48/50 eval N>=65536; both splits include N>=262144.',
            generator_sha256=sha((TOOLS/'random_workloads.py').read_bytes()),
            builder_sha256=sha(Path(__file__).read_bytes()),generated_cases=make_specs(master))
        write_once(recipe_path,encoded(recipe))
    assert recipe['generator_sha256']==sha((TOOLS/'random_workloads.py').read_bytes())
    assert recipe['builder_sha256']==sha(Path(__file__).read_bytes())
    assert recipe['source_selection_sha256']==sha(selection_path.read_bytes())
    manifests={}
    for member in ('cyanneko','liunianwww','Vanius0525'):
        m=json.loads((REPO/'datasets'/member/'manifest.json').read_text(encoding='utf-8-sig'))
        manifests.update({r['path']:r for r in m['cases'] if r['split']=='train'})
    records=[]
    for number,source_path in enumerate(recipe['reused_training_paths']):
        source=REPO/source_path;src=manifests[source_path]
        data=source.read_bytes();raw_meta=source.with_suffix('.meta.json').read_bytes()
        assert sha(data)==src['sha256'] and sha(raw_meta)==src['metadata_sha256']
        original=json.loads(raw_meta.decode('utf-8-sig'));a=audit_case(source,original)
        member=Path(source_path).parts[1]
        family=src.get('family',original.get('family',original.get('scenario','random_source')))
        path=package/'train'/f'train_{number:03d}_{member}_{family}.txt'
        meta=dict(schema_version=2,case_id=path.stem,split='train',family=family,
            business_scenario='ordinary_random_source',is_edge=False,edge_reason=[],source_member=member,
            source_path=source_path,source_revision=SOURCE_REVISION,source_sha256=a['sha256'],
            source_metadata_sha256=sha(raw_meta),original_metadata=original,historical_development_exposure=True,
            seed=original.get('seed'),
            **{key:a[key] for key in ('k','p','memory','write','read','penalty','period','operations','per_operator_counts','build_bytes','sha256','operation_stream_sha256')})
        write_once(path,data);write_once(path.with_suffix('.meta.json'),encoded(meta))
        records.append(record_for(package,path,meta))
    print('Copied 120 ordinary source training workloads',flush=True)
    spec=importlib.util.spec_from_file_location('random_workloads',TOOLS/'random_workloads.py')
    generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
    for number,request in enumerate(recipe['generated_cases'],1):
        data,meta=generator.construct(request['spec'],request['seed'])
        meta.update(schema_version=2,case_id=Path(request['path']).stem,split=request['split'],
            source_member='new_synthetic',source_path=None,source_sha256=None,business_scenario=request['family'],
            spec=request['spec'],generator_source='final_dataset/tools/random_workloads.py',
            generator_sha256=recipe['generator_sha256'],prior_release_revision=PREVIOUS_RELEASE,
            no_solver_or_score_input=True,actual_production_trace=False,official_hidden_distribution_claim=False)
        assert meta['family']==request['family'] and meta['seed']==request['seed']
        path=package/request['path'];write_once(path,data);write_once(path.with_suffix('.meta.json'),encoded(meta))
        records.append(record_for(package,path,meta))
        if number%20==0 or number==430:print(f'Generated and audited random inputs: {number}/430',flush=True)
    write_once(package/'eval/VERSION',b'2.0.0\n')
    summary={}
    for split in ('train','eval'):
        rs=[r for r in records if r['split']==split];ns=[r['operations'] for r in rs]
        summary[split]=dict(cases=len(rs),regular=sum(not r['is_edge'] for r in rs),edge=sum(r['is_edge'] for r in rs),
            edge_fraction=sum(r['is_edge'] for r in rs)/len(rs),source_counts=dict(collections.Counter(r['source_member'] for r in rs)),
            families=dict(collections.Counter(r['family'] for r in rs)),operations_min=min(ns),operations_median=statistics.median(ns),
            operations_max=max(ns),at_least_32768=sum(n>=32768 for n in ns),at_least_65536=sum(n>=65536 for n in ns),
            at_least_262144=sum(n>=262144 for n in ns),total_operations=sum(ns),input_bytes=sum(r['file_bytes'] for r in rs),
            total_build_bytes=sum(r['build_bytes'] for r in rs))
    assert len(records)==550 and summary['train']['edge']==20 and summary['eval']['edge']==2
    manifest=dict(schema_version=2,name='final_dataset',version='2.0.0',source_revision=SOURCE_REVISION,
        previous_release_revision=PREVIOUS_RELEASE,recipe_sha256=sha(recipe_path.read_bytes()),summary=summary,cases=records,
        eval_exposure='New seeds/traces; no fitting, solver execution or score selection; public fixed tests after release.',
        official_hidden_distribution_claim=False)
    write_once(package/'manifest.json',encoded(manifest));print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
