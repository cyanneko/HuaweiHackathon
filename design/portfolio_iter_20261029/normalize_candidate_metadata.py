"""Normalize a publication COPY of category-candidate metadata.

normalize(obj) is pure: it copies its argument and performs no filesystem IO.
It never edits frozen candidate files, fits a model, exports C++ or runs a
program.  The optional CLI writes new canonical JSON and an evidence manifest
using exclusive creation.  Actual exported C++ byte equality remains a caller
check; unchanged export inputs alone are not presented as a completed export.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path


NORMALIZATION_KIND = 'category_full_remaining_metadata_v1'
# These are the object fields consumed by the existing build_candidates.export
# implementation. Missing keys and keys explicitly set to null are distinct.
EXECUTABLE_FIELDS = ('kind', 'tree', 'used_features', 'forced_cover',
                     'shared_scratch', 'periodic_admission_shift', 'next_deficit_shift',
                     'exact_next_credit_shift')
REWRITTEN_METADATA = frozenset((
    'ancestor_metadata', 'input_artifacts', 'data_isolation', 'config',
    'refinement', 'objective', 'validation_role', 'validation_performed',
    'train_only', 'training_horizon', 'label_caveat',
    'metadata_normalization', 'category_transition',
    'local_min_side_samples', 'local_min_side_input_groups',
))
PROXY_SEMANTICS = (
    'This legacy finite_window field refers here to the full_remaining '
    'counterfactual suffix under the frozen parent continuation. Literal T/S '
    'weights estimate sampled exposure; suffixes overlap. It is not a short '
    'truncated window, measured whole-input SDK Score, or a global oracle.'
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf8')


def sha(body):
    return hashlib.sha256(body).hexdigest()


def executable_fields(obj):
    return {key: {'present': key in obj, 'value': deepcopy(obj.get(key))}
            for key in EXECUTABLE_FIELDS}


def unchanged_executable_fields(before, after):
    return executable_fields(before) == executable_fields(after)


def legacy_proxy_notes(value, path=''):
    notes = []
    if isinstance(value, dict):
        for key, child in value.items():
            item_path = path + '/' + key
            if key.startswith('raw_finite_window'):
                notes.append(dict(path=item_path, original_field_preserved=True,
                                  meaning=PROXY_SEMANTICS))
            notes.extend(legacy_proxy_notes(child, item_path))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            notes.extend(legacy_proxy_notes(child, path + '/' + str(i)))
    return notes


def preserve_ancestor_metadata(original, fields):
    old = original.get('ancestor_metadata')
    if isinstance(old, dict):
        ancestor = deepcopy(old)
    else:
        ancestor = {}
        if 'ancestor_metadata' in original:
            ancestor['previous_ancestor_metadata'] = deepcopy(old)
    key = 'category_transition_legacy_top_level'
    counter = 1
    while key in ancestor:
        counter += 1
        key = 'category_transition_legacy_top_level_' + str(counter)
    ancestor[key] = dict(
        role='Historical parent diagnostics, not the current category training source.',
        original_values=deepcopy(fields))
    return ancestor


def normalize(obj):
    """Return a normalized publication copy; leave all executable inputs intact.

    This normalizer is scoped to the completed full-remaining category run.
    It binds source/count/objective metadata to category_transition and keeps
    the original sampling record unchanged. It does not independently audit
    input bytes, collection horizons, isolation or measured fitness.
    """
    require(isinstance(obj, dict), 'Expected a JSON object')
    result = deepcopy(obj)
    if 'category_transition' not in obj:
        return result
    marker = obj.get('metadata_normalization')
    if isinstance(marker, dict) and marker.get('kind') == NORMALIZATION_KIND:
        # Idempotent publication: never nest the same source history twice.
        return result
    transition = obj['category_transition']
    require(isinstance(transition, dict), 'Expected category_transition metadata')
    artifact = transition.get('training_artifact')
    proposal = transition.get('proposal')
    require(isinstance(artifact, dict) and isinstance(proposal, dict),
            'Category transition lacks its actual training artifact/proposal')
    require(all(key in artifact for key in ('path', 'sha256', 'rows')),
            'Incomplete category training identity')
    require(type(artifact['rows']) is int and artifact['rows'] > 0,
            'Invalid category label count')
    inventory_sha = transition.get('input_inventory_sha256')
    count = transition.get('train_input_count')
    require(isinstance(inventory_sha, str) and len(inventory_sha) == 64,
            'Missing current inventory SHA')
    require(type(count) is int and count > 0, 'Invalid current train inventory count')
    sampling = obj.get('sampling')
    require(isinstance(sampling, dict) and sampling.get('rows') == artifact['rows'],
            'Sampling/actual category artifact counts disagree')
    require(type(sampling.get('represented_inputs')) is int
            and 0 < sampling['represented_inputs'] <= count,
            'Invalid represented training input count')
    objective = proposal.get('objective_spec')
    require(isinstance(objective, dict)
            and objective.get('name') == proposal.get('objective'),
            'Category objective and objective_spec disagree')
    min_samples = transition.get('min_side_samples')
    min_groups = transition.get('min_side_input_groups')
    require(type(min_samples) is int and min_samples > 0
            and type(min_groups) is int and min_groups > 0,
            'Missing local categorical split constraints')

    replaced = {key: deepcopy(obj[key]) for key in REWRITTEN_METADATA
                if key in obj and key not in ('ancestor_metadata', 'category_transition')}
    result['ancestor_metadata'] = preserve_ancestor_metadata(obj, replaced)
    result.pop('refinement', None)
    result['input_artifacts'] = dict(training_jsonl=deepcopy(artifact),
        common_layer_parent=dict(path=transition.get('parent_path'),
                                 sha256=transition.get('parent_sha256')),
        inventory_sha256=inventory_sha)
    result['data_isolation'] = dict(train_inputs=count, inventory_sha256=inventory_sha,
        source='category_transition.input_inventory_sha256',
        eval_use='Hash exclusion only; no eval labels or costs used by category generation.',
        eval_costs_read=False, validation_labels_read=False,
        full_inventory_embedded=False,
        note='Current category metadata binds the checked inventory SHA. Eval count and overlap tables are not embedded here; old 640/568 values remain historical only.')
    result['objective'] = deepcopy(objective)
    result['config'] = dict(
        feature_set='inherited_parent_features_with_category30_mask',
        update='one existing split at category_transition.node',
        objective=proposal['objective'], objective_spec=deepcopy(objective),
        event_weighting=sampling.get('event_weighting'),
        local_min_side_samples=min_samples, local_min_side_input_groups=min_groups,
        max_depth=obj.get('configured_max_depth', obj.get('max_depth')),
        horizon='full_remaining', train_only=True, validation_performed=False)
    if 'clip_quantile' in objective:
        result['config']['absolute_cap_quantile'] = objective['clip_quantile']
    result['local_min_side_samples'] = min_samples
    result['local_min_side_input_groups'] = min_groups
    result['training_horizon'] = 'full_remaining'
    result['train_only'] = True
    result['validation_performed'] = False
    result['validation_role'] = (
        'No validation labels or costs used to generate this category change. '
        'Subsequent SDK fitness and regression are separate measurement records.')
    result['label_caveat'] = (
        'Full-remaining labels from the actual category training artifact, '
        'after one forced first expert action and a fixed parent continuation. '
        'The categorical mask search optimizes a constrained frozen-state '
        'local proxy only; T/S-weighted suffix costs overlap and CPU labels '
        'are noisy. It is neither whole-input SDK fitness nor a global oracle.')
    notes = legacy_proxy_notes(transition, '/category_transition')
    if notes:
        # Existing numeric keys and values are deliberately retained. This
        # sibling explanation adds semantics without rewriting frozen numbers.
        result['category_transition']['raw_proxy_horizon_semantics'] = PROXY_SEMANTICS
    result['metadata_normalization'] = dict(kind=NORMALIZATION_KIND,
        publication_copy_only=True, original_candidate_not_modified=True,
        current_label_rows=artifact['rows'],
        current_represented_inputs=sampling['represented_inputs'],
        current_inventory_train_inputs=count, current_inventory_sha256=inventory_sha,
        source_of_truth='category_transition, current sampling, and its proposal.objective_spec',
        horizon='full_remaining', legacy_proxy_fields=notes,
        history='Replaced top-level metadata preserved in ancestor_metadata.',
        independent_horizon_or_isolation_audit_performed=False)
    require(result['sampling'] == obj['sampling'], 'Current sampling must remain unchanged')
    require(unchanged_executable_fields(obj, result), 'Executable export inputs changed')
    # Also protect every unknown nonmetadata field, including future common
    # options not yet enumerated in EXECUTABLE_FIELDS.
    for key in set(obj) | set(result):
        if key not in REWRITTEN_METADATA:
            require((key in obj) == (key in result) and obj.get(key) == result.get(key),
                    'Nonmetadata field changed: ' + key)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path,
        help='Defaults to OUTPUT_STEM_metadata_manifest.json (excluded by builder).')
    args = parser.parse_args()
    source = args.input.resolve(strict=True)
    target = args.output.resolve()
    evidence_path = (args.evidence.resolve() if args.evidence is not None else
                     target.with_name(target.stem + '_metadata_manifest.json'))
    require(len({source, target, evidence_path}) == 3, 'Input/output/evidence paths must differ')
    for path in (target, evidence_path):
        if path.exists():
            raise FileExistsError('Refusing to overwrite ' + str(path))
    original_bytes = source.read_bytes()
    original = json.loads(original_bytes.decode('utf8'))
    normalized = normalize(original)
    output_bytes = canonical_bytes(normalized)
    before_export = executable_fields(original)
    after_export = executable_fields(normalized)
    evidence = dict(kind='candidate_metadata_normalization_evidence',
        input=dict(filename=source.name, sha256=sha(original_bytes)),
        output=dict(filename=target.name, sha256=sha(output_bytes)),
        source_file_unchanged=True, normalization_applied=normalized != original,
        executable_field_names=list(EXECUTABLE_FIELDS),
        executable_fields_unchanged=before_export == after_export,
        executable_fields_sha256=sha(canonical_bytes(before_export)),
        tree_unchanged=original.get('tree') == normalized.get('tree'),
        used_features_unchanged=original.get('used_features') == normalized.get('used_features'),
        sampling_unchanged=original.get('sampling') == normalized.get('sampling'),
        unknown_nonmetadata_fields_unchanged=True,
        cpp_byte_identity_verified=False,
        cpp_check='Caller must export both and compare actual C++ bytes before publication; no compiler/exporter was run here.')
    require(evidence['executable_fields_unchanged'], 'Executable identity mismatch')
    require(source.read_bytes() == original_bytes, 'Source changed during normalization')
    # Exclusive creation protects a concurrent publication using these names.
    for path, body in ((target, output_bytes), (evidence_path, canonical_bytes(evidence))):
        with path.open('xb') as stream:
            stream.write(body)
    print(json.dumps(dict(output=target.name, sha256=sha(output_bytes),
        evidence=evidence_path.name, executable_fields_unchanged=True,
        cpp_byte_identity_verified=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
