"""Freeze and generate additional large/skewed cases, without score-based selection."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
from pathlib import Path
import random
import secrets

from release_v21 import PACKAGE, VERSION, EVAL_COUNTS, TRAIN_COUNTS, encoded, load, sha, write_same
import random_workloads
from fast_allocation import allocate
from build_v2 import record_for

TOOLS = Path(__file__).resolve().parent


def seed_for(master,label):
    return int.from_bytes(hashlib.sha256(f'final-dataset-v21/{master}/{label}'.encode()).digest()[:8],'big')


def make_specs(master):
    requests = []
    for split,counts in (('train',TRAIN_COUNTS),('eval',EVAL_COUNTS)):
        rng = random.Random(seed_for(master,split+'/parameters'))
        ident = 500 if split=='train' else 50
        for family,count in counts.items():
            if split=='train':
                factor = 2 if count==108 else 1
                bands = [(65536,131071)]*(24*factor)+[(131072,262143)]*(24*factor)
                bands += [(262144,524287)]*(5*factor)+[(1048576,1048576)]*factor
            else:
                small,large,xlarge = (4,6,3) if count==14 else (2,3,2)
                bands = [(131072,262143)]*small+[(262144,524287)]*large
                bands += [(524288,786431)]*xlarge+[(1048576,1048576)]
            assert len(bands)==count
            rng.shuffle(bands)
            for index,(low,high) in enumerate(bands):
                n = rng.randint(low,high)
                level = index%3
                k,p = rng.choice([1,2,4,8]),rng.choice([8,16,32,64])
                memory = rng.choice([64,128,256,512,1024,2048,4096])*2**20
                # Long cases explicitly exercise the largest operator/partition state.
                if low==1048576:
                    k,p = 8,64
                pressure_low,pressure_high = [(1.15,1.7),(1.7,2.7),(2.7,4.0)][(index//3)%3]
                shape_ranges = [(0.8,1.05),(1.05,1.4),(1.4,1.8)] if family=='random_zipf' else [(0.5,0.85),(0.85,1.25),(1.25,1.8)]
                hot_ranges = [(0.60,0.72),(0.72,0.86),(0.86,0.95)]
                builds = int((n-k)*rng.uniform(.45,.65))
                spec = dict(family=family,k=k,p=p,memory=memory,write=rng.randint(100,10000),
                    read=rng.randint(100,10000),penalty=rng.randint(1,1000),
                    period=rng.choice([8,16,64,256,1024,4096,10000]),build_count=builds,
                    probe_count=n-k-builds,pressure=round(rng.uniform(pressure_low,pressure_high),6),
                    tuple_cv=round(rng.uniform(.3,1.2),6),shape_alpha=round(rng.uniform(*shape_ranges[level]),6),
                    hot_fraction=round(rng.uniform(.05,.25),6),hot_probability=round(rng.uniform(*hot_ranges[level]),6))
                requests.append(dict(path=f'{split}/{split}_{ident:03d}_{family}.txt',split=split,
                    family=family,seed=seed_for(master,f'{split}/{index}/{family}'),spec=spec))
                ident += 1
    assert len(requests)==306
    return requests


def metadata_for(request,meta,generator_hash):
    meta.update(schema_version=2,case_id=Path(request['path']).stem,split=request['split'],
        source_member='new_synthetic',source_path=None,source_sha256=None,
        business_scenario=request['family'],spec=request['spec'],
        generator_source='final_dataset/tools/random_workloads.py',generator_sha256=generator_hash,
        release_version=VERSION,expansion=True,no_solver_or_score_input=True,
        actual_production_trace=False,official_hidden_distribution_claim=False)
    return meta


def generate_one(args):
    package,request,generator_hash = args
    original = random_workloads._allocate
    try:
        random_workloads._allocate = allocate
        data,meta = random_workloads.construct(request['spec'],request['seed'])
    finally:
        random_workloads._allocate = original
    meta = metadata_for(request,meta,generator_hash)
    path = package/request['path']
    write_same(path,data)
    write_same(path.with_suffix('.meta.json'),encoded(meta))
    return record_for(package,path,meta)


def check_plan(plan):
    if plan['version']!=VERSION or plan['generated_cases']!=make_specs(plan['master_seed']):
        raise ValueError('Expansion specifications differ from frozen deterministic plan')
    if plan['generator_sha256']!=sha(TOOLS/'random_workloads.py') or plan['planner_sha256']!=sha(Path(__file__)):
        raise ValueError('Frozen generator/planner identity differs')
    if plan['allocation_backend_sha256']!=sha(TOOLS/'fast_allocation.py'):
        raise ValueError('Equivalent allocation implementation differs')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--freeze',action='store_true',help='write specs before generating any input')
    parser.add_argument('--generate',action='store_true')
    parser.add_argument('--jobs',type=int,default=1)
    args = parser.parse_args(argv)
    if args.freeze==args.generate or not 1<=args.jobs<=4:
        parser.error('choose --freeze or --generate; jobs must be 1..4')
    package = args.package.resolve()
    plan_path = package/'expansion.json'
    if args.freeze:
        if plan_path.exists():
            check_plan(load(plan_path))
        else:
            master = secrets.token_hex(24)
            plan = dict(schema_version=1,version=VERSION,master_seed=master,
                generator_sha256=sha(TOOLS/'random_workloads.py'),planner_sha256=sha(Path(__file__)),
                specifications_frozen_before_generation=True,no_solver_or_score_selection=True,
                allocation_backend_sha256=sha(TOOLS/'fast_allocation.py'),
                added_training_cases=270,added_eval_cases=36,
                policy='Fixed three-family quotas; independent split seeds; stratified operation count, pressure and skew; no retries or score filtering.',
                numerical_contract=dict(k=[1,8],p=[2,64],memory=[64*2**20,4096*2**20],
                    operations=[1,5000000],write=[1,10000],read=[1,10000],penalty=[1,1000],
                    period=[1,10000],key=[0,1000000000],tuple_bytes=[1,1048576],partition_bytes_max='M'),
                runtime_contract=dict(wall_seconds_per_case=60,
                    decision_complexity='O(K*P*log(K*P)) is an official recommendation, not an input bound',
                    note='Simulated IO cost is not sleep/wall time. Runtime depends on solver and machine; verify separately.'),
                generated_cases=make_specs(master))
            write_same(plan_path,encoded(plan))
        print('Frozen expansion: 270 train + 36 eval; no inputs generated',flush=True)
        return

    plan = load(plan_path)
    check_plan(plan)
    tasks = [(package,r,plan['generator_sha256']) for r in plan['generated_cases']]
    records = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for row in pool.map(generate_one,tasks):
            records.append(row)
            if len(records)%10==0 or len(records)==306:
                print(f'Generated and independently audited {len(records)}/306',flush=True)
    hashes = ('sha256','operation_stream_sha256','partition_stream_sha256')
    parent = load(package/'provenance/v2.0.0/manifest.json')
    for key in hashes:
        new = [r[key] for r in records]
        if len(set(new))!=len(new) or set(new)&{r[key] for r in parent['cases']}:
            raise ValueError('Duplicate new/parent signature: '+key)
    result = dict(schema_version=1,version=VERSION,expansion_sha256=sha(plan_path),
                  independently_audited_cases=len(records),cases=records)
    write_same(package/'expansion_manifest.json',encoded(result))
    print('Completed expansion; no solver or model run',flush=True)


if __name__=='__main__':
    main()
