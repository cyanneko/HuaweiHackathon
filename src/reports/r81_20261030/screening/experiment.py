"""R81 score-based screening; frozen R80 process runner and parser are reused."""
from pathlib import Path
import copy
import importlib.util
import statistics

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('r81_frozen_execution_core', ROOT / 'tmp/r80_eval/experiment.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
HERE = Path(__file__).resolve().parent
core.HERE = HERE
read, save, sha, path = core.read, core.save, core.sha, core.path
PARENT = 'R80_next_hier_fast100'
NEW = ['R81_op256_cond2048', 'R81_op512_cond2048']
PARENT_SHA = '0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d'
BASE_SUMMARIZE = core.summarize


def summarize(selection, rows):
    # The execution phase remains TRAIN/DEV. Only use the frozen scoring branch
    # that normalizes against a same-run Naive, without pretending TRAIN is test.
    scored = dict(selection, mode='final')
    result = BASE_SUMMARIZE(scored, rows)
    result['phase'] = selection['mode']
    if not result['complete']:
        return result
    extra = {g: [c for c in selection['cases'] if c['group'] == g]
             for g in ['old26', 'new_train', 'dev6']}
    for p in [1, 100, 1000]:
        extra['penalty' + str(p)] = [c for c in selection['cases'] if c['stats']['penalty'] == p]
    for group, cases in extra.items():
        if cases:
            ids = {c['case_id'] for c in cases}
            subset = BASE_SUMMARIZE(dict(scored, cases=cases), [r for r in rows if r['case_id'] in ids])
            assert subset['complete']
            result['groups'][group] = subset['groups']['all']
    index = {(r['case_id'], r['method']): r['metrics'] for r in rows}
    per = {(r['case_id'], r['method']): r for r in result['per_case']}
    for group, entries in result['groups'].items():
        if group == 'all':
            cases = selection['cases']
        elif group in extra:
            cases = extra[group]
        else:
            cases = [c for c in selection['cases'] if c['family'] == group]
        assert cases
        for m in entries:
            name = m['method']
            ratios, physical, delta, raw = [], [], [], []
            for c in cases:
                cid = c['case_id']
                a, b, naive = [index[cid, n] for n in [name, PARENT, 'Naive']]
                ratios.append(a['Total_Score']/b['Total_Score'] if b['Total_Score'] > 0 else None)
                pa, pb = [v['Total_IO_Time'] + c['stats']['penalty']*v['Miss_Count'] for v in [a, b]]
                physical.append(pa/pb if pb > 0 else None)
                delta.append(per[cid, name]['score'] - per[cid, PARENT]['score'])
                raw.append(1-a['Total_Score']/naive['Total_Score'] if naive['Total_Score'] > 0 else None)
            m['cost_to_parent'] = core.ratios(ratios)
            m['physical_to_parent'] = core.ratios(physical)
            m['mean_score_delta_parent'] = statistics.mean(delta)
            m['mean_unclipped_cost_reduction'] = statistics.mean([x for x in raw if x is not None]) if any(x is not None for x in raw) else None
            m['defined_naive_denominators'] = sum(x is not None for x in raw)
    for r in result['per_case']:
        b = per[r['case_id'], PARENT]
        n = index[r['case_id'], 'Naive']['Total_Score']
        r['ratio_to_parent'] = r['cost']/b['cost'] if b['cost'] > 0 else None
        r['score_delta_parent'] = r['score'] - b['score']
        r['unclipped_cost_reduction'] = 1-r['cost']/n if n > 0 else None
    return result


def choose(summary):
    assert summary['complete']
    groups = {g: {m['method']: m for m in entries} for g, entries in summary['groups'].items()}
    choices = []
    for name in NEW:
        required = all(g in groups and name in groups[g] for g in ['all', 'old26', 'new_train'])
        guards = dict(required_groups_present=required)
        if required:
            whole, old, new = [groups[g][name] for g in ['all', 'old26', 'new_train']]
            defined = all(m['cost_to_parent']['n'] == m['cases'] == m['defined_naive_denominators'] for m in [whole, old, new])
            guards['all_parent_and_naive_denominators_defined'] = defined
            if defined:
                guards.update(new_train_score_improves=new['mean_score_delta_parent'] > 0,
                              old26_score_loss_le_0_05=old['mean_score_delta_parent'] >= -.05,
                              worst_train_cost_parent_le_1_25=whole['cost_to_parent']['worst'] <= 1.25)
            choices.append(dict(method=name, eligible=all(guards.values()), guards=guards,
                                new_train_mean_score=new['average_score'], new_train_score_delta=new['mean_score_delta_parent'],
                                old26_score_delta=old['mean_score_delta_parent'], worst_cost_parent=whole['cost_to_parent']['worst'],
                                D_total_us=whole['D_total_us'], D_hard_veto=False))
        else:
            choices.append(dict(method=name, eligible=False, guards=guards))
    eligible = sorted([c for c in choices if c['eligible']], key=lambda c: (-c['new_train_mean_score'], c['D_total_us'], c['method']))
    return dict(complete=True, selected=[c['method'] for c in eligible[:1]], choices=choices,
                rule='Highest same-run Naive new-TRAIN mean score; strictly improve parent, old26 loss<=.05 points, all-TRAIN worst cost/parent<=1.25, complete defined denominators; ties lower D then name; no hard D veto',
                reserved_dev_results_consulted=False)


def advance(summary, out):
    decision = choose(summary)
    decision['training_summary_sha256'] = sha(out / 'summary.json')
    save(out / 'advance.json', decision)


def verify_method(m):
    assert m['compile_flags'] == ['-std=c++14', '-O2'] and not m['instrumented']
    for f, k in [('source_path', 'source_sha256'), ('translation_unit_path', 'translation_unit_sha256'), ('binary', 'binary_sha256')]:
        assert sha(path(m[f])) == m[k], m['name'] + '/' + f
    source = path(m['source_path']).read_text(encoding='utf-8-sig')
    tu = path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(source) == 1
    skeleton = core.hashlib.sha256(tu.replace(source, '<SCHEDULER>').encode()).hexdigest()
    assert skeleton == read(core.OLD / 'config.json')['framework_skeleton_sha256']


def verify_dev_identity(training_selection, methods, data_digest, selected):
    assert len(selected) == 1 and selected[0] in NEW
    trained = {m['name']: m for m in training_selection['methods']}
    for m in methods:
        assert m == trained[m['name']], 'DEV method changed after TRAIN: ' + m['name']
    assert data_digest == training_selection['dependencies']['tmp/r81_data_panel/data_manifest.json'], 'DEV data contract changed after TRAIN'


def prepare(mode):
    assert mode in ['train', 'dev']
    assert not (HERE / mode / 'selection.json').exists(), 'no re-preparation of frozen selections'
    baseline_file = ROOT / 'tmp/r80_lazy_eval/final/selection.json'
    baseline = read(baseline_file)
    prodfile = ROOT / 'tmp/r81_two_timescale/producer.json'
    prod = read(prodfile)
    release = read(prodfile.parent / 'release.json')
    assert prod['status'] == 'READY' and prod['framework_unchanged']
    assert release['final'] and release['ready'] and release['active_child_processes'] == 0
    assert release['producer_sha256'] == sha(prodfile)
    assert read(prodfile.parent / 'test_summary.json')['status'] == 'PASS'
    assert [m['name'] for m in prod['variants']] == NEW
    methods_by_name = {m['name']: m for m in baseline['methods'] + prod['variants']}
    assert methods_by_name[PARENT]['source_sha256'] == PARENT_SHA
    datafile = ROOT / 'tmp/r81_data_panel/data_manifest.json'
    data = read(datafile)
    assert read(datafile.parent / 'cpu_released.json')['active_child_processes'] == 0
    oldfile = ROOT / 'tmp/r80_eval/train/selection.json'
    old = read(oldfile)
    assert data['config_sha256'] == sha(datafile.parent / 'config.json')
    refs = read(datafile.parent / 'old26_references.json')
    assert refs['source_selection_sha256'] == sha(oldfile)
    originals = {c['case_id']: c for c in old['cases']}
    old_refs = [c for c in data['cases'] if c['group'] == 'old26']
    assert len(old_refs) == len(originals) == 26
    for c in old_refs:
        assert c['input_sha256'] == originals[c['case_id']]['input_sha256']
        assert c['metadata_sha256'] == originals[c['case_id']]['metadata_sha256']
    newcases = [c for c in data['cases'] if c['group'] != 'old26']
    assert all(c['status'] == 'FULL_INPUT_AUDIT_PASS' and all(c['validation'].values()) for c in newcases)
    assert len([c for c in newcases if c['split'] == 'train']) == data['new_train']
    assert len([c for c in newcases if c['split'] == 'dev']) == data['reserved_dev']
    deps = dict(baseline['dependencies'])
    for rel in ['tmp/r80_eval/experiment.py', 'tmp/r81_eval/experiment.py', 'tmp/r81_eval/test_protocol.py',
                'docs/superpowers/plans/2026-10-30-r81-two-timescale-heat.md',
                'tmp/r81_two_timescale/producer.json', 'tmp/r81_two_timescale/release.json', 'tmp/r81_two_timescale/test_summary.json',
                'tmp/r81_data_panel/data_manifest.json', 'tmp/r81_data_panel/config.json', 'tmp/r81_data_panel/review.json',
                'tmp/r81_data_panel/old26_references.json', 'tmp/r81_data_panel/selection.json', 'tmp/r81_data_panel/prepare_data.py',
                'tmp/r81_data_panel/cpu_released.json', 'tmp/r80_eval/train/selection.json', 'tmp/r80_lazy_eval/final/selection.json']:
        deps[rel] = sha(ROOT / rel)
    if mode == 'train':
        assert len(old['cases']) == 26
        cases = [dict(copy.deepcopy(c), group='old26') for c in old['cases']]
        cases += [dict(copy.deepcopy(c), group='new_train') for c in newcases if c['split'] == 'train']
        names = ['Naive', 'R79_adaptive', PARENT, 'R80_paired_hier_fast100'] + NEW
        scope = 'R81 TRAIN screening only: old26 plus predeclared valid fresh TRAIN; same-run Naive score; no DEV outcome access'
    else:
        decision = read(HERE / 'train/advance.json')
        assert decision['complete'] and len(decision['selected']) == 1
        assert decision['training_summary_sha256'] == sha(HERE / 'train/summary.json')
        training_selection = read(HERE / 'train/selection.json')
        assert read(HERE / 'train/campaign.json')['selection_sha256'] == sha(HERE / 'train/selection.json')
        assert read(HERE / 'train/completion.json')['valid'] == training_selection['planned_cells']
        expected = choose(read(HERE / 'train/summary.json'))
        assert all(decision[k] == v for k, v in expected.items())
        cases = [dict(copy.deepcopy(c), group='dev6') for c in newcases if c['split'] == 'dev']
        assert cases
        names = ['Naive', 'R79_adaptive', PARENT, 'R80_paired_hier_fast100'] + decision['selected']
        for rel in ['tmp/r81_eval/train/advance.json', 'tmp/r81_eval/train/summary.json', 'tmp/r81_eval/train/selection.json']:
            deps[rel] = sha(ROOT / rel)
        scope = 'R81 fresh reserved DEV only after TRAIN candidate identity freeze; a small development sample, not hidden official test'
    assert len({c['case_id'] for c in cases}) == len(cases)
    assert len({c['input_sha256'] for c in cases}) == len(cases)
    train_cases = [c for c in newcases if c['split'] == 'train']
    dev_cases = [c for c in newcases if c['split'] == 'dev']
    assert not ({c['lineage_id'] for c in train_cases} & {c['lineage_id'] for c in dev_cases})
    assert not ({c['input_sha256'] for c in train_cases} & {c['input_sha256'] for c in dev_cases})
    for c in cases:
        c['input_path'] = str(path(c.get('input_path_linux', c.get('input_path'))))
        c['metadata_path'] = str(path(c['metadata_path']))
        assert sha(path(c['input_path'])) == c['input_sha256']
        assert sha(path(c['metadata_path'])) == c['metadata_sha256']
        assert c['stats']['operations'] == (100000 if c['group'] == 'old26' else 150000)
    cases.sort(key=lambda c: core.hashlib.sha256(('r81-' + mode + '-order-v1' + c['case_id']).encode()).hexdigest())
    methods = [methods_by_name[n] for n in names]
    if mode == 'dev':
        verify_dev_identity(training_selection, methods, sha(datafile), decision['selected'])
    for m in methods:
        verify_method(m)
    selection = dict(mode=mode, scope=scope, cases=cases, methods=methods, dependencies=deps,
                     planned_cells=len(cases)*len(methods), repeats=1, active_controller_budget_seconds=240 if mode == 'train' else 120,
                     official_per_case_seconds=60, order='fixed hash order of cases; rotate methods by case index',
                     protocol='official-2026-10-26', percentiles='nearest-rank ceil(q*n)', score='case-mean-v1', gpu=False,
                     D_policy='D included in final cost and score, ratio reported without hard veto',
                     training_count=len(train_cases), reserved_dev_count=len(dev_cases),
                     data_manifest_status=data.get('status'), parent_source_sha256=PARENT_SHA,
                     original_runner_sha256=sha(ROOT / 'tmp/r80_eval/experiment.py'))
    save(HERE / mode / 'selection.json', selection)
    print(core.json.dumps(dict(prepared=mode, cases=len(cases), methods=len(methods), cells=selection['planned_cells'],
                               selection_sha256=sha(HERE / mode / 'selection.json'))))


if __name__ == '__main__':
    p = core.argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'run'])
    p.add_argument('mode', choices=['train', 'dev'])
    p.add_argument('--cpu-window-released', action='store_true')
    args = p.parse_args()
    if args.action == 'prepare':
        prepare(args.mode)
    else:
        assert args.cpu_window_released
        core.summarize, core.advance = summarize, advance
        core.run(args.mode)
