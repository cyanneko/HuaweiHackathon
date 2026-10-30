"""Frozen R81 candidate on exposed original datasets, including same-run R75."""
from pathlib import Path
import copy
import experiment as ex

ROOT, core = ex.ROOT, ex.core
HERE = ROOT / 'tmp/r81_regression_eval'
core.HERE = HERE
read, save, sha, path = ex.read, ex.save, ex.sha, ex.path
CHOSEN = 'R81_op256_cond2048'
NAMES = ['Naive', 'R75_dense_switch', 'R79_adaptive', ex.PARENT, 'R80_paired_hier_fast100', CHOSEN]
SOURCES = {'dyna': 'tmp/r80_dyna_eval/final/selection.json', 'final': 'tmp/r80_lazy_eval/final/selection.json'}


def prepare(which):
    assert not (HERE / which / 'selection.json').exists()
    tr = read(ROOT / 'tmp/r81_eval/train/selection.json')
    advance = read(ROOT / 'tmp/r81_eval/train/advance.json')
    dev = read(ROOT / 'tmp/r81_eval/dev/selection.json')
    assert advance['selected'] == [CHOSEN]
    assert advance['training_summary_sha256'] == sha(ROOT / 'tmp/r81_eval/train/summary.json')
    assert tr['dependencies']['tmp/r81_eval/experiment.py'] == sha(ROOT / 'tmp/r81_eval/experiment.py')
    assert read(ROOT / 'tmp/r81_eval/dev/completion.json')['valid'] == 30
    assert read(ROOT / 'tmp/r81_eval/dev/cpu_released.json')['active_child_processes'] == 0
    review = read(ROOT / 'tmp/r81_review/dev_review.json')
    assert review['status'] == review['dev']['status'] == 'PASS'
    for file in ['selection', 'rows', 'summary']:
        assert review['dev'][file + '_sha256'] == sha(ROOT / ('tmp/r81_eval/dev/' + file + '.json'))
    assert review['training_advance_sha256'] == sha(ROOT / 'tmp/r81_eval/train/advance.json')
    ds = read(ROOT / 'tmp/r81_eval/dev/summary.json')
    assert ds['complete']
    dm = {m['method']: m for m in ds['groups']['all']}
    assert dm[CHOSEN]['average_score'] > dm[ex.PARENT]['average_score']
    trained = {m['name']: m for m in tr['methods']}
    ex.verify_dev_identity(tr, dev['methods'], sha(ROOT / 'tmp/r81_data_panel/data_manifest.json'), [CHOSEN])
    r75sel = read(ROOT / 'tmp/r79_final_eval/selection.json')
    r75 = next(m for m in r75sel['methods'] if m['name'] == 'R75_dense_switch')
    assert r75['source_sha256'] == 'cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
    all_methods = dict(trained, R75_dense_switch=r75)
    methods = [all_methods[n] for n in NAMES]
    for m in methods:
        ex.verify_method(m)
    old = read(ROOT / SOURCES[which])
    cases = copy.deepcopy(old['cases'])
    assert len(cases) == (6 if which == 'dyna' else 24)
    for c in cases:
        c['input_path'] = str(path(c['input_path']))
        c['metadata_path'] = str(path(c['metadata_path']))
        c['group'] = 'dyna6' if which == 'dyna' else 'final24'
        assert sha(path(c['input_path'])) == c['input_sha256']
        assert sha(path(c['metadata_path'])) == c['metadata_sha256']
        if which == 'dyna':
            assert c['stats']['operations'] == 5000000
    deps = dict(tr['dependencies'])
    for rel in [SOURCES[which], 'tmp/r81_eval/regression.py', 'tmp/r81_eval/train/selection.json',
                'tmp/r81_eval/train/advance.json', 'tmp/r81_eval/train/summary.json',
                'tmp/r81_eval/dev/selection.json', 'tmp/r81_eval/dev/summary.json', 'tmp/r81_eval/dev/completion.json',
                'tmp/r81_review/dev_review.json', 'tmp/r79_final_eval/selection.json',
                'docs/superpowers/plans/2026-10-30-r81-original-regression.md']:
        deps[rel] = sha(ROOT / rel)
    sel = dict(old, mode=which, scope='R81 unchanged TRAIN-selected candidate; exposed original ' + which + ' regression sample; same-run Naive/R75/R79/R80 controls',
               methods=methods, cases=cases, dependencies=deps, planned_cells=len(cases)*len(methods), repeats=1,
               active_controller_budget_seconds=360 if which == 'dyna' else 180,
               official_per_case_seconds=60, protocol='official-2026-10-26', score='case-mean-v1',
               percentiles='nearest-rank ceil(q*n)', gpu=False,
               combined_dataset_weight=.5, selected_method=CHOSEN, no_parameter_changes_after_train=True,
               default_promotion=False)
    save(HERE / which / 'selection.json', sel)
    print(core.json.dumps(dict(prepared=which, cases=len(cases), methods=len(methods), cells=sel['planned_cells'],
                               selection_sha256=sha(HERE / which / 'selection.json'))))


if __name__ == '__main__':
    parser = core.argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('mode', choices=['dyna', 'final'])
    parser.add_argument('--cpu-window-released', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.mode)
    else:
        assert args.cpu_window_released
        core.summarize = ex.summarize
        core.run(args.mode)
