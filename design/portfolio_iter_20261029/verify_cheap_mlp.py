"""Cross-language classification check: saved C++ kernels versus folded NumPy.

Nothing runs on import. Invoke with Windows Python to check Windows NumPy;
the default Windows toolchain uses WSL g++, matching the research executable.
All new artifacts, compiler temporary files and logs stay in mlp_checks/<tag>.
This checks fixed training features, not online feature extraction or full SDK D.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True  # Imported helpers must not create artifacts elsewhere.
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess

import numpy as np
from cheap_mlp_export import NUMERIC_FEATURE_IDS, export_route, validate_model
from train_cheap_mlp import deployment_logits, previous_ids


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
KERNEL_START = 'static int cheapMlpDecision('
ROUTE_START = 'int route('


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def sha_text(value):
    return hashlib.sha256(value.encode('utf8')).hexdigest()


def resolve_artifact(value, manifest_path):
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    # Parent manifests use repository-relative portable paths for label files,
    # but just a filename for each model JSON.
    if path.parts and path.parts[0] == 'design':
        return (PROJECT / path).resolve()
    return (manifest_path.parent / path).resolve()


def extract_kernel(source):
    source = source.replace('\r\n', '\n')
    if source.count(KERNEL_START) != 1:
        raise ValueError('Expected one actual exported cheapMlpDecision kernel')
    begin = source.index(KERNEL_START)
    end = source.find(ROUTE_START, begin)
    if end < 0:
        raise ValueError('Expected the route method after the pure kernel')
    kernel = source[begin:end].strip() + '\n'
    if ('SystemState' in kernel or not kernel.rstrip().endswith('}') or
            kernel.count('{') != kernel.count('}')):
        raise ValueError('Could not isolate the pure balanced float kernel')
    return kernel


def load_features(path, expected_rows):
    rows = []
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            origin = str(row.get('file', '')).replace('\\', '/').lower()
            if '/train/' not in origin or '/eval/' in origin:
                raise ValueError('Non-training feature row ' + str(number))
            if str(row.get('split', 'train')).lower() not in ('train', 'training'):
                raise ValueError('Non-training split at row ' + str(number))
            rows.append(row['features'])
    result = np.asarray(rows, np.float32)
    if result.shape != (expected_rows, 32) or not np.isfinite(result).all():
        raise ValueError('Expected finite training features with shape (%d,32)' % expected_rows)
    return result


def windows_to_wsl(path):
    path = path.resolve()
    value = path.as_posix()
    if not re.match(r'^[A-Za-z]:/', value):
        raise ValueError('WSL backend requires an ordinary Windows drive path')
    return '/mnt/' + value[0].lower() + value[2:]


def checker_source(kernels, numeric_count):
    """Assemble actual saved kernels; only their function names are changed."""
    count = len(kernels)
    declarations = []
    calls = []
    for i, kernel in enumerate(kernels):
        unique = 'cheapMlpDecision_model' + str(i)
        declarations.append(kernel.replace(KERNEL_START, 'static int ' + unique + '(', 1))
        calls.append('        actual[' + str(i) + ']=' + unique + '(numeric,previous);')
    header = '''#include <array>
#include <cfenv>
#include <cmath>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(sizeof(float)==4,"Expected 32-bit float storage");
static_assert(std::numeric_limits<float>::is_iec559&&std::numeric_limits<float>::radix==2&&std::numeric_limits<float>::digits==24,"Expected IEEE binary32 float");
'''
    main = r'''
struct Difference {std::size_t row;int model,expected,actual;};
int main(int argc,char** argv){try{
    if(argc!=3)throw std::runtime_error("Expected fixture and row count");
    if(std::fegetround()!=FE_TONEAREST)throw std::runtime_error("Expected round-to-nearest floating point");
    std::ifstream input(argv[1]);
    if(!input)throw std::runtime_error("Cannot open fixture");
    input.imbue(std::locale::classic());
    const std::size_t expected_rows=std::stoull(argv[2]);
    std::array<std::size_t,MODEL_COUNT> mismatches{};
    std::vector<Difference> examples;
    std::size_t rows=0,total=0;
    std::string line;
    while(std::getline(input,line)){
        if(line.empty())continue;
        std::istringstream row(line);row.imbue(std::locale::classic());
        std::array<float,NUMERIC_COUNT> numeric;
        for(int i=0;i<NUMERIC_COUNT;++i){if(!(row>>numeric[i])||!std::isfinite(numeric[i]))throw std::runtime_error("Invalid numeric fixture field");}
        int previous=-1;if(!(row>>previous)||previous<0||previous>=8)throw std::runtime_error("Invalid previous expert");
        std::array<int,MODEL_COUNT> expected,actual;
        for(int i=0;i<MODEL_COUNT;++i)if(!(row>>expected[i])||expected[i]<0||expected[i]>=8)throw std::runtime_error("Invalid expected class");
        std::string extra;if(row>>extra)throw std::runtime_error("Extra fixture field");
CALLS
        for(int i=0;i<MODEL_COUNT;++i){
            if(actual[i]!=expected[i]){++mismatches[i];++total;
                if(examples.size()<32)examples.push_back({rows,i,expected[i],actual[i]});}
        }
        ++rows;
    }
    if(!input.eof())throw std::runtime_error("Fixture read failed");
    if(rows!=expected_rows)throw std::runtime_error("Fixture row count differs");
    std::cout<<"{\"rows\":"<<rows<<",\"models\":MODEL_COUNT,\"total_mismatches\":"<<total<<",\"mismatches\":[";
    for(int i=0;i<MODEL_COUNT;++i)std::cout<<(i?",":"")<<mismatches[i];
    std::cout<<"],\"examples\":[";
    for(std::size_t i=0;i<examples.size();++i){const auto& d=examples[i];
        std::cout<<(i?",":"")<<"{\"row_zero_based\":"<<d.row<<",\"model_index\":"<<d.model<<",\"expected\":"<<d.expected<<",\"actual\":"<<d.actual<<"}";}
    std::cout<<"]}\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}}
'''
    # MODEL_COUNT occurs both as a C++ token and inside a JSON output literal;
    # substituting it globally keeps the emitted output valid JSON.
    main = main.replace('NUMERIC_COUNT', str(numeric_count)).replace('MODEL_COUNT', str(count))
    main = main.replace('CALLS', '\n'.join(calls))
    return header + '\n'.join(declarations) + main


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'mlp_full108_mlp1_manifest.json')
    parser.add_argument('--input', type=Path, help='Defaults to the manifest-bound training labels')
    parser.add_argument('--expected-rows', type=int, default=3854)
    parser.add_argument('--toolchain', choices=('native', 'wsl'), default='wsl' if os.name == 'nt' else 'native')
    parser.add_argument('--compiler', default='g++')
    parser.add_argument('--cxx-flag', action='append', default=[], help='Additional actual deployment flag, repeatable')
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--require-windows', action='store_true', help='Reject a non-Windows Python/NumPy host')
    parser.add_argument('--prepare-only', action='store_true', help='Write fixture/kernel/checker only; do not compile or run')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', args.tag):
        parser.error('Use a unique plain directory tag')
    if args.expected_rows < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('Expected rows and timeout must be positive')
    if args.require_windows and os.name != 'nt':
        parser.error('Run this check with Windows Python to verify Windows NumPy')
    if args.toolchain == 'wsl' and os.name != 'nt':
        parser.error('WSL toolchain is for a Windows Python host')
    manifest_path = args.manifest.expanduser()
    if not manifest_path.is_absolute() and manifest_path.parent == Path('.'):
        manifest_path = ROOT / manifest_path
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text('utf8'))
    entries = manifest.get('candidates', [])
    if manifest.get('kind') != 'cheap_mlp_manifest' or len(entries) != 8 or manifest.get('candidate_count') != 8:
        raise ValueError('Expected exactly eight frozen MLP models')
    checks_root = (ROOT / 'mlp_checks').resolve()
    if checks_root.parent != ROOT:
        raise ValueError('mlp_checks must stay directly inside the script directory')
    output = checks_root / args.tag
    if output.exists():
        raise FileExistsError('Check tag already exists; never overwrite its artifacts')
    artifact = manifest['training_artifact']
    input_path = args.input.expanduser().resolve() if args.input else resolve_artifact(artifact['path'], manifest_path)
    input_sha = sha(input_path)
    if artifact.get('sha256') != input_sha or artifact.get('rows') != args.expected_rows:
        raise ValueError('Training input does not match the manifest hash/row count')
    frozen = {manifest_path: sha(manifest_path), input_path: input_sha,
              ROOT / 'train_cheap_mlp.py': sha(ROOT / 'train_cheap_mlp.py'),
              ROOT / 'cheap_mlp_export.py': sha(ROOT / 'cheap_mlp_export.py')}
    features = load_features(input_path, args.expected_rows)
    numeric_ids = list(NUMERIC_FEATURE_IDS)
    if manifest.get('numeric_feature_ids') != numeric_ids:
        raise ValueError('Manifest does not use the audited 20 numeric feature order')
    numeric = features[:, numeric_ids].astype(np.float32)
    categories = previous_ids(features)
    kernels, predictions, models = [], [], []
    model_paths = set()
    for index, entry in enumerate(entries):
        model_path = resolve_artifact(entry['path'], manifest_path)
        if model_path in model_paths:
            raise ValueError('Duplicate model in manifest')
        model_paths.add(model_path)
        model_sha = sha(model_path)
        if model_sha != entry['sha256']:
            raise ValueError('Frozen model SHA mismatch: ' + model_path.name)
        model = json.loads(model_path.read_text('utf8'))
        checked_ids, hidden, parameters = validate_model(model)
        if checked_ids != numeric_ids or model.get('training_artifact', {}).get('sha256') != input_sha:
            raise ValueError('Model features/training input differ from the fixture')
        weights = {key: np.asarray(value, np.float32) for key, value in model['weights'].items()}
        prediction = deployment_logits(weights, numeric, categories).argmax(axis=1)
        predictions.append(prediction)
        cpp_path = model_path.with_suffix('.cpp')
        source_sha = sha(cpp_path)
        actual_kernel = extract_kernel(cpp_path.read_text('utf8'))
        regenerated_kernel = extract_kernel(export_route(model))
        kernels.append(actual_kernel)
        models.append(dict(index=index, name=model_path.stem, hidden=hidden, parameters=parameters,
            model_path=str(model_path), model_sha256=model_sha,
            source_cpp_path=str(cpp_path), source_cpp_sha256=source_sha,
            source_kernel_sha256=sha_text(actual_kernel),
            regenerated_kernel_sha256=sha_text(regenerated_kernel),
            actual_kernel_matches_current_exporter=actual_kernel == regenerated_kernel,
            rows=args.expected_rows, mismatches=None))
        frozen[model_path], frozen[cpp_path] = model_sha, source_sha
    expected = np.column_stack(predictions)
    fixture_lines = []
    for row, previous, classes in zip(numeric, categories, expected):
        tokens = [format(float(value), '.9g') for value in row]
        # Nine significant digits round-trip every binary32 input. Check its
        # bits as well as equality so signed zero is not silently changed.
        round_trip = np.asarray([float(token) for token in tokens], np.float32)
        if not np.array_equal(row.view(np.uint32), round_trip.view(np.uint32)):
            raise ValueError('Float32 fixture did not round-trip with nine digits')
        fixture_lines.append(' '.join(tokens + [str(int(previous))] + [str(int(value)) for value in classes]))
    checker = checker_source(kernels, len(numeric_ids))
    checks_root.mkdir(exist_ok=True)
    output.mkdir(exist_ok=False)
    result_path = output / 'result.json'
    fixture_path = output / 'fixture.txt'
    source_path = output / 'checker.cpp'
    binary_path = output / ('checker.exe' if args.toolchain == 'native' and os.name == 'nt' else 'checker')
    result = dict(schema_version=1, status='prepared', tag=args.tag,
        scope='Actual saved C++ float kernel versus train_cheap_mlp.deployment_logits on fixed training features; no online feature or SDK D claim.',
        python_host=dict(platform=sys.platform, system=platform.system(), version=platform.python_version(),
                         numpy_version=np.__version__, windows_numpy=os.name == 'nt'),
        windows_numpy_requested=args.require_windows,
        manifest_path=str(manifest_path), manifest_sha256=frozen[manifest_path],
        input_path=str(input_path), input_sha256=input_sha,
        predictor_module_sha256=frozen[ROOT / 'train_cheap_mlp.py'],
        exporter_module_sha256=frozen[ROOT / 'cheap_mlp_export.py'],
        verifier_sha256=sha(Path(__file__)), toolchain=args.toolchain,
        numeric_feature_ids=numeric_ids, fixture_columns='20 numeric float32, previous expert integer, 8 Python expected classes in manifest order',
        numeric_accumulation_order='For each hidden: b1, numeric columns 0..19 multiply/add, one category column, ReLU; then b2 and hidden columns in order.',
        float32_fixture_significant_digits=9, models=models, rows=args.expected_rows,
        comparisons=args.expected_rows * len(models), mismatches=None,
        originals_unchanged=None, windows_numpy_classification_verified=False)
    try:
        fixture_path.write_text('\n'.join(fixture_lines) + '\n', encoding='ascii')
        source_path.write_text(checker, encoding='utf8')
        for i, kernel in enumerate(kernels):
            (output / ('kernel_%02d.cpp.inc' % i)).write_text(kernel, encoding='utf8')
        result.update(fixture_sha256=sha(fixture_path), checker_sha256=sha(source_path))
        flags = ['-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors'] + args.cxx_flag
        env = os.environ.copy()
        env.update(TMPDIR=str(output), TMP=str(output), TEMP=str(output))
        if args.toolchain == 'wsl':
            compile_command = ['wsl', '--exec', 'env', 'TMPDIR=' + windows_to_wsl(output), args.compiler] + flags + [windows_to_wsl(source_path), '-o', windows_to_wsl(binary_path)]
            run_command = ['wsl', '--exec', windows_to_wsl(binary_path), windows_to_wsl(fixture_path), str(args.expected_rows)]
        else:
            compile_command = [args.compiler] + flags + [str(source_path), '-o', str(binary_path)]
            run_command = [str(binary_path), str(fixture_path), str(args.expected_rows)]
        result.update(compile_command=compile_command, run_command=run_command,
                      fp_contraction='No extra contraction override; use actual compiler defaults/deployment flags.')
        if not args.prepare_only:
            compiled = subprocess.run(compile_command, cwd=output, env=env, capture_output=True, timeout=args.timeout)
            (output / 'compile.stdout.txt').write_bytes(compiled.stdout)
            (output / 'compile.stderr.txt').write_bytes(compiled.stderr)
            result['compile_returncode'] = compiled.returncode
            if compiled.returncode:
                raise RuntimeError('Kernel checker compilation failed; see local compile logs')
            result['binary_sha256'] = sha(binary_path)
            checked = subprocess.run(run_command, cwd=output, env=env, capture_output=True, timeout=args.timeout)
            (output / 'checker.stdout.txt').write_bytes(checked.stdout)
            (output / 'checker.stderr.txt').write_bytes(checked.stderr)
            result['checker_returncode'] = checked.returncode
            if checked.returncode:
                raise RuntimeError('Kernel checker failed; see local checker logs')
            observed = json.loads(checked.stdout.decode('utf8'))
            if observed.get('rows') != args.expected_rows or observed.get('models') != len(models):
                raise ValueError('Unexpected checker dimensions')
            counts = observed.get('mismatches')
            if (not isinstance(counts, list) or len(counts) != len(models) or
                    any(type(value) is not int or not 0 <= value <= args.expected_rows for value in counts) or
                    observed.get('total_mismatches') != sum(counts)):
                raise ValueError('Invalid checker mismatch counts')
            for model, count in zip(models, counts):
                model['mismatches'] = count
            result.update(status='verified' if not sum(counts) else 'mismatch',
                mismatches=sum(counts), examples=observed.get('examples', []),
                windows_numpy_classification_verified=os.name == 'nt' and not sum(counts))
            if sha(binary_path) != result['binary_sha256']:
                raise RuntimeError('Checker binary changed during execution')
        for path, digest in frozen.items():
            if sha(path) != digest:
                raise RuntimeError('Frozen original changed: ' + path.name)
        result['originals_unchanged'] = True
        write_json(result_path, result)
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error))
        result['originals_unchanged'] = all(path.is_file() and sha(path) == digest for path, digest in frozen.items())
        write_json(result_path, result)
        raise
    print(json.dumps(dict(result=str(result_path), status=result['status'], rows=args.expected_rows,
                          mismatches=result['mismatches'], windows_numpy=result['python_host']['windows_numpy'])), flush=True)
    if result['status'] == 'mismatch':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
