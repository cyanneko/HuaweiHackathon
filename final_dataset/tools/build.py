"""Build a fixed 500/50 integration without consulting algorithms or scores."""
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
SOURCE_REVISION = '750618cead2d8f9d815a47fd8217fdab23d786dd'
sys.path.insert(0, str(REPO / 'evaluation/scripts'))
from audit_datasets import audit_case

EDGE_FAMILIES = {
    'over_by_one', 'almost_M', 'pair_fits', 'pair_exceeds', 'capacity_cliff',
    'corners', 'empty_partitions', 'cpu_tiny_io', 'mandatory_prefetch',
    'advance_build', 'micro_hot_giant_cold', 'memory_one_partition_boundary',
    'fully_resident_control', 'no_op_controls', 'next_bait_anticorrelation',
}
REGULAR_QUOTAS = {
    'anchor_new': 10, 'anchor_refined': 7, 'build_heavy': 15,
    'builder_vs_prober': 9, 'bursts': 15, 'capacity_cycle': 15,
    'grow_after_overlap': 9, 'hot_handoff': 9, 'hot_large': 12,
    'hot_plus_scan': 14, 'hot_small': 13, 'interleaved_phases': 14,
    'moving_hot': 16, 'near_uniform': 13, 'one_time_tail': 14,
    'operator_competition': 14, 'overlap_new': 8, 'sequential_scan': 13, 'zipf': 17,
}
EDGE_QUOTAS = {
    'corners': 5, 'almost_M': 5, 'pair_fits': 4, 'pair_exceeds': 5,
    'capacity_cliff': 5, 'empty_partitions': 4, 'cpu_tiny_io': 4,
    'mandatory_prefetch': 3, 'advance_build': 3, 'micro_hot_giant_cold': 4,
    'bandwidth_reversal': 7, 'operator_size_skew': 6,
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')

def signature(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        header = stream.readline().removeprefix(b'\xef\xbb\xbf').split()
        k, p = map(int, header[:2])
        h.update(f'{k} {p}\n'.encode())
        stream.readline()
        for _ in range(k):
            stream.readline()
        for line in stream:
            tokens = line.split()
            if tokens:
                if tokens[0] in (b'INSERT', b'PROBE'):
                    tokens[2] = str(int(tokens[2]) % p).encode()
                h.update(b' '.join(tokens) + b'\n')
    return h.hexdigest()

def edge_reasons(row):
    reasons = []
    if row['family'] in EDGE_FAMILIES:
        reasons.append('explicit boundary/adversarial construction: ' + row['family'])
    if 'r61root_07_resident_control_' in row['path']:
        reasons.append('explicit fully resident control')
    a = row['audit']
    if max(a['write'], a['read']) / min(a['write'], a['read']) >= 1000:
        reasons.append('read/write bandwidth ratio >= 1000')
    if a['pressure'] > 8:
        reasons.append('total build bytes / memory > 8')
    return reasons

def scenario(family, path, audit):
    if family in {'zipf', 'partition_zipf'}:
        return 'zipf_analytics'
    if family in {'sequential_scan', 'hot_plus_scan', 'scan', 'serial', 'hot_scan_pollution'}:
        return 'scan_hot_mix'
    if family in {'moving_hot', 'moving_hotspot', 'bursts', 'burst', 'shift', 'markov', 'hot_handoff', 'one_time_tail', 'hotset_phase_reverse'}:
        return 'moving_hotspot'
    if family in {'interleaved_phases', 'builder_vs_prober', 'overlap', 'overlap_new', 'grow_after_overlap', 'build_heavy'}:
        return 'build_probe_overlap' if audit['phase_overlap'] else 'heterogeneous_partitions'
    if family in {'operator_competition', 'operator_size_skew', 'cross_operator'}:
        return 'multi_operator_competition'
    if family in {'near_uniform', 'hot_small', 'hot_large', 'hot', 'uniform', 'hot_stream'}:
        return 'hotspot_queries'
    return 'heterogeneous_partitions'

def rank(row):
    return sha(('final-dataset-v1/' + row['path']).encode())

def choose(candidates, count, used):
    """Greedily cover parameters, deterministic hash tie-break; never use scores."""
    pool = sorted(candidates, key=rank)
    chosen, coverage = [], collections.Counter()
    def features(r):
        a = r['audit']
        return [('k', a['k']), ('p', a['p']), ('memory', a['memory']),
                ('pressure', int(a['pressure'] * 2)), ('period', a['period']),
                ('length', 0 if a['operations'] < 5000 else 1 if a['operations'] < 25000 else 2),
                ('read', a['read']), ('write', a['write'])]
    while len(chosen) < count:
        eligible = [r for r in pool if r['semantic'] not in used]
        if not eligible:
            raise RuntimeError(f'Insufficient independent inputs: need {count}, got {len(chosen)}')
        best = max(eligible, key=lambda r: (sum(1 / (1 + coverage[f]) for f in features(r)), rank(r)))
        chosen.append(best)
        used.add(best['semantic'])
        coverage.update(features(best))
        pool.remove(best)
    return chosen

def candidates():
    rows = []
    for member in ('cyanneko', 'liunianwww', 'Vanius0525'):
        manifest = json.loads((REPO / 'datasets' / member / 'manifest.json').read_text(encoding='utf-8-sig'))
        for item in manifest['cases']:
            if item['split'] != 'train':
                continue
            path = REPO / item['path']
            data = path.read_bytes()
            if sha(data) != item['sha256']:
                raise RuntimeError('Source input changed: ' + item['path'])
            original_meta = path.with_suffix('.meta.json').read_bytes()
            if sha(original_meta) != item['metadata_sha256']:
                raise RuntimeError('Source metadata changed: ' + item['path'])
            meta = json.loads(original_meta.decode('utf-8-sig'))
            family = item.get('family', meta.get('family', meta.get('scenario', meta.get('category', 'unspecified'))))
            row = dict(path=item['path'], member=member, family=family, meta=meta,
                       original_metadata_sha256=sha(original_meta),
                       audit=audit_case(path, meta), semantic=signature(path))
            row['edge_reason'] = edge_reasons(row)
            row['is_edge'] = bool(row['edge_reason'])
            rows.append(row)
        print('read source:', member, flush=True)
    return rows

def record_for(path, meta):
    a = audit_case(path, meta)
    return dict(path=path.relative_to(PACKAGE).as_posix(), split=meta['split'],
                source_member=meta.get('source_member', 'new_synthetic'),
                source_path=meta.get('source_path'), source_sha256=meta.get('source_sha256'),
                family=meta['family'], business_scenario=meta['business_scenario'],
                is_edge=meta['is_edge'], edge_reason=meta['edge_reason'],
                sha256=a['sha256'], metadata_sha256=sha(path.with_suffix('.meta.json').read_bytes()),
                operation_stream_sha256=a['operation_stream_sha256'],
                partition_stream_sha256=signature(path), operations=a['operations'],
                k=a['k'], p=a['p'], memory=a['memory'], pressure=a['pressure'],
                phase_overlap=a['phase_overlap'], file_bytes=a['file_bytes'])

def main():
    recipe_path = PACKAGE / 'recipe.json'
    if recipe_path.exists():
        recipe = json.loads(recipe_path.read_text(encoding='utf-8'))
    else:
        recipe = dict(schema_version=1, version='1.0.0', source_revision=SOURCE_REVISION,
            master_seed=secrets.token_hex(24), frozen_before_eval_generation=True,
            no_solver_or_scores=True, train_cases=500, eval_cases=50,
            train_regular=425, train_edge=75, eval_regular=42, eval_edge=8,
            train_source_counts={'cyanneko':48, 'liunianwww':292, 'Vanius0525':160},
            liunianwww_regular_family_quotas=REGULAR_QUOTAS,
            liunianwww_edge_family_quotas=EDGE_QUOTAS,
            edge_family_rules=sorted(EDGE_FAMILIES),
            numeric_edge_rules=['read/write bandwidth ratio >= 1000', 'total build bytes / memory > 8'],
            explicit_control_path_rule='r61root_07_resident_control_',
            selection='Source train only; family quotas; unique modulo-P streams; greedy parameter coverage; fixed hash tie-break.',
            business_assumption='Typical analytical database workloads; no production trace was supplied. Not a measured population distribution.',
            fresh_eval='Seven regular business scenarios, six each, and eight explicit edge diagnostics. Shared declared workload families; new seeds and traces.',
            generator_sha256=sha((PACKAGE/'tools/generate_eval.py').read_bytes()),
            builder_sha256=sha(Path(__file__).read_bytes()))
        dump(recipe_path, recipe)
    assert recipe['generator_sha256'] == sha((PACKAGE/'tools/generate_eval.py').read_bytes())
    assert recipe['builder_sha256'] == sha(Path(__file__).read_bytes())
    pool = candidates()
    used, selected = set(), []
    selected.extend(choose([r for r in pool if r['member']=='cyanneko'], 48, used))
    for family, count in REGULAR_QUOTAS.items():
        selected.extend(choose([r for r in pool if r['member']=='liunianwww' and r['family']==family and not r['is_edge']], count, used))
    for family, count in EDGE_QUOTAS.items():
        selected.extend(choose([r for r in pool if r['member']=='liunianwww' and r['family']==family and r['is_edge']], count, used))
    for family in ('uniform', 'hot', 'shift', 'scan', 'burst', 'markov', 'serial', 'overlap'):
        selected.extend(choose([r for r in pool if r['member']=='Vanius0525' and r['family']==family and not r['is_edge']], 20, used))
    assert len(selected)==500 and sum(r['is_edge'] for r in selected)==75
    (PACKAGE/'train').mkdir(exist_ok=True)
    (PACKAGE/'eval').mkdir(exist_ok=True)
    records=[]
    for number, row in enumerate(sorted(selected, key=lambda r:(r['member'],r['family'],rank(r)))):
        path=PACKAGE/'train'/f"train_{number:03d}_{row['member']}_{row['family']}.txt"
        data=(REPO/row['path']).read_bytes()
        if path.exists() and path.read_bytes()!=data:
            raise RuntimeError('Refuse to replace existing different input: '+path.name)
        path.write_bytes(data)
        a=row['audit']
        meta=dict(schema_version=1,case_id=path.stem,split='train',family=row['family'],
            business_scenario=scenario(row['family'],row['path'],a),is_edge=row['is_edge'],edge_reason=row['edge_reason'],
            source_member=row['member'],source_path=row['path'],source_revision=SOURCE_REVISION,
            source_sha256=a['sha256'],source_metadata_sha256=row['original_metadata_sha256'],
            original_metadata=row['meta'],historical_development_exposure=True,
            seed=row['meta'].get('seed'),partition_stream_sha256=row['semantic'],
            **{k:a[k] for k in ('k','p','memory','write','read','penalty','period','operations','per_operator_counts','build_bytes','sha256','operation_stream_sha256')})
        dump(path.with_suffix('.meta.json'),meta)
        records.append(record_for(path,meta))
    print('selected 500 training inputs',flush=True)
    spec=importlib.util.spec_from_file_location('final_eval_generator',PACKAGE/'tools/generate_eval.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build_eval(PACKAGE/'eval',recipe['master_seed'])
    for path in sorted((PACKAGE/'eval').glob('*.txt')):
        meta=json.loads(path.with_suffix('.meta.json').read_text(encoding='utf-8'))
        records.append(record_for(path,meta))
    assert len(records)==550
    assert sum(r['is_edge'] for r in records if r['split']=='eval')==8
    (PACKAGE/'eval/VERSION').write_text('1.0.0\n',encoding='ascii',newline='\n')
    summary={}
    for split in ('train','eval'):
        rs=[r for r in records if r['split']==split]
        summary[split]=dict(cases=len(rs),regular=sum(not r['is_edge'] for r in rs),edge=sum(r['is_edge'] for r in rs),
            edge_fraction=sum(r['is_edge'] for r in rs)/len(rs),
            source_counts=dict(collections.Counter(r['source_member'] for r in rs)),
            business_scenarios=dict(collections.Counter(r['business_scenario'] for r in rs)),
            total_operations=sum(r['operations'] for r in rs),input_bytes=sum(r['file_bytes'] for r in rs),
            max_case_operations=max(r['operations'] for r in rs),phase_overlap_cases=sum(r['phase_overlap'] for r in rs))
    manifest=dict(schema_version=1,name='final_dataset',version='1.0.0',source_revision=SOURCE_REVISION,
        recipe_sha256=sha(recipe_path.read_bytes()),summary=summary,cases=records,
        eval_exposure='Freshly synthesized for this release; no solver execution, fitting or score-based selection. Public after release, shared declared workload families.',
        official_hidden_distribution_claim=False,
        evaluate='python evaluation/evaluate.py --datasets-root . --members final_dataset --repeats 3 --out results/final.json --command SOLVER {input}',
        scoring_note='Run as an explicit standalone suite; do not add these selected training sources to member-weighted evaluation again.')
    dump(PACKAGE/'manifest.json',manifest)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
