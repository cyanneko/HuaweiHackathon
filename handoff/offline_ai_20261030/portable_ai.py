"""Saved-feature AI loader. No solver, raw-input replay, or automatic training."""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import struct
import sys

BASE = Path(__file__).resolve().parent
WS = BASE / 'workspace'
AI = WS / 'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030'
R70 = WS / 'tmp/r70_nn_pipeline'
REQUIRED_INPUTS = BASE / 'AI_REQUIRED_INPUTS.json'
SAVED_LABELS = BASE / 'saved_label_manifest.json'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def source_module():
    spec = importlib.util.spec_from_file_location('published_plan_ranker', AI / 'model.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def model_paths():
    fixed = ['small_full', 'large_full', 'large_no_score_inputs', 'large_no_score_or_skip']
    student = ['A_old', 'B_student_fixed', 'C_student_portfolio']
    return [R70 / 'model_v2/model.json'] + [AI / ('gpu_fixed_v1/' + n + '/model.json') for n in fixed] + [AI / ('gpu_student_v1/' + n + '/model.json') for n in student]

def checked_jsonl(relative_path, expected_sha):
    path = (WS / relative_path).resolve()
    assert path.is_relative_to(WS.resolve()), 'Label path escapes mirrored workspace'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha, 'Label SHA mismatch: ' + relative_path
    return [json.loads(line) for line in raw.decode('utf8').splitlines() if line.strip()]

def old_label_refs():
    refs = read(REQUIRED_INPUTS)['existing_label_blobs']
    assert len(refs) == 28 and len({r['path_to_restore'] for r in refs}) == 28
    assert all(r['source_git_ref'] == '5726b9dd1bfd1c21dcbe9eff1f8b09a78c67550c' for r in refs)
    return refs

def load_model(path):
    import torch
    ranker = source_module().PlanRanker
    data = read(path)
    tiny = 'w1' in data
    model = ranker([16] if tiny else data['hidden'], [] if tiny else data['zero_columns'], True if tiny else data['base_skip'])
    layers = [{'weight': data['w1'], 'bias': data['b1']}, {'weight': [data['w2']], 'bias': [data['b2']]}] if tiny else data['layers']
    with torch.no_grad():
        for target, saved in zip(model.layers, layers):
            target.weight.copy_(torch.tensor(saved['weight'], dtype=torch.float32))
            target.bias.copy_(torch.tensor(saved['bias'], dtype=torch.float32))
    return model.eval(), data

def rows_for(name):
    rows = []
    refs = [r for r in old_label_refs() if Path(r['path_to_restore']).name.startswith('train_')]
    assert len(refs) == 24
    for ref in refs:
        relative = ref['path_to_restore']
        assert Path(relative).parent.as_posix() == 'tmp/r70_nn_pipeline/labels_v3'
        case = Path(relative).stem
        try:
            saved = checked_jsonl(relative, ref['sha256'])
        except FileNotFoundError as exc:
            raise FileNotFoundError('Restore existing labels from AI_REQUIRED_INPUTS.json; do not regenerate them.') from exc
        assert saved and all(row['case_id'] == case and row['split'] == 'train' for row in saved)
        rows += saved
    original_cases = {r['case_id'] for r in rows}
    assert len(original_cases) == 24 and len(rows) == 370
    if name != 'old':
        assert name in ['student-fixed', 'student-portfolio']
        entries = [r for r in read(SAVED_LABELS)['labels'] if r['id'] == name]
        assert len(entries) == 1 and entries[0]['train_eligible'] is True
        saved = checked_jsonl(entries[0]['workspace_path'], entries[0]['public_sha256'])
        assert len(saved) == 46 and all(r['split'] == 'train' and r['case_id'] in original_cases for r in saved)
        rows += saved
    assert all(row['split'] == 'train' and row['feature_version'] == 'r70-causal32-v2-sequential-sums' for row in rows)
    assert len({(r['case_id'], r['anchor_snapshot_sha256']) for r in rows}) == len(rows)
    return rows

def tensors(rows, device):
    import torch
    counts = Counter(r['case_id'] for r in rows if r['integer_gap_scale'] > 0)
    x = torch.zeros((len(rows), 8, 32), dtype=torch.float32, device=device)
    y = torch.zeros((len(rows), 8), dtype=torch.float32, device=device)
    valid = torch.zeros((len(rows), 8), dtype=torch.bool, device=device)
    weights = torch.zeros(len(rows), dtype=torch.float32, device=device)
    for i, row in enumerate(rows):
        if row['integer_gap_scale'] > 0:
            weights[i] = 1 / (len(counts) * counts[row['case_id']])
        assert 1 <= len(row['plans']) <= 8
        for j, plan in enumerate(row['plans']):
            assert len(plan['x']) == 32 and plan['valid_cost'] and plan['cost']['status'] == 'complete'
            x[i, j] = torch.tensor(plan['x'], device=device)
            y[i, j] = plan['target']
            valid[i, j] = True
    return x, y, valid, weights

def tiny_sequential(data, x):
    f32 = lambda z: struct.unpack('<f', struct.pack('<f', float(z)))[0]
    x = [f32(v) for v in x]
    z = f32(data['b2'])
    for j in range(16):
        h = f32(data['b1'][j])
        for i in range(32):
            h = f32(h + f32(data['w1'][j][i] * x[i]))
        z = f32(z + f32(data['w2'][j] * max(0., h)))
    return f32(x[13] + min(1., max(-1., z)))

def verify():
    import torch
    torch.set_num_threads(1)
    checks = []
    vectors = read(R70 / 'model_v2/score_vectors.json')
    sample = [v['x'] for v in vectors[:8]]
    paths = model_paths()
    assert len(paths) == 8 and len(set(paths)) == 8 and all(p.is_file() for p in paths)
    assert sum(p.with_name('weights.pt').is_file() for p in paths) == 7
    for path in paths:
        model, data = load_model(path)
        pt = path.with_name('weights.pt')
        if pt.exists():
            state = torch.load(pt, map_location='cpu', weights_only=True)
            assert model.state_dict().keys() == state.keys()
            assert all(torch.equal(model.state_dict()[k], v) for k, v in state.items())
        with torch.inference_mode():
            scores = model(torch.tensor(sample, dtype=torch.float32))
        assert torch.isfinite(scores).all()
        checks.append({'model': path.relative_to(WS).as_posix(), 'json_pt_bitwise_equal': True if pt.exists() else None,
                       'cpu_inference_vectors': len(sample), 'finite_scores': True})
    tiny = read(R70 / 'model_v2/model.json')
    error = max(abs(tiny_sequential(tiny, v['x']) - v['score']) for v in vectors)
    assert error == 0
    refs = old_label_refs()
    restored = all((WS / r['path_to_restore']).is_file() for r in refs)
    if restored:
        for ref in refs:
            saved = checked_jsonl(ref['path_to_restore'], ref['sha256'])
            case = Path(ref['path_to_restore']).stem
            split = 'train' if case.startswith('train_') else 'dev'
            assert saved and all(r['case_id'] == case and r['split'] == split for r in saved)
    label_entries = read(SAVED_LABELS)['labels']
    assert len(label_entries) == 3
    for entry in label_entries:
        checked_jsonl(entry['workspace_path'], entry['public_sha256'])
    counts = {name: len(rows_for(name)) for name in ['old', 'student-fixed', 'student-portfolio']} if restored else None
    if restored:
        assert counts == {'old': 370, 'student-fixed': 416, 'student-portfolio': 416}
    report = {'passed': True, 'torch_version': torch.__version__, 'device': 'cpu', 'models': checks,
              'tiny_sequential_vectors': len(vectors), 'tiny_max_error': error, 'train_label_counts': counts,
              'old_labels_restored': restored, 'old_labels_policy': 'restore existing pinned blobs before explicit training; never regenerate',
              'new_saved_label_sha_checks': len(label_entries), 'old_label_sha_checks': len(refs) if restored else 0,
              'scope': 'weights and saved-feature loader only; no training, solver, replay, new quality or formal timing claim'}
    return report

def train(args):
    if args.epochs <= 0:
        raise ValueError('--epochs must be positive')
    if args.out.exists():
        raise FileExistsError('Output already exists; choose a new experiment directory')
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    module = source_module()
    model = module.PlanRanker([16] if args.architecture == 'small' else [256, 128], args.zero_columns, not args.no_skip).to(args.device)
    rows = rows_for(args.labels)
    x, y, valid, weights = tensors(rows, args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    model.train()
    for _ in range(args.epochs):
        optimizer.zero_grad(set_to_none=True)
        loss = module.ranking_loss(model(x), y, valid, model.observable(x), weights)
        assert torch.isfinite(loss)
        loss.backward()
        optimizer.step()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'model.json').write_text(json.dumps(model.export(), indent=2) + '\n', encoding='utf8')
    torch.save(model.cpu().state_dict(), args.out / 'weights.pt')
    return {'status': 'new_experiment_from_saved_train_features', 'rows': len(rows), 'epochs': args.epochs,
            'seed': args.seed, 'loss': float(loss.detach().cpu()), 'not_historical_reproduction': True,
            'validation': 'none; no dev/holdout, no closed-loop quality claim'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('verify')
    p = sub.add_parser('infer')
    p.add_argument('--model', type=Path, required=True, help='path relative to mirrored workspace')
    p.add_argument('--features', type=Path, required=True, help='JSON array of 32-dimensional saved causal features')
    p = sub.add_parser('train', help='explicit new research experiment; never run automatically')
    p.add_argument('--labels', choices=['old', 'student-fixed', 'student-portfolio'], required=True)
    p.add_argument('--architecture', choices=['small', 'large'], required=True)
    p.add_argument('--epochs', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--lr', type=float, default=.001)
    p.add_argument('--seed', type=int, default=20261030)
    p.add_argument('--zero-columns', nargs='*', type=int, default=[])
    p.add_argument('--no-skip', action='store_true')
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    if args.command == 'verify':
        result = verify()
    elif args.command == 'infer':
        import torch
        model, data = load_model(WS / args.model)
        xs = read(args.features)
        assert xs and all(len(x) == 32 for x in xs)
        with torch.inference_mode():
            result = {'scores': model(torch.tensor(xs, dtype=torch.float32)).tolist(),
                      'scope': 'saved-feature CPU inference; no policy rollout'}
        if 'w1' in data:
            result['sequential_cpp_reference_scores'] = [tiny_sequential(data, x) for x in xs]
    else:
        result = train(args)
    print(json.dumps(result, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
