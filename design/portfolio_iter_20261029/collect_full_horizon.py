"""Prepare or collect training-only full-remaining-trace counterfactual labels.

Reuses collect_on_policy.prepare's rotated expert order and per-kind T/S
statistics, but finalizes only newly created tag files with end=N. A preexisting
tag is always rejected; historical teachers, labels and provenance are untouched.
Full future and true p remain teacher-only; the online scheduler source is not
edited. Full remaining cost under one fixed continuation is not a global oracle.
"""
from __future__ import annotations
from pathlib import Path
import argparse, collections, hashlib, json, math, re, subprocess, time
from collect_on_policy import prepare

ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent
PROJECT = ROOT.parents[1]
HORIZON_LINES = (
    '        int end=std::min(int(input->rows.size()),pos+384);\n'
    '        if(kind!=1)end=std::min(int(input->rows.size()),std::min(pos+2048,std::max(end,input->switched[co]+128)));'
)
SAMPLE_EXPRESSION = 'kind==1?cap:std::max(4,cap/3)'


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


def input_identity(paths, root):
    rows = []
    for path in paths:
        if '/train/' not in path.as_posix() or '/eval/' in path.as_posix():
            raise ValueError('Only explicit training paths may be collected')
        with path.open(encoding='utf-8-sig') as stream:
            stream.readline(); operations = int(stream.readline().split()[0])
        rows.append(dict(path=path.relative_to(root).as_posix(), sha256=sha(path), operations=operations))
    return rows


