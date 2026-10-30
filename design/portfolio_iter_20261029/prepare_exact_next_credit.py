"""Prepare three forced-cover-certified p-credit candidates; never compile/fit.

Only exact_next_credit_shift and its provenance are added to the frozen parent
JSON. Nodes, experts, admission2 and inherited next_deficit_shift=0 are retained.
The builder must apply next_deficit_patch first, then exact_next_credit_patch,
using key presence for both flags (zero is an active configuration).
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from exact_next_credit_patch import LOCAL_PROOF, patch


ROOT = Path(__file__).resolve().parent
NEW_FIELDS = {'exact_next_credit_shift', 'exact_next_credit_experiment'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT / 'tree_nextcredit_next113_r1_s0.json',
        help='Parent JSON; a bare filename resolves in the script directory.')
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', args.tag):
        parser.error('Tag must be a unique plain filename token')
    parent_path = args.base.expanduser()
    if not parent_path.is_absolute() and parent_path.parent == Path('.'):
        parent_path = ROOT / parent_path
    parent_path = parent_path.resolve()
    parent_source = parent_path.with_suffix('.cpp')
    parent_bytes = parent_path.read_bytes()
    parent_sha = hashlib.sha256(parent_bytes).hexdigest()
    parent = json.loads(parent_bytes.decode('utf8'))
    if (parent.get('kind') != 'cost_sensitive_cart' or parent.get('classes') != 8 or
            not parent.get('forced_cover') or parent.get('periodic_admission_shift') != 2 or
            type(parent.get('next_deficit_shift')) is not int or parent['next_deficit_shift'] != 0):
        raise ValueError('Expected the eight-expert admission2/next-deficit-0 tree parent')
    if any(key in parent for key in NEW_FIELDS):
        raise ValueError('Parent already has exact-next-credit fields')
    if not parent_source.is_file():
        raise FileNotFoundError('Frozen parent CPP required: ' + str(parent_source))
    source_sha = sha(parent_source)
    patch_path = ROOT / 'exact_next_credit_patch.py'
    patch_sha = sha(patch_path)
    patch(parent_source.read_text('utf8'), 0)  # Source-layout validation only; no CPP is written.
    prefix = 'tree_exactcredit_' + args.tag + '_'
    manifest_path = ROOT / (prefix + 'manifest.json')
    targets = [ROOT / (prefix + 's%d.json' % shift) for shift in range(3)]
    if any(path.exists() for path in targets + [manifest_path]):
        raise FileExistsError('Exact-credit tag exists; refusing any overwrite')
    prepared, entries = [], []
    for shift, target in enumerate(targets):
        obj = deepcopy(parent)
        obj['exact_next_credit_shift'] = shift
        obj['exact_next_credit_experiment'] = {
            'parent': parent_path.name,
            'parent_json_sha256': parent_sha,
            'parent_source': parent_source.name,
            'parent_cpp_sha256': source_sha,
            'patch_module': patch_path.name,
            'patch_sha256': patch_sha,
            'tag': args.tag,
            'shift': shift,
            'p_credit_fraction': 1.0 / (1 << shift),
            'p_credit_formula': 'floor(size(p)/2^shift)/W',
            'guard_order': ['old next-deficit-0 comparison', 'p-credit can pass', 'scan only existing other victims for forcedness'],
            'certificate': 'Every protected-plan victim has size>M-size(p)-size(q); the already legal plan is an exact compulsory cover.',
            'local_proof': deepcopy(LOCAL_PROOF),
            'tree_unchanged': True,
            'expert_classes_unchanged': 8,
            'history_and_action_construction_unchanged': True,
            'only_helper_and_comparison_OR_added': True,
            'periodic_admission_shift_preserved': 2,
            'next_deficit_shift_preserved': 0,
            'additional_work': 'O(|other|) only after both numerical comparisons; no new plan call or whole-partition scan.',
            'candidate_has_measured_fitness': False,
            'inherits_parent_results_as_candidate_fitness': False,
            'status': 'candidate JSON prepared only; no compilation, train fitness or eval performed by this generator',
            'builder_support_required': 'After next_deficit_patch, apply exact_next_credit_patch.patch(source,obj[exact_next_credit_shift]) by key presence.',
        }
        if {key: value for key, value in obj.items() if key not in NEW_FIELDS} != parent:
            raise AssertionError('Original parent JSON fields changed')
        content = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
        prepared.append((target, content))
        entries.append(dict(path=target.name, sha256=hashlib.sha256(content).hexdigest(),
            exact_next_credit_shift=shift, p_credit_fraction=1.0 / (1 << shift)))
    manifest = dict(schema_version=1, kind='exact_next_credit_manifest', tag=args.tag,
        parent=parent_path.name, parent_json_sha256=parent_sha,
        parent_source=parent_source.name, parent_cpp_sha256=source_sha,
        patch_module=patch_path.name, patch_sha256=patch_sha,
        generator=Path(__file__).name, generator_sha256=sha(Path(__file__)),
        candidate_count=3, candidates=entries, tree_unchanged=True, classes=8,
        periodic_admission_shift=2, next_deficit_shift=0,
        fit_or_sdk_executed=False, candidate_fitness_unknown=True,
        local_proof=LOCAL_PROOF,
        warning='Certificate proves only additional p-credit acceptance in real-arithmetic p,q prefix IO; no full-Score or machine-certified guarantee.')
    prepared.append((manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')))
    if sha(parent_path) != parent_sha or sha(parent_source) != source_sha or sha(patch_path) != patch_sha:
        raise RuntimeError('Frozen parent or patch changed during preparation')
    for path, _ in prepared:
        if path.exists():
            raise FileExistsError('Output appeared during preparation; refusing overwrite')
    for path, content in prepared:  # Manifest last; exclusive creation also rejects races.
        with path.open('xb') as stream:
            stream.write(content)
        print(path.name, flush=True)


if __name__ == '__main__':
    main()
