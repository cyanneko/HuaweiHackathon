"""Publish a portable copy of completed forced-expert1 scope diagnostics.

Run explicitly after SDK timing. This script only reads existing JSON and
writes a new public copy; it never imports or calls a solver or compiler.
The original result is immutable. Importing this module performs no work.
"""
from pathlib import Path
import hashlib
import json
import re

from publish_kernel_evidence import semantic_leaves


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
SOURCE = ROOT / 'next_credit_checks/next113_scope_r1/result.json'
TARGET = ROOT / 'next_deficit_scope_verification.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def project_prefixes():
    """Recognize both Windows and WSL spellings whichever Python runs here."""
    value = PROJECT.as_posix().replace('\\', '/').rstrip('/')
    prefixes = {value}
    drive = re.fullmatch(r'([A-Za-z]):(/.*)', value)
    mounted = re.fullmatch(r'/mnt/([A-Za-z])(/.*)', value)
    match = drive or mounted
    if match:
        letter, tail = match.groups()
        prefixes.update((letter.upper() + ':' + tail,
                         letter.lower() + ':' + tail,
                         '/mnt/' + letter.lower() + tail))
    return sorted(prefixes, key=len, reverse=True)


def portable_payload(value, prefixes):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized_key = portable_payload(key, prefixes)
            require(normalized_key not in result,
                    'Path normalization would merge distinct JSON keys')
            result[normalized_key] = portable_payload(item, prefixes)
        return result
    if isinstance(value, list):
        return [portable_payload(item, prefixes) for item in value]
    if isinstance(value, str):
        normalized = value.replace('\\', '/')
        changed = False
        for prefix in prefixes:
            if prefix + '/' in normalized:
                normalized = normalized.replace(prefix + '/', '')
                changed = True
            if normalized == prefix:
                normalized = '.'
                changed = True
            # Handle a quoted/space-delimited project root inside a command or
            # note, without truncating a different directory with that prefix.
            pattern = re.escape(prefix) + r'''(?=$|[\s"'])'''
            normalized, count = re.subn(pattern, '.', normalized)
            changed |= bool(count)
        return normalized if changed else value
    # int, float, bool, null and all non-path data are returned unchanged.
    return value


def typed_semantic_leaves(value):
    """Also distinguish bool/int and retain both 16/64-hex hashes and key hashes."""
    if isinstance(value, dict):
        return [leaf for key, item in value.items()
                for part in (key, item) for leaf in typed_semantic_leaves(part)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in typed_semantic_leaves(item)]
    if type(value) in (bool, int, float):
        return [(type(value).__name__, value)]
    if isinstance(value, str) and re.fullmatch(r'(?:[a-fA-F0-9]{16}|[a-fA-F0-9]{64})', value):
        return [('hex', value)]
    return []


def validate_scope(value):
    require(value['status'] == 'passed', 'Only a completed passed result may be published')
    require(value['diagnostic_only'] is True and value['current_online_router_evaluated'] is False,
            'Expected diagnostic-only evidence without evaluation of the current router')
    require(type(value['forced_expert']) is int and value['forced_expert'] == 1,
            'Expected the unchanged forced-expert1 experiment')
    require(value['decision_time_mathematically_certified'] is False,
            'Decision-time measurements must not be called a mathematical certificate')
    programs = value['programs']
    require(set(programs) == {'parent113', 'shift0', 'shift1', 'shift2'},
            'Expected exactly the four independent diagnostic programs')
    require(all(type(program['forced_expert']) is int and program['forced_expert'] == 1
                for program in programs.values()), 'All four programs must retain forced expert1')
    require(value['hand_proof']['full_score_guarantee'] is False
            and value['hand_proof']['D_part_of_mathematical_certificate'] is False,
            'The local prefix result must not claim full-Score or D guarantees')


def main():
    if TARGET.exists():
        raise FileExistsError('Existing published evidence is immutable')
    raw = SOURCE.read_bytes()
    original = json.loads(raw)
    validate_scope(original)
    prefixes = project_prefixes()
    published = portable_payload(original, prefixes)
    # Run the shared invariant and a stronger type/short-hash invariant before
    # appending publication metadata. Traversal order remains insertion order.
    require(semantic_leaves(published) == semantic_leaves(original),
            'Numeric/boolean/SHA256 sequence changed during normalization')
    require(typed_semantic_leaves(published) == typed_semantic_leaves(original),
            'Typed numeric/boolean/hex-hash sequence changed during normalization')
    validate_scope(published)
    require('publication' not in published, 'Source already contains publication metadata')
    published['publication'] = dict(
        original_result_sha256=hashlib.sha256(raw).hexdigest(),
        source_result=SOURCE.relative_to(PROJECT).as_posix(),
        only_project_path_metadata_normalized=True,
        numeric_values_and_hashes_unchanged=True,
        numeric_boolean_and_hex_hash_sequence_unchanged=True,
        original_result_modified=False,
        no_solver_or_compiler_invoked=True,
        current_online_router_evaluated=False,
        forced_expert_unchanged=True,
        scope=(
            'Four independent forced-expert1 diagnostic programs verify a known '
            'prefix IO calculation and a future-tail reversal. These are not '
            'current online router performance results. Recorded decision time '
            'is not a mathematical guarantee; neither D nor full Score is '
            'covered by the local prefix certificate.'),
        publisher=Path(__file__).resolve().relative_to(PROJECT).as_posix(),
        publisher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    body = (json.dumps(published, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
    require(b'/mnt/' not in body and b':/Users/' not in body and b':\\\\Users' not in body,
            'Published evidence still contains a local absolute path')
    require(SOURCE.read_bytes() == raw, 'Original result changed during publication')
    with TARGET.open('xb') as stream:
        stream.write(body)
    print('Portable next-deficit scope evidence:', TARGET.name)


if __name__ == '__main__':
    main()