def validate_labels(path, inputs, caps):
    operations = {str(p): row['operations'] for p,row in inputs}
    counts = collections.Counter(); sampled = {}; totals = {}
    with path.open(encoding='utf8') as stream:
        for line in stream:
            if not line.strip(): continue
            row = json.loads(line); key = (row['file'], int(row['kind']))
            if key[0] not in operations or key[1] not in [0,1,2]: raise ValueError('Unexpected training file/kind in labels')
            if int(row['end']) != operations[key[0]]: raise ValueError('Label is not full remaining trace')
            total, take = int(row['event_total']), int(row['event_sampled'])
            if not 1 <= take <= min(total,caps[key[1]]): raise ValueError('Invalid per-kind T/S statistics')
            if key in sampled and (sampled[key] != take or totals[key] != total): raise ValueError('Inconsistent T/S group')
            sampled[key], totals[key] = take,total
            counts[key] += 1
            if len(row['features']) != 32 or len(row['costs']) != 8: raise ValueError('Unexpected feature/cost dimensions')
            for field in ['features','costs','decision_us']:
                if not all(math.isfinite(float(v)) for v in row[field]): raise ValueError('Nonfinite labels')
    if any(counts[key] != take for key,take in sampled.items()): raise ValueError('Sample counts do not match event_sampled')
    per_file = collections.Counter()
    for (filename,kind), count in counts.items(): per_file[filename] += count
    if any(count>6 for count in per_file.values()): raise ValueError('More than six sampled states for a file')
    return dict(label_rows=sum(counts.values()), represented_training_inputs=len(per_file),
                max_states_per_file=max(per_file.values(),default=0),
                per_kind_label_rows={str(k):sum(n for (f,kind),n in counts.items() if kind==k) for k in [0,1,2]},
                all_label_ends_equal_input_operations=True, T_over_S_counts_verified=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', required=True, help='Frozen scheduler source stem in this directory')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--data-root', type=Path, default=DESIGN/'member_eval_20261030/worktree/datasets')
    ap.add_argument('--expected-train', type=int, default=840)
    ap.add_argument('--cap', type=int, default=4, help='Maximum miss decision samples per input')
    ap.add_argument('--nonmiss-cap', type=int, default=1, help='Maximum samples for each of overflow and periodic')
    ap.add_argument('--prepare-only', action='store_true')
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',args.tag): ap.error('Tag must be a unique plain filename token')
    model = args.model[:-4] if args.model.endswith('.cpp') else args.model
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',model): ap.error('Model must be a source stem, without a directory')
    if args.cap<0 or args.nonmiss_cap<0 or not 1<=args.cap+2*args.nonmiss_cap<=6: ap.error('Caps must be nonnegative and sum to 1..6 states per file')
    if args.expected_train<1: ap.error('expected-train must be positive')
    names = dict(teacher=ROOT/(args.tag+'_teacher.cpp'), binary=ROOT/(args.tag+'_teacher'),
                 paths=ROOT/(args.tag+'_paths.txt'), labels=ROOT/(args.tag+'_labels.jsonl'),
                 provenance=ROOT/(args.tag+'_provenance.json'), compile_log=ROOT/(args.tag+'_compile.log'))
    protected = list(names.values())+[ROOT/(args.tag+'_teacher.exe'),ROOT/(args.tag+'_labels.jsonl.gz')]
    if any(path.exists() for path in protected): raise FileExistsError('Tag artifacts already exist; use a new tag, never overwrite frozen records')
    data_root = args.data_root.resolve()
    paths = sorted(data_root.glob('*/train/*.txt'))
    if len(paths)!=args.expected_train: raise ValueError('Unexpected training inventory size')
    source = ROOT/(model+'.cpp')
    if not source.is_file(): raise FileNotFoundError(source.name)
    source_sha = sha(source)
    identities = input_identity(paths,data_root)
    teacher = prepare(model,args.tag,data_root,args.expected_train)
    if teacher.resolve()!=names['teacher'].resolve(): raise ValueError('Unexpected prepare output path')
    provenance = json.loads(names['provenance'].read_text('utf8'))
    constructed_sha = sha(teacher)
    if provenance['source_sha256']!=source_sha or provenance['teacher_sha256']!=constructed_sha: raise ValueError('Initial prepare identities changed')
    text = teacher.read_text('utf8')
    if text.count(HORIZON_LINES)!=1 or text.count(SAMPLE_EXPRESSION)!=1: raise ValueError('Teacher template differs; refusing ambiguous patches')
    text = text.replace(HORIZON_LINES,'        int end=int(input->rows.size());',1)
    text = text.replace(SAMPLE_EXPRESSION,f'kind==1?cap:{args.nonmiss_cap}',1)
    # Keep the runtime teacher subject to the six-state budget and current-tree
    # continuation even if someone later invokes the prepared binary manually.
    main_tail = ';std::string path;\n    while(std::getline(list,path))'
    if text.count(main_tail)!=1: raise ValueError('Teacher main differs')
    guard = f';if(cap<0||cap+2*{args.nonmiss_cap}>6||cap+2*{args.nonmiss_cap}<1||mode!=-1||continuation!=-1)throw std::runtime_error("full-horizon budget or continuation");std::string path;\n    while(std::getline(list,path))'
    text = text.replace(main_tail,guard,1)
    preserved = ['for(int order=0;order<8;++order){int e=(order+pos)%8;',
                 'event_totals[kind]=int(group.size());sample_totals[kind]=take;',
                 'second.event_totals=event_totals;second.sample_totals=sample_totals;',
                 'event_totals[kind]<<', 'sample_totals[kind]<<']
    if not all(marker in text for marker in preserved): raise ValueError('Rotated order or T/S instrumentation was lost')
    teacher.write_bytes(text.encode('utf8'))
    caps = {0:args.nonmiss_cap,1:args.cap,2:args.nonmiss_cap}
    provenance.update(status='prepared', horizon='full_remaining_trace',
        constructed_teacher_sha256=constructed_sha, teacher_sha256=sha(teacher),
        original_teacher_template_sha256=sha(DESIGN/'neural_selector/teacher.cpp'),
        prepare_module_sha256=sha(ROOT/'collect_on_policy.py'), wrapper_sha256=sha(Path(__file__)),
        reference_types_sha256=sha(DESIGN/'neural_selector/reference_types.hpp'),
        source_json_sha256=sha(source.with_suffix('.json')) if source.with_suffix('.json').is_file() else None,
        source_path=portable(source),teacher_path=portable(teacher),training_input_identity=identities,
        paths_sha256=sha(names['paths']),trajectory_mode=-1,continuation_mode=-1,
        expert_order='e=(order+pos)%8; all eight expert costs stored by expert id',
        sampling_caps=dict(miss=args.cap,overflow=args.nonmiss_cap,periodic=args.nonmiss_cap,
                           actual_per_file_max=args.cap+2*args.nonmiss_cap,hard_limit=6),
        weight='event_total/event_sampled per file and callback kind; totals refer to the full parent trajectory',
        cost='Remaining IO + true offline p times future misses + measured callback CPU, under one common continuation',
        online_boundary='Only the offline teacher reads full future and true p; the frozen online source is unchanged.',
        caveats=['CPU labels contain measurement noise despite rotated order.',
                 'Visible features can alias states with different hidden parameters/future.',
                 'One forced first action plus a fixed continuation is not a global optimal oracle.',
                 'T/S weighting is a sample-exposure estimate; rollout windows overlap.'],
        compile_command=['g++','-std=c++14','-O2',teacher.name,'-o',names['binary'].name],
        runtime_arguments=[names['paths'].name,names['labels'].name,str(args.cap),'-1','-1'])
    dump(names['provenance'],provenance)
    if args.prepare_only:
        print(json.dumps(dict(tag=args.tag,status='prepared',teacher=teacher.name,
                             teacher_sha256=provenance['teacher_sha256'],horizon='full_remaining_trace')),flush=True)
        return
    started = time.monotonic()
    try:
        if sha(source)!=source_sha: raise RuntimeError('Frozen source changed before compile')
        proc = subprocess.run(['g++','-std=c++14','-O2',str(teacher),'-o',str(names['binary'])],capture_output=True,text=True)
        names['compile_log'].write_bytes((proc.stdout+proc.stderr).encode('utf8'))
        if proc.returncode: raise RuntimeError('Full-horizon teacher compilation failed')
        provenance.update(status='collecting',binary_sha256=sha(names['binary']))
        dump(names['provenance'],provenance)
        subprocess.run([str(names['binary']),str(names['paths']),str(names['labels']),str(args.cap),'-1','-1'],check=True,timeout=1800)
        if sha(source)!=source_sha or sha(teacher)!=provenance['teacher_sha256']: raise RuntimeError('Frozen source or teacher changed')
        for path,identity in zip(paths,identities):
            if sha(path)!=identity['sha256']: raise RuntimeError('Training input changed during collection')
        provenance.update(status='collected',labels_sha256=sha(names['labels']),
            validation=validate_labels(names['labels'],list(zip(paths,identities)),caps),
            elapsed_seconds=time.monotonic()-started)
        dump(names['provenance'],provenance)
    except Exception as exc:
        provenance.update(status='failed',error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        if names['labels'].is_file(): provenance['partial_labels_sha256']=sha(names['labels'])
        dump(names['provenance'],provenance)
        raise
    print(json.dumps(dict(tag=args.tag,status='collected',horizon='full_remaining_trace',
                         validation=provenance['validation'])),flush=True)


if __name__ == '__main__': main()
