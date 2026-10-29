"""Prepare eight constant-expert controls with the current online common layer.

Explicit preparation only: no fitting, score-artifact reads, compilation or
solver execution. The parent contributes ONLY forced_cover/shared_scratch/
periodic_admission_shift. Its tree and training/validation metadata are unused.
Each one-leaf numeric tree is consumable by build_candidates.py. Expert IDs
0..7 are not engine mode IDs; the builder assigns the latter independently.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
COMMON_FIELDS = ('forced_cover', 'shared_scratch', 'periodic_admission_shift')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2,
                       allow_nan=False) + '\n').encode('utf8')


def local_input(path):
    path = path.expanduser()
    if not path.is_absolute() and path.parent == Path('.'):
        path = ROOT / path
    return path.resolve(strict=True)


def portable(path):
    try:
        return path.resolve().relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def online_common(parent):
    require(parent.get('classes') == 8 and parent.get('feature_count') == 32,
            'Expected an eight-expert, 32-feature parent')
    common = {key: parent[key] for key in COMMON_FIELDS if key in parent}
    for key in ('forced_cover', 'shared_scratch'):
        require(key not in common or type(common[key]) is bool,
                'Expected a boolean ' + key)
    require(common.get('forced_cover') is True,
            'Expected the current forced-cover common layer')
    require(type(common.get('periodic_admission_shift')) is int
            and common['periodic_admission_shift'] == 2,
            'Expected the current admission2 common layer')
    # Preserve key absence: the builder treats a missing shared_scratch as off.
    return common


def expert_names(path, explicitly_requested):
    if not path.is_file():
        require(not explicitly_requested, 'Explicit expert catalog does not exist')
        return [None] * 8, None, None
    body = path.read_bytes()
    catalog = json.loads(body.decode('utf-8-sig'))
    require(isinstance(catalog, list) and len(catalog) == 8,
            'Expected exactly eight expert catalog entries')
    names = {}
    for entry in catalog:
        require(isinstance(entry, dict) and type(entry.get('id')) is int
                and 0 <= entry['id'] < 8 and entry['id'] not in names,
                'Expert catalog IDs must be exactly 0..7')
        require(isinstance(entry.get('name'), str) and entry['name'].strip(),
                'Expert catalog name must be nonempty')
        names[entry['id']] = entry['name']
    return [names[i] for i in range(8)], body, digest(body)


def constant_model(expert, common):
    # Construct from scratch: no inherited tree, objective, labels, metrics,
    # validation diagnostics, provider notes, or stale data-isolation claims.
    return dict(
        schema_version=2,
        kind='cost_sensitive_cart',
        classes=8,
        feature_count=32,
        requested_features=[],
        used_features=[],
        threshold_dtype='float32',
        comparison='<=',
        node_count=1,
        leaf_count=1,
        max_depth=0,
        configured_max_depth=0,
        tree=[dict(id=0, depth=0, expert=expert)],
        **common,
        candidate_generation='fixed_expert_same_online_common_layer_no_fitting',
        fixed_expert_id=expert,
        fitted=False,
        candidate_has_measured_fitness=False,
        experiment_role=(
            'One of all eight fixed-expert ablations under the same online '
            'common layer as the parent. The router always returns this expert; '
            'common certificates, history and expert logic remain active.'),
        parent_metadata_inherited=False,
        score_artifacts_read=False,
        compilation_or_evaluation_performed_by_generator=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path,
                        default=ROOT / 'tree_category_full108_r1_3.json',
                        help='Parent JSON; bare filenames resolve beside this script.')
    parser.add_argument('--base-cpp', type=Path,
                        help='Optional parent C++ identity; defaults to --base with .cpp suffix.')
    parser.add_argument('--tag', default='shared113',
                        help='ASCII letters/digits/underscore; scopes eight candidates and manifest.')
    parser.add_argument('--catalog', type=Path,
                        help='Optional eight-rule catalog; defaults to neural_selector/catalog.json if present.')
    args = parser.parse_args()
    require(re.fullmatch(r'[A-Za-z0-9_]{1,64}', args.tag) is not None,
            'Tag must contain 1..64 ASCII letters, digits or underscores')
    parent_path = local_input(args.base)
    parent_cpp = local_input(args.base_cpp) if args.base_cpp else parent_path.with_suffix('.cpp')
    require(parent_cpp.is_file(), 'Parent CPP identity is required; use --base-cpp if needed')
    parent_bytes = parent_path.read_bytes()
    cpp_bytes = parent_cpp.read_bytes()
    parent = json.loads(parent_bytes.decode('utf-8-sig'))
    common = online_common(parent)
    parent_hash, cpp_hash = digest(parent_bytes), digest(cpp_bytes)
    catalog_path = (local_input(args.catalog) if args.catalog is not None
                    else ROOT.parent / 'neural_selector/catalog.json')
    names, catalog_bytes, catalog_hash = expert_names(catalog_path, args.catalog is not None)
    generator_path = Path(__file__).resolve()
    generator_hash = digest(generator_path.read_bytes())

    # Bind the code that will later implement the common layer. No imports of
    # builders/trainers occur: importing this module performs no preparation.
    dependency_paths = [ROOT / 'build_candidates.py', ROOT / 'admission_patch.py',
                        ROOT.parent / 'neural_selector/Scheduler.template']
    dependencies = [dict(path=portable(path), sha256=digest(path.read_bytes()))
                    for path in dependency_paths]
    prefix = 'tree_fixed_' + args.tag
    prepared, records = [], []
    for expert in range(8):
        target = ROOT / (prefix + '_e' + str(expert) + '.json')
        model = constant_model(expert, common)
        require(set(COMMON_FIELDS).intersection(model) == set(common),
                'Unexpected inherited common-layer key')
        require(model['tree'] == [dict(id=0, depth=0, expert=expert)]
                and model['used_features'] == [], 'Invalid constant-router construction')
        body = encoded(model)
        prepared.append((target, body))
        records.append(dict(name=target.stem, path=target.name, sha256=digest(body),
                            expert_id=expert, rule_name=names[expert],
                            engine_mode_id=None,
                            engine_mode_id_assignment='Later by build_candidates.py; not the expert ID'))
    # *_manifest is excluded by the builder's tree_*.json candidate scan.
    manifest_path = ROOT / (prefix + '_manifest.json')
    manifest = dict(
        schema_version=1,
        kind='fixed_expert_shared_layer_ablation_manifest',
        tag=args.tag,
        candidate_count=8,
        expert_ids=list(range(8)),
        classes=8,
        feature_count=32,
        parent_json=portable(parent_path),
        parent_json_sha256=parent_hash,
        parent_cpp=portable(parent_cpp),
        parent_cpp_sha256=cpp_hash,
        inherited_online_fields=common,
        missing_shared_scratch_means_disabled='shared_scratch' not in common,
        inherited_parent_field_allowlist=list(COMMON_FIELDS),
        parent_tree_or_training_validation_metadata_inherited=False,
        all_eight_rules_included_without_selection=True,
        router='One numeric leaf; returns fixed expert ID without evaluating features.',
        comparison_scope=(
            'Fixed-expert controls share the current forced-cover, scratch option '
            'and admission2 layer. This avoids comparing against modes100..107 '
            'whose old neural-reference common layer differs.'),
        fitted=False,
        score_artifacts_read=False,
        compilation_or_evaluation_performed_by_generator=False,
        next_step='Separately build, audit and measure all eight controls; no selection or benefit claimed here.',
        catalog=(dict(path=portable(catalog_path), sha256=catalog_hash)
                 if catalog_hash is not None else None),
        generator=portable(generator_path),
        generator_sha256=generator_hash,
        future_builder_dependencies=dependencies,
        candidates=records,
    )
    prepared.append((manifest_path, encoded(manifest)))

    # Unified preflight for all nine outputs, before any candidate is written.
    # Exclusive creation also rejects a file introduced after the preflight.
    require(len({path for path, _ in prepared}) == 9, 'Output names must be unique')
    for target, _ in prepared:
        if target.exists():
            raise FileExistsError('Refusing to overwrite ' + target.name)
    require(digest(parent_path.read_bytes()) == parent_hash
            and digest(parent_cpp.read_bytes()) == cpp_hash,
            'Parent JSON/CPP changed during preparation')
    require(digest(generator_path.read_bytes()) == generator_hash,
            'Generator changed during preparation')
    if catalog_bytes is not None:
        require(catalog_path.read_bytes() == catalog_bytes, 'Expert catalog changed during preparation')
    for path, record in zip(dependency_paths, dependencies):
        require(digest(path.read_bytes()) == record['sha256'], 'Builder dependency changed during preparation')
    # Manifest last: its presence signals that all eight candidate writes ran.
    for target, body in prepared:
        with target.open('xb') as stream:
            stream.write(body)
        print(target.name, flush=True)


if __name__ == '__main__':
    main()
