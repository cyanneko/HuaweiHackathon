"""Reconstruct the fixed published bytes; do not download large input blobs.

Eval is never used for training, filtering, threshold choice or seed retries.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT/'build/round6'
DATA = STATE/'dataset/final_dataset'
COMMIT = '33ab5af221069fe8b8832fd77e85563e9997633a'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == data, f'Preserve differing artifact: {path}'
    else:
        path.write_bytes(data)


def manifest():
    return json.loads((STATE/'final_manifest.json').read_text())


def bootstrap():
    """Fetch only fixed small metadata/tools when reproducing from a clean tree."""
    STATE.mkdir(parents=True,exist_ok=True)
    exists=subprocess.run(['git','cat-file','-e',COMMIT+'^{commit}'],cwd=ROOT,
                          capture_output=True).returncode==0
    if not exists:
        subprocess.run(['git','fetch','--filter=blob:none','--no-tags','origin',COMMIT],cwd=ROOT,check=True)
    assets={STATE/'final_manifest.json':'manifest.json',
            STATE/'publisher_validation.json':'validation.json',
            STATE/'recipe.json':'recipe.json',
            DATA/'tools/random_workloads.py':'tools/random_workloads.py',
            DATA/'tools/verify.py':'tools/verify.py',
            DATA/'tools/build_v2.py':'tools/build_v2.py'}
    for target,relative in assets.items():
        if not target.exists():
            raw=subprocess.check_output(['git','show',COMMIT+':final_dataset/'+relative],cwd=ROOT)
            assert len(raw)<5*(1<<20), 'Unexpectedly large metadata/tool'
            put(target,raw)


def freeze():
    m = manifest()
    recipe = json.loads((STATE/'recipe.json').read_text())
    generator = DATA/'tools/random_workloads.py'
    assert hashlib.sha256(generator.read_bytes()).hexdigest() == recipe['generator_sha256']
    assert hashlib.sha256((STATE/'recipe.json').read_bytes()).hexdigest() == m['recipe_sha256']
    sources = {'pure_best': ROOT/'MySpillSchedulerBest.cpp',
               'ai_best': ROOT/'round4/ai_prefetch_budget2048.cpp'}
    source_lock = {}
    for name, path in sources.items():
        raw = path.read_bytes()
        put(STATE/'frozen_sources'/(name+'.cpp'), raw)
        source_lock[name] = {'source': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest()}
    # Reserve development only from new TRAIN flows, never from eval or reused
    # historical training. Quotas fixed before any solver results are opened.
    quotas = {'random_hotspot':28, 'random_zipf':28, 'random_uniform':24,
              'random_lognormal':16, 'one_byte_over':2, 'empty_partition_probe':2}
    rows = m['cases']
    dev = []
    for family, count in quotas.items():
        pool = [r for r in rows if r['split']=='train' and r['source_member']=='new_synthetic' and r['family']==family]
        pool.sort(key=lambda r: hashlib.sha256(('round6-dev-v1:'+r['partition_stream_sha256']).encode()).hexdigest())
        assert len(pool) >= count
        dev += [r['path'] for r in pool[:count]]
    train = [r['path'] for r in rows if r['split']=='train' and r['path'] not in dev]
    assert len(train)==400 and len(dev)==100
    # Small, fixed pilot training budget; full train remains available later.
    pilot = sorted(train, key=lambda p: hashlib.sha256(('round6-pilot-v1:'+p).encode()).hexdigest())[:80]
    lock = {'dataset_commit': COMMIT, 'dataset_version':'2.0.0',
            'manifest_sha256':hashlib.sha256((STATE/'final_manifest.json').read_bytes()).hexdigest(),
            'sources':source_lock, 'train':train, 'dev':dev, 'pilot_train':pilot,
            'test':[r['path'] for r in rows if r['split']=='eval'],
            'selection':'fixed 400 train/100 new-train dev; 80-flow pilot subset; no eval-driven choices',
            'baseline_repeats':3, 'main_metric':'all50 test mean per-case score, no member grouping',
            'secondary_metrics':['uncapped sum', 'capped Level1 sum', 'physical cost ratios', 'CPU', 'failures/tails'],
            'test_policy':'baseline once; one predeclared dev-selected challenger per route, then mark all read results exposed; no test fitting'}
    put(ROOT/'round6/DATASET_LOCK.json', (json.dumps(lock, indent=2)+'\n').encode())
    return lock


def materialize(split):
    rows = [r for r in manifest()['cases'] if r['split']==split]
    recipes = {r['path']:r for r in json.loads((STATE/'recipe.json').read_text())['generated_cases']}
    gen = load_module('round6_frozen_generator', DATA/'tools/random_workloads.py')
    for index, row in enumerate(rows):
        path = DATA/row['path']
        if path.exists():
            raw = path.read_bytes()
        elif row['path'] in recipes:
            request = recipes[row['path']]
            raw, _ = gen.construct(request['spec'], request['seed'])
        else:
            # Only the 120 explicitly reused old train files, 11.5MB in total.
            raw = subprocess.check_output(['git','show',manifest()['source_revision']+':'+row['source_path']], cwd=ROOT)
        assert len(raw)==row['file_bytes']
        assert hashlib.sha256(raw).hexdigest()==row['sha256'], row['path']
        put(path, raw)
        if index%10==0:
            print('materialized exact published bytes',split,index+1,len(rows),flush=True)
    if split=='eval':
        put(DATA/'eval/VERSION', b'2.0.0\n')


def audit_test():
    sys.path.insert(0,str(ROOT))
    from replay import parse_input
    verifier = load_module('round6_publisher_signature', DATA/'tools/verify.py')
    m = manifest()
    rows = m['cases']
    # Check all500 train vs50 eval signatures without silently claiming all
    # training files have already been independently reconstructed.
    collisions = {}
    for key in ['sha256','operation_stream_sha256','partition_stream_sha256']:
        train = {r[key] for r in rows if r['split']=='train'}
        collisions[key] = [r['path'] for r in rows if r['split']=='eval' and r[key] in train]
    assert not any(collisions.values())
    for row in rows:
        if row['split']!='eval':
            continue
        path=DATA/row['path']
        params, ops = parse_input(path)
        assert len(ops)==row['operations']
        signatures=verifier.signatures(path)
        assert all(signatures[k]==row[k] for k in signatures)
    # Check actual legacy fitted inputs, using the publisher's stronger
    # cost-header-independent modulo-P stream digest as well as raw hashes.
    old = sorted((ROOT/'build/data/train').glob('*.txt'))
    for family in ['fresh','ood']:
        old += sorted((ROOT/'build/round4/context_train'/family).glob('*.txt'))
    eval_sigs = {k:{r[k] for r in rows if r['split']=='eval'} for k in collisions}
    legacy_collisions = []
    for path in old:
        sig = verifier.signatures(path)
        if any(sig[k] in eval_sigs[k] for k in eval_sigs):
            legacy_collisions.append(path.name)
    assert not legacy_collisions
    report={'passed':True,'eval_cases_independently_validated':50,
            'published_manifest_train_cases_checked':500,'legacy_training_inputs_checked':len(old),
            'train_test_collisions':collisions,'legacy_training_test_collisions':legacy_collisions,
            'scope':'All eval raw bytes, logical signatures and input legality independently checked; all500 train signatures checked from fixed publisher manifest; legacy fitted288 actual files rehashed. Test file operations are not training features.'}
    put(ROOT/'round6/TEST_ISOLATION_AUDIT.json',(json.dumps(report,indent=2)+'\n').encode())
    return report


if __name__=='__main__':
    bootstrap()
    freeze()
    materialize('eval')
    print(json.dumps(audit_test()),flush=True)
