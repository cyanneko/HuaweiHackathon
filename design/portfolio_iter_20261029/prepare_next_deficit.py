"""Prepare three next-deficit-credit candidates without compiling or timing.

Only next_deficit_shift and new experiment provenance are added to the parent
JSON. Existing parent fields, tree nodes and public admission layers are copied
unchanged. New files/manifest are exclusive; a tag can never overwrite a record.
The builder must explicitly support next_deficit_shift BY KEY PRESENCE (s0=0).
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from next_deficit_patch import LOCAL_PROOF, patch


ROOT = Path(__file__).resolve().parent
NEW_FIELDS = {'next_deficit_shift', 'next_deficit_experiment'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT / 'tree_category_full108_r1_3.json',
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
    if parent.get('kind') != 'cost_sensitive_cart' or parent.get('classes') != 8:
        raise ValueError('Expected an unchanged eight-expert tree parent')
    if any(key in parent for key in NEW_FIELDS):
        raise ValueError('Parent already has next-deficit experiment fields')
    if not parent.get('forced_cover') or parent.get('periodic_admission_shift') != 2:
        raise ValueError('Expected the current forced-cover/admission2 common layers')
    if not parent_source.is_file():
        raise FileNotFoundError('Frozen parent CPP is required for provenance: ' + str(parent_source))
    source_sha = sha(parent_source)
    patch_path = ROOT / 'next_deficit_patch.py'
    patch_sha = sha(patch_path)
    # Validate the exact original branch in memory. No patched CPP is written.
    patch(parent_source.read_text('utf8'), 0)
    prefix = 'tree_nextcredit_' + args.tag + '_'
    manifest_path = ROOT / (prefix + 'manifest.json')
    targets = [ROOT / (prefix + 's%d.json' % shift) for shift in range(3)]
    if any(path.exists() for path in targets + [manifest_path]):
        raise FileExistsError('Next-credit tag exists; refusing any overwrite')
    prepared, entries = [], []
    for shift, target in enumerate(targets):
        obj = deepcopy(parent)
        obj['next_deficit_shift'] = shift
        obj['next_deficit_experiment'] = {
            'parent': parent_path.name,
            'parent_json_sha256': parent_sha,
            'parent_source': parent_source.name,
            'parent_cpp_sha256': source_sha,
            'patch_module': patch_path.name,
            'patch_sha256': patch_sha,
            'tag': args.tag,
            'shift': shift,
            'credit_fraction': 1.0 / (1 << shift),
            'credit_formula': 'max(1us, floor(max(0,qsize-(M-U+f1-sizep))/2^shift)/W)',
            'local_proof': deepcopy(LOCAL_PROOF),
            'tree_unchanged': True,
            'expert_classes_unchanged': 8,
            'history_and_action_construction_unchanged': True,
            'only_one_comparison_changed': True,
            'common_admission_shift_preserved': parent['periodic_admission_shift'],
            'candidate_has_measured_fitness': False,
            'inherits_parent_results_as_candidate_fitness': False,
            'status': 'candidate JSON prepared only; no compilation, train fitness or eval has been performed by this generator',
            'builder_support_required': 'Apply next_deficit_patch.patch(source, obj[next_deficit_shift]) when the key exists, including shift=0.',
        }
        if {key: value for key, value in obj.items() if key not in NEW_FIELDS} != parent:
            raise AssertionError('Unexpected change to original parent JSON fields')
        content = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
        prepared.append((target, content))
        entries.append(dict(path=target.name, sha256=hashlib.sha256(content).hexdigest(),
            next_deficit_shift=shift, credit_fraction=1.0 / (1 << shift)))
    manifest = dict(schema_version=1, kind='next_deficit_credit_manifest', tag=args.tag,
        parent=parent_path.name, parent_json_sha256=parent_sha,
        parent_source=parent_source.name, parent_cpp_sha256=source_sha,
        patch_module=patch_path.name, patch_sha256=patch_sha,
        generator=Path(__file__).name, generator_sha256=sha(Path(__file__)),
        candidate_count=3, candidates=entries, tree_unchanged=True, classes=8,
        periodic_admission_shift=parent['periodic_admission_shift'],
        fit_or_sdk_executed=False, candidate_fitness_unknown=True,
        local_proof=LOCAL_PROOF,
        warning='Only newly accepted region has a real-arithmetic local IO certificate; the inherited +1us tolerance and full Score have no such guarantee.')
    prepared.append((manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')))
    if sha(parent_path) != parent_sha or sha(parent_source) != source_sha or sha(patch_path) != patch_sha:
        raise RuntimeError('Frozen parent or patch changed during preparation')
    for path, _ in prepared:
        if path.exists():
            raise FileExistsError('Output appeared during preparation; refusing overwrite')
    # All four names are preflighted; manifest is written last. Exclusive mode
    # also prevents a concurrent process from replacing an existing artifact.
    for path, content in prepared:
        with path.open('xb') as stream:
            stream.write(content)
        print(path.name, flush=True)


if __name__ == '__main__':
    main()
