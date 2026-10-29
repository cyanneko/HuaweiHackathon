"""Serial full-trace training fitness; never read eval Scores or select on eval."""
from pathlib import Path
import argparse, collections, hashlib, importlib.util, json, math, re, statistics, subprocess, time

ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent
PROJECT = ROOT.parents[1]
# Use an alias: importing local evaluate.py as "evaluate" would collide with
# its import of the public module bearing the same basename.
_spec = importlib.util.spec_from_file_location('portfolio_evaluate_for_train', ROOT/'evaluate.py')
_evaluate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_evaluate)
summarize = _evaluate.summarize
parse_metrics = _evaluate.parse_metrics
audit_case = _evaluate.audit_case
object_hash = _evaluate.object_hash
METRICS = ['Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score']


def read(path):
    return json.loads(path.read_text('utf8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def portable(path):
    try: return path.resolve().relative_to(PROJECT).as_posix()
    except ValueError: return path.name


def dump(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf8'))


def inventory(root, expected):
    inputs, identities, names = [], [], set()
    for member in sorted(p for p in root.iterdir() if p.is_dir()):
        train = member/'train'
        if not train.is_dir(): continue
        for path in sorted(train.rglob('*.txt')):
            meta_path = path.with_suffix('.meta.json')
            metadata = read(meta_path) if meta_path.is_file() else None
            stats = audit_case(path, metadata, enforce_limits=True)
            with path.open(encoding='utf-8-sig') as stream:
                stream.readline(); stream.readline()
                if [int(stream.readline().split()[0]) for _ in range(stats['k'])] != list(range(stats['k'])):
                    raise ValueError('Training input headers are not ascending')
            relative = path.relative_to(root).as_posix()
            case = member.name+'/'+path.relative_to(train).as_posix()
            if case in names: raise ValueError('Duplicate member/filename case id')
            names.add(case)
            family = 'unknown'
            if metadata:
                for key in ['family', 'scenario', 'workload_family']:
                    if isinstance(metadata.get(key), str) and metadata[key]:
                        family = metadata[key]; break
            entry = dict(case=case, member=member.name, family=family,
                         input=relative, sha256=stats['sha256'],
                         metadata_sha256=sha(meta_path) if meta_path.is_file() else None,
                         operations=stats['operations'], probe_count=stats['probe_count'],
                         k=stats['k'], p=stats['p'], memory=stats['memory'],
                         write=stats['write'], read=stats['read'], penalty=stats['penalty'],
                         period=stats['period'])
            identities.append(entry)
            inputs.append(dict(identity=entry, path=path, metadata_path=meta_path, stats=stats))
            if len(inputs)%128 == 0:
                print(json.dumps(dict(stage='audit_train', audited=len(inputs), expected=expected)), flush=True)
    if len(inputs) != expected:
        raise ValueError(f'Expected {expected} full train files, found {len(inputs)}')
    return inputs, identities


def with_base30(rows):
    result = summarize(rows)
    grouped = collections.defaultdict(list)
    for row in rows: grouped[row['case'], row['mode']].append(row['Total_Score'])
    means = {key: statistics.mean(values) for key, values in grouped.items()}
    for mode, output in result.items():
        pairs = [(value, means[case, 30]) for (case, m), value in means.items()
                 if m == int(mode) and (case, 30) in means]
        if pairs:
            candidate, baseline = (math.fsum(p[i] for p in pairs) for i in [0, 1])
            output['paired_base30_cases'] = len(pairs)
            output['base30_total_score'] = baseline
            output['decrease_vs_base30_percent'] = 100*(1-candidate/baseline) if baseline else (0.0 if not candidate else None)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ids', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--datasets-root', type=Path, default=DESIGN/'member_eval_20261030/worktree/datasets')
    ap.add_argument('--expected-cases', type=int, default=840)
    ap.add_argument('--engine', type=Path, default=ROOT/'engine')
    ap.add_argument('--timeout', type=float, default=120)
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', args.tag): ap.error('tag must be a unique plain filename token')
    ids = [int(x) for x in args.ids.split(',')]
    if not ids or len(set(ids)) != len(ids) or any(i < 0 for i in ids): ap.error('ids must be distinct nonnegative integers')
    requested_ids = ids[:]
    if 30 not in ids: ids.append(30)
    if args.repeats < 1 or args.expected_cases < 1 or not math.isfinite(args.timeout) or args.timeout <= 0: ap.error('repeats/cases/timeout must be positive')
    runs = ROOT/(args.tag+'_runs.jsonl')
    summary_path = ROOT/(args.tag+'_summary.json')
    identity_path = ROOT/(args.tag+'_identity.json')
    if any(p.exists() for p in [runs, summary_path, identity_path]): raise FileExistsError('Tag already exists; choose a new tag')
    variants_path = ROOT/'variants.json'
    variants = read(variants_path)
    registry = {int(v['id']): v for v in variants}
    registered = set(registry)|{0, 1, 2}|set(range(100, 108))
    if not set(ids) <= registered: raise ValueError('Unregistered SDK candidate id')
    engine = args.engine.resolve()
    binary_sha = sha(engine)
    sources = [ROOT/'engine.cpp', variants_path, DESIGN/'MySpillScheduler_neural.cpp',
               DESIGN/'MySpillScheduler_final.cpp', DESIGN/'holistic_20261026/reference_current.cpp']
    sources += [ROOT/v['source'] for v in variants]
    sources += [Path(_evaluate.__file__), Path(audit_case.__code__.co_filename), Path(parse_metrics.__code__.co_filename)]
    sources = list(dict.fromkeys(p.resolve() for p in sources))
    sourcehashmap = {portable(p): sha(p) for p in sources}
    def verify_program():
        if sha(engine) != binary_sha or any(sha(p) != sourcehashmap[portable(p)] for p in sources):
            raise RuntimeError('Frozen binary or source identity changed during fitness')
    inputs, input_identity = inventory(args.datasets_root.resolve(), args.expected_cases)
    members = sorted({r['member'] for r in input_identity})
    # Case ids deliberately include member/filename. Equal input bytes must
    # never collapse distinct dataset files in evaluate.summarize().
    duplicate_hashes = collections.defaultdict(list)
    for entry in input_identity: duplicate_hashes[entry['sha256']].append(entry['case'])
    train_id = object_hash(input_identity)
    try:
        revision = subprocess.run(['git','-C',str(args.datasets_root.resolve().parent),'rev-parse','HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = 'unknown'
        # Windows-created worktree locators use a drive path. Translate that
        # locator only for a read-only WSL git-dir query; never edit .git files.
        locator = args.datasets_root.resolve().parent/'.git'
        if locator.is_file():
            line = locator.read_text('utf8').strip()
            if line.startswith('gitdir: '):
                directory = line[8:].replace('\\','/')
                if re.match(r'^[A-Za-z]:/', directory) and Path('/mnt').is_dir():
                    directory = '/mnt/'+directory[0].lower()+directory[2:]
                try:
                    revision = subprocess.run(['git','--git-dir='+directory,'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
                except (OSError, subprocess.CalledProcessError): pass
    identity = dict(scope='train', fitness_only=True, fixed_eval_used=False,
        train_suite_id=train_id, dataset_revision=revision,
        datasets_root=portable(args.datasets_root), case_count=len(inputs), members=members,
        input_identity=input_identity, sourcehashmap=sourcehashmap, binary_sha256=binary_sha,
        duplicate_sha_cases={h: cases for h, cases in duplicate_hashes.items() if len(cases)>1},
        case_key='member/filename, not input SHA', ids=ids, requested_ids=requested_ids,
        tag=args.tag, repeats=args.repeats, repeat_index_base=0,
        aggregation='per-file repeat arithmetic mean; raw mean Score over all train files; no normalization')
    dump(identity_path, identity)
    rows, error = [], None
    started = time.monotonic()
    try:
        with runs.open('x', encoding='utf8') as output:
            for repeat in range(args.repeats):
                for i, entry in enumerate(inputs):
                    item, path, stats = entry['identity'], entry['path'], entry['stats']
                    if sha(path) != item['sha256']: raise RuntimeError('Frozen train input changed')
                    for mode in (ids if (i+repeat)%2 == 0 else ids[::-1]):
                        proc = subprocess.run([str(engine), str(path), str(mode)], capture_output=True, text=True, timeout=args.timeout)
                        if proc.returncode: raise RuntimeError(f'SDK returned {proc.returncode} for {item["case"]}, mode {mode}')
                        metrics = parse_metrics(proc.stdout, stats, 'official-2026-10-26')
                        row = dict(case=item['case'], member=item['member'], family=item['family'],
                                   input=item['input'], sha256=item['sha256'], mode=mode, repeat=repeat, **metrics)
                        rows.append(row); output.write(json.dumps(row, allow_nan=False)+'\n'); output.flush()
                    if sha(path) != item['sha256']: raise RuntimeError('Train input changed during SDK calls')
                    meta = entry['metadata_path']
                    if item['metadata_sha256'] is not None and sha(meta) != item['metadata_sha256']: raise RuntimeError('Frozen train metadata changed')
                    if (i+1)%32 == 0 or i+1 == len(inputs):
                        verify_program()
                        live = dict(scope='train', fitness_only=True, fixed_eval_used=False,
                            suite_id=train_id, train_suite_id=train_id, tag=args.tag, repeat=repeat+1,
                            completed_cases=i+1, total_cases=len(inputs), provisional=repeat+1<args.repeats or i+1<len(inputs),
                            summary=with_base30(rows))
                        dump(ROOT/'live_train_metrics.json', live)
                        print(json.dumps(dict(stage='train_fitness', progress=f'{repeat+1}/{args.repeats} {i+1}/{len(inputs)}',
                            mean_score={mode: value['mean_score'] for mode, value in live['summary'].items()})), flush=True)
        verify_program()
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    result = dict(**identity, status='failed' if error else 'complete',
        protocol='official-2026-10-26', measurement_count=len(rows),
        wall_seconds=time.monotonic()-started, errors=[error] if error else [],
        summary=None if error else with_base30(rows),
        by_member={} if error else {m: with_base30([r for r in rows if r['member']==m]) for m in members},
        by_family={} if error else {f: with_base30([r for r in rows if r['family']==f]) for f in sorted({r['family'] for r in rows})})
    dump(summary_path, result)
    if error: raise RuntimeError(error)
    expected = len(inputs)*len(ids)*args.repeats
    if len(rows) != expected: raise RuntimeError('Incomplete fitness measurements')
    print(json.dumps(dict(scope='train', status='complete', tag=args.tag,
                          cases=len(inputs), measurements=len(rows), summary=result['summary'])), flush=True)


if __name__ == '__main__': main()
