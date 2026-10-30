"""Train-whitelisted metadata only. No input trace, solver, labels, or selection."""
import collections
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUND = HERE.parent
LOCK_SHA = '79e1f003fe808ea1380a7cd1bc679cb0ebccb75718fd0a485115e108472e0b08'
SIGS = ['seed', 'sha256', 'operation_stream_sha256', 'partition_stream_sha256']
FAMILIES = ['random_hotspot', 'random_zipf', 'random_lognormal']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    lock_bytes = (ROUND/'V21_DATASET_LOCK.json').read_bytes()
    assert digest(lock_bytes) == LOCK_SHA
    lock = json.loads(lock_bytes)
    train, pilot = set(lock['train']), set(lock['pilot_train'])
    assert len(train) == 432 and len(pilot) == 60 and pilot <= train
    # Do not inspect fields of rows outside the authorized training whitelist.
    identity = {r['path']: r for r in lock['cases'] if r['path'] in train}
    assert set(identity) == train
    folder = ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset'
    sources = {'V21_DATASET_LOCK.json': LOCK_SHA}
    containers = {}
    for name in ['manifest.json', 'recipe.json', 'selection.json']:
        raw = (folder/name).read_bytes()
        assert digest(raw) == lock['metadata'][name]['sha256']
        sources[name] = digest(raw)
        containers[name] = json.loads(raw)
    manifest = {r['path']: r for r in containers['manifest.json']['cases'] if r['path'] in train}
    recipe = {r['path']: r for r in containers['recipe.json']['generated_cases'] if r['path'] in train}
    added = set(containers['selection.json']['added_training_paths']) & train
    assert set(manifest) == set(recipe) == train
    del containers
    rows = {}
    for path in sorted(train):
        row, gen, ident = manifest[path], recipe[path], identity[path]
        assert row['family'] == gen['family'] == ident['family']
        assert gen['seed'] == ident['seed']
        for key in SIGS[1:]:
            assert row[key] == ident[key]
        assert not row['phase_overlap']
        assert row['operations'] == row['insert_count'] + row['probe_count'] + row['k']
        rows[path] = dict(path=path, seed=ident['seed'], family=row['family'],
                          signatures={k: ident[k] for k in SIGS},
                          operations=row['operations'], probes=row['probe_count'], inserts=row['insert_count'],
                          switches=row['k'], file_bytes=row['file_bytes'], added_v21=path in added,
                          suffix_upper=max(0, row['probe_count']-4096))
    parent = {p: p for p in train}
    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a
    repetitions = {}
    for key in SIGS:
        buckets = collections.defaultdict(list)
        for p in sorted(train):
            buckets[rows[p]['signatures'][key]].append(p)
        for group in buckets.values():
            for p in group[1:]:
                union(group[0], p)
        repetitions[key] = dict(unique=len(buckets), groups_with_multiple_cases=sum(len(g)>1 for g in buckets.values()),
                                cases_in_repeated_groups=sum(len(g) for g in buckets.values() if len(g)>1))
    components = collections.defaultdict(list)
    for p in sorted(train):
        components[find(p)].append(p)
    blocked_roots = {find(p) for p in pilot}
    excluded = {p for p in train if find(p) in blocked_roots}
    available = train-excluded
    # If grouping is non-singleton, simple top-eight-case arithmetic would not
    # equal an independent-group allocation; stop instead of overclaiming.
    assert all(len(g) == 1 for root, g in components.items() if root not in blocked_roots)

    def distribution(values):
        return dict(min=min(values), median=statistics.median(values), max=max(values), sum=sum(values))
    def summary(paths):
        data = [rows[p] for p in paths]
        return dict(cases=len(paths), unique_seeds=len({r['seed'] for r in data}),
                    fingerprint_components=len({find(p) for p in paths}),
                    operations=distribution([r['operations'] for r in data]),
                    probes=distribution([r['probes'] for r in data]),
                    file_bytes=distribution([r['file_bytes'] for r in data]),
                    operations_ge={str(t):sum(r['operations']>=t for r in data) for t in [65536,131072,262144,524288,1048576]},
                    probes_ge={str(t):sum(r['probes']>=t for r in data) for t in [4096,16384,65536,262144,524288]},
                    no_positive_suffix_by_simple_bound=sum(r['suffix_upper']==0 for r in data))
    def budget(paths):
        populations = {f:[rows[p] for p in paths if rows[p]['family']==f] for f in FAMILIES}
        assert all(len(v)>=8 for v in populations.values())
        expressions = {
            'selected_input_operations': lambda r:r['operations'],
            'four_branch_suffix_operations_upper': lambda r:4*r['suffix_upper'],
            'collector_plus_four_branch_operations_upper': lambda r:r['operations']+4*r['suffix_upper'],
            'selected_raw_input_bytes': lambda r:r['file_bytes'],
        }
        bounds = {}
        for name, expr in expressions.items():
            by_family = {}
            for f, data in populations.items():
                values = sorted(expr(r) for r in data)
                by_family[f] = dict(smallest_eight_sum=sum(values[:8]), largest_eight_sum=sum(values[-8:]))
            bounds[name] = dict(minimum_bound_across_balanced_choices=sum(v['smallest_eight_sum'] for v in by_family.values()),
                                maximum_bound_across_balanced_choices=sum(v['largest_eight_sum'] for v in by_family.values()),
                                by_family=by_family)
        return dict(quota_per_family=8, seeds=24, branches_per_seed=4, maximum_branches=96,
                    bounds=bounds, selected_case_paths=None,
                    caution='Min/max of conservative bounds, not observed executed work; expression extrema may use different cohorts.')
    populations = {}
    for name, paths in [('remaining_all_train', available), ('remaining_added_v21_train', available & added)]:
        populations[name] = dict(summary=summary(paths),
            families={f:summary({p for p in paths if rows[p]['family']==f}) for f in FAMILIES},
            balanced24_budget=budget(paths))
    result = dict(scope='Train metadata only; no selected cohort, trace reads, solver, teacher, model, or test score access.',
        source_sha256=sources, train_cases=432, pilot_cases=60,
        signature_repetitions_within_train=repetitions,
        fingerprint_component_sizes=dict(collections.Counter(map(len,components.values()))),
        excluded_by_pilot_component=len(excluded), additional_relatives_beyond_pilot=len(excluded-pilot),
        added_train_before_pilot_exclusion=len(added), pilot_in_added=len(pilot & added),
        populations=populations,
        assumptions=['q0 is unknown legal callback state; only q0>=4096 is used.',
                     'All authorized metadata rows have INSERT+PROBE+K=N and no phase overlap.',
                     'No future N, residual length, family, seed, period or hidden penalty is a model feature.',
                     'Distinct seeds/fingerprints do not prove statistical independence or zero historical exposure.',
                     'Original 60 pure-configuration complementarity remains unverified by this metadata audit.'],
        access_note='Initial schema inspection printed one eval metadata identity row from the joint lock; no eval input, operation sequence or score was read or used.',
        raw_input_reads=0, solver_runs=0, teacher_branches=0, training_runs=0, selected_seed_count=0)
    out = HERE/'CONFIGURATION_POPULATION_BUDGET_V1.json'
    content = json.dumps(result, indent=2)+'\n'
    if out.exists():
        assert out.read_text() == content
    else:
        out.write_text(content)
    print(json.dumps({'excluded':len(excluded), 'extra_relatives':len(excluded-pilot), 'populations':populations}, indent=2))


if __name__ == '__main__':
    main()
