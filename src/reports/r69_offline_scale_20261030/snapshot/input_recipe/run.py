"""Frozen wrapper around the existing generator; no default/all-batch execution."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
CONFIG = ROOT / 'config.json'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8')
    temporary.replace(path)


def frozen_module(descriptor, name):
    path = WORKSPACE / descriptor['path']
    if sha(path) != descriptor['sha256']:
        raise RuntimeError('source changed; refusing unfrozen source: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def modulo_fingerprint(path, k, p, expected_n):
    """Hash opcode/op/key%P/INSERT bytes, preserving physical global order."""
    digest = hashlib.sha256()
    count = 0
    with path.open(encoding='utf8') as stream:
        for _ in range(2 + k):
            next(stream)
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            kind, op = fields[0], int(fields[1])
            if kind == 'SWITCH':
                canonical = f'SWITCH {op}\n'
            elif kind == 'INSERT':
                canonical = f'INSERT {op} {int(fields[2]) % p} {int(fields[3])}\n'
            else:
                canonical = f'PROBE {op} {int(fields[2]) % p}\n'
            digest.update(canonical.encode('ascii'))
            count += 1
    if count != expected_n:
        raise ValueError('modulo fingerprint operation count mismatch')
    return digest.hexdigest()


def probe_skew(counts, p):
    result = []
    for start in range(0, len(counts), p):
        values = counts[start:start+p]
        total = sum(values)
        shares = [value / total if total else 0. for value in values]
        result.append(dict(total=total, top1_share=max(shares),
                           top2_share=sum(sorted(shares, reverse=True)[:2]),
                           fixed_pid_0_1_share=sum(shares[:2]),
                           hhi=sum(v*v for v in shares),
                           normalized_entropy=-sum(v*math.log(v) for v in shares if v) / math.log(p)))
    return result


def generate_one(row, config, generator, validator):
    split, case_id = row['split'], row['id']
    destination = ROOT / 'data' / split / (case_id + '.txt')
    metadata_path = destination.with_suffix('.verified.json')
    if any(p.exists() for p in (destination, destination.with_suffix('.meta.json'), metadata_path)):
        raise FileExistsError('refusing overwrite; inspect existing artifacts: ' + str(destination))
    parameters = dict(config['common'])
    parameters.update({key: row[key] for key in ('scenario', 'seed', 'builds', 'probes', 'pressure')})
    generated_meta = generator.generate(destination, **parameters)
    # Existing streaming validator checks official min M, all stages/counts,
    # key/tuple bounds, one SWITCH/op and cumulative partition size <= M.
    audit = validator.audit_case(destination, metadata=generated_meta, enforce_limits=True)
    if audit['operations'] != row['expected_N']:
        raise ValueError('actual N differs from frozen case specification')
    modulo_sha = modulo_fingerprint(destination, audit['k'], audit['p'], audit['operations'])
    result = dict(schema_version=1, status='generated_input_audited', case_id=case_id,
                  split=split, seed=row['seed'], scenario=row['scenario'],
                  usage=config['split_policy'][split], independence_claim=config['split_policy']['independence_claim'],
                  requested_pressure=row['pressure'], actual_pressure=audit['pressure'],
                  requested_parameters=parameters, N=audit['operations'],
                  partition_bytes=[audit['partition_sizes'][i:i+audit['p']]
                                   for i in range(0, len(audit['partition_sizes']), audit['p'])],
                  actual_probe_counts=[audit['probe_counts'][i:i+audit['p']]
                                       for i in range(0, len(audit['probe_counts']), audit['p'])],
                  per_operator_probe_skew=probe_skew(audit['probe_counts'], audit['p']),
                  sha256=audit['sha256'], operation_stream_sha256=audit['operation_stream_sha256'],
                  modulo_operation_sha256=modulo_sha,
                  modulo_hash_schema='v1: ordered opcode op key_mod_P INSERT_bytes ASCII LF; excludes headers',
                  config_sha256=sha(CONFIG), wrapper_sha256=sha(__file__),
                  sources={key: config[key] for key in ('generator', 'validator')},
                  official_input_validation=audit,
                  limitation='input audit only; no scheduler rollout, solver, performance or official-distribution claim')
    write_json(metadata_path, result)
    manifest_path = ROOT / 'manifests' / (split + '.generated.json')
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf8'))
        if manifest['config_sha256'] != sha(CONFIG):
            raise ValueError('existing split manifest belongs to a different config')
    else:
        manifest = dict(schema_version=1, split=split, config_sha256=sha(CONFIG), cases=[])
    if any(item['case_id'] == case_id for item in manifest['cases']):
        raise ValueError('duplicate case_id in generated split manifest')
    manifest['cases'].append(dict(case_id=case_id, input=str(destination.relative_to(ROOT)),
                                  metadata=str(metadata_path.relative_to(ROOT)), N=audit['operations'],
                                  sha256=audit['sha256'], modulo_operation_sha256=modulo_sha))
    manifest['cases'].sort(key=lambda item: item['case_id'])
    write_json(manifest_path, manifest)
    print(json.dumps(dict(case_id=case_id, split=split, N=audit['operations'],
                          actual_pressure=audit['pressure'], sha256=audit['sha256']), sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument('--case', help='one exact frozen case id')
    selector.add_argument('--split', choices=['train', 'dev', 'holdout'])
    parser.add_argument('--execute', action='store_true', help='explicitly authorize generation of selected case/split')
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding='utf8'))
    ids = [row['id'] for row in config['cases']]
    seeds = [row['seed'] for row in config['cases']]
    if len(ids) != len(set(ids)) or len(seeds) != len(set(seeds)):
        raise ValueError('duplicate frozen ids/seeds')
    for row in config['cases']:
        if not re.fullmatch(r'[a-z0-9_]+', row['id']) or row['split'] not in ('train', 'dev', 'holdout'):
            raise ValueError('invalid case id/split')
        if row['expected_N'] != config['common']['operators'] * (row['builds'] + row['probes'] + 1):
            raise ValueError('incorrect frozen expected_N')
    selected = [row for row in config['cases'] if row['id'] == args.case] if args.case else [row for row in config['cases'] if row['split'] == args.split]
    if not selected:
        parser.error('case id not present in the frozen configuration')
    # Check source hashes for preview as well; import only during execute.
    for key in ('generator', 'validator'):
        if sha(WORKSPACE / config[key]['path']) != config[key]['sha256']:
            raise RuntimeError('frozen ' + key + ' source hash mismatch')
    if not args.execute:
        print(json.dumps(dict(status='preview_only_no_generation', selected=selected,
                              expected_total_N=sum(row['expected_N'] for row in selected)), indent=2))
        return
    generator = frozen_module(config['generator'], '_r66_frozen_generate')
    validator = frozen_module(config['validator'], '_r66_frozen_input_audit')
    for row in selected:
        generate_one(row, config, generator, validator)


if __name__ == '__main__':
    main()
