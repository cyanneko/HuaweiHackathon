"""Two independently controlled victim-search variants; inherited R81 score rule."""
from pathlib import Path
import copy
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('r82_frozen_score_protocol', ROOT/'tmp/r81_eval/experiment.py')
inherited = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inherited)
core = inherited.core
HERE = Path(__file__).resolve().parent
core.HERE = HERE
PARENT = inherited.PARENT
NEW = ['R82_singlefit025', 'R82_write1']
inherited.NEW = NEW
read, save, sha, path = inherited.read, inherited.save, inherited.sha, inherited.path
choose = inherited.choose
NAMES = ['Naive', 'R79_adaptive', PARENT, 'R80_paired_hier_fast100'] + NEW


def summarize(selection, rows):
    result = inherited.summarize(selection, rows)
    if result['complete'] and selection['mode'] == 'dev':
        result['groups']['dev12'] = copy.deepcopy(result['groups']['all'])
    return result


def verify_case_uniqueness(cases):
    assert len({c['case_id'] for c in cases}) == len(cases), 'duplicate case ID'
    assert len({c['input_sha256'] for c in cases}) == len(cases), 'duplicate input content'


def advance(summary, out):
    result = choose(summary)
    result['training_summary_sha256'] = sha(out/'summary.json')
    save(out/'advance.json', result)


def verify_dev_identity(training_selection, methods, data_digest, selected):
    assert len(selected) == 1 and selected[0] in NEW
    trained = {m['name']: m for m in training_selection['methods']}
    for m in methods:
        assert m == trained[m['name']], 'DEV method changed after TRAIN: ' + m['name']
    assert data_digest == training_selection['dependencies']['tmp/r82_dev_panel/data_manifest.json'], 'DEV data contract changed after TRAIN'


def prepare(mode):
    assert mode in ['train', 'dev'] and not (HERE/mode/'selection.json').exists()
    oldfile = ROOT/'tmp/r81_eval/train/selection.json'
    old = read(oldfile)
    for rel in ['tmp/r81_eval/experiment.py', 'tmp/r80_eval/experiment.py']:
        assert sha(ROOT/rel) == old['dependencies'][rel]
    prodfile = ROOT/'tmp/r82_victim_search/producer.json'
    prod = read(prodfile)
    rel = read(prodfile.parent/'release.json')
    assert prod['status'] == 'READY' and prod['framework_unchanged']
    assert rel['final'] and rel['ready'] and rel['active_child_processes'] == 0
    assert rel['producer_sha256'] == sha(prodfile)
    assert read(prodfile.parent/'test_summary.json')['status'] == 'PASS'
    assert prod['parent_sha256'] == inherited.PARENT_SHA
    assert [m['name'] for m in prod['variants']] == NEW
    method_map = {m['name']: m for m in old['methods'] + prod['variants']}
    datafile = ROOT/'tmp/r82_dev_panel/data_manifest.json'
    data = read(datafile)
    assert read(datafile.parent/'cpu_released.json')['active_child_processes'] == 0
    assert data['config_sha256'] == sha(datafile.parent/'config.json')
    assert all(c['split'] == 'dev' and c['status'] == 'FULL_INPUT_AUDIT_PASS' and all(c['validation'].values()) for c in data['cases'])
    assert not ({c['input_sha256'] for c in old['cases']} & {c['input_sha256'] for c in data['cases']})
    assert not ({c['lineage_id'] for c in old['cases']} & {c['lineage_id'] for c in data['cases']})
    deps = dict(old['dependencies'])
    for rel in ['tmp/r81_eval/train/selection.json', 'tmp/r82_eval/experiment.py', 'tmp/r82_eval/test_protocol.py',
                'tmp/r82_victim_search/producer.json', 'tmp/r82_victim_search/release.json', 'tmp/r82_victim_search/test_summary.json',
                'tmp/r82_dev_panel/data_manifest.json', 'tmp/r82_dev_panel/config.json', 'tmp/r82_dev_panel/selection.json',
                'tmp/r82_dev_panel/prepare_data.py', 'tmp/r82_dev_panel/review.json', 'tmp/r82_dev_panel/cpu_released.json',
                'docs/superpowers/plans/2026-10-30-r82-victim-search-ablation.md']:
        deps[rel] = sha(ROOT/rel)
    frozen_data_key = 'tmp/r82_dev_panel/data_manifest.json'
    if mode == 'train':
        cases = copy.deepcopy(old['cases'])
        names = NAMES
        assert len(cases) == 38
        assert sum(c['group'] == 'old26' for c in cases) == 26
        assert sum(c['group'] == 'new_train' for c in cases) == 12
    else:
        decision = read(HERE/'train/advance.json')
        tr = read(HERE/'train/selection.json')
        assert decision['complete'] and len(decision['selected']) == 1 and decision['selected'][0] in NEW
        assert decision['training_summary_sha256'] == sha(HERE/'train/summary.json')
        expected = choose(read(HERE/'train/summary.json'))
        assert all(decision[k] == v for k,v in expected.items())
        assert read(HERE/'train/completion.json')['valid'] == tr['planned_cells']
        assert read(HERE/'train/campaign.json')['selection_sha256'] == sha(HERE/'train/selection.json')
        assert sha(datafile) == tr['dependencies'][frozen_data_key]
        cases = [dict(copy.deepcopy(c), group='dev12') for c in data['cases']]
        assert cases
        names = NAMES[:4] + decision['selected']
        for rel in ['tmp/r82_eval/train/advance.json', 'tmp/r82_eval/train/summary.json', 'tmp/r82_eval/train/selection.json']:
            deps[rel] = sha(ROOT/rel)
    methods = [method_map[n] for n in names]
    verify_case_uniqueness(cases)
    if mode == 'dev':
        verify_dev_identity(tr, methods, sha(datafile), decision['selected'])
    for m in methods:
        inherited.verify_method(m)
    for c in cases:
        c['input_path'] = str(path(c.get('input_path_linux', c.get('input_path'))))
        c['metadata_path'] = str(path(c['metadata_path']))
        assert sha(path(c['input_path'])) == c['input_sha256']
        assert sha(path(c['metadata_path'])) == c['metadata_sha256']
        assert c['stats']['operations'] == (100000 if c['group'] == 'old26' else 150000)
    if mode == 'dev':
        cases.sort(key=lambda c: core.hashlib.sha256(('r82-dev-order-v1'+c['case_id']).encode()).hexdigest())
    selection = dict(old, mode=mode, methods=methods, cases=cases, dependencies=deps,
                     scope='R82 reused TRAIN38 score screening' if mode == 'train' else 'R82 independently seeded reserved DEV, six paired lineages, selected method frozen after TRAIN',
                     planned_cells=len(cases)*len(methods), active_controller_budget_seconds=240 if mode == 'train' else 120,
                     score='case-mean-v1', repeats=1, official_per_case_seconds=60,
                     training_count=38, reserved_dev_count=len(data['cases']), data_manifest_status=data['status'],
                     original_runner_sha256=sha(ROOT/'tmp/r80_eval/experiment.py'),
                     borrowed_scoring_sha256=sha(ROOT/'tmp/r81_eval/experiment.py'), no_R81_heat_change=True)
    save(HERE/mode/'selection.json', selection)
    print(core.json.dumps(dict(prepared=mode, cases=len(cases), methods=len(methods), cells=selection['planned_cells'], selection_sha256=sha(HERE/mode/'selection.json'))))


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
