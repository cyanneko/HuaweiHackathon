"""Prepare four opt-in periodic admission candidates; never compile or time.

Run explicitly after the current timing window.  build_candidates.py consumes
periodic_admission_shift by key presence, so shift=0 is an active configuration.
The four candidate names and their manifest are scoped by --tag.  Existing
candidate or manifest files are always refused, even when their bytes match.
"""

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OFFICIAL_CONTENT_SHA256 = "61b537b9ed5aa691f8a2bf8b628c3b7fdb45a09dd9ef4182733f1d209c7097db"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--base', type=Path, default=ROOT / 'tree_search_g1_1.json',
        help='Parent JSON path; a bare filename is resolved in this script directory.',
    )
    parser.add_argument(
        '--tag', default='',
        help='Optional ASCII letters/digits/underscore tag for all four names and their manifest.',
    )
    args = parser.parse_args()
    allowed_tag = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
    if args.tag and not all(c in allowed_tag for c in args.tag):
        raise ValueError('Invalid candidate tag: use ASCII letters, digits or underscore')
    base = args.base.expanduser()
    if not base.is_absolute() and base.parent == Path('.'):
        base = ROOT / base
    parent_path = base.resolve()
    parent_bytes = parent_path.read_bytes()
    parent = json.loads(parent_bytes.decode("utf8"))
    if parent.get("classes") != 8 or parent.get("kind") != "cost_sensitive_cart":
        raise ValueError("expected the unchanged eight-class parent tree")
    if not parent.get("forced_cover") or "periodic_admission_shift" in parent:
        raise ValueError("expected the forced-cover parent without admission")
    parent_sha256 = hashlib.sha256(parent_bytes).hexdigest()
    prefix = 'tree_admission_' + (args.tag + '_' if args.tag else '')
    # The suffix is intentional: build_candidates.py excludes *_manifest.json
    # from its tree_*.json candidate glob.
    manifest_path = ROOT / (prefix + 'manifest.json')
    if manifest_path.exists():
        raise FileExistsError("refusing to overwrite " + str(manifest_path))
    parent_source = parent_path.with_suffix('.cpp')
    parent_source_sha256 = (
        hashlib.sha256(parent_source.read_bytes()).hexdigest()
        if parent_source.is_file() else None
    )
    prepared = []
    candidate_records = []
    for shift in range(4):
        target = ROOT / (prefix+"s%d.json" % shift)
        if target.exists():
            raise FileExistsError("refusing to overwrite " + str(target))
        obj = deepcopy(parent)
        obj["periodic_admission_shift"] = shift
        obj["candidate_generation"] = "periodic_admission_certificate_without_fitness"
        obj["candidate_has_measured_fitness"] = False
        obj["label_caveat"] = (
            "Tree nodes and eight expert classes are copied unchanged from the parent; "
            "inherited training diagnostics describe the parent only. This new common "
            "periodic action changes trajectories and has not been compiled or evaluated. "
            "No admission candidate fitness is read to generate these configurations."
        )
        obj["periodic_admission_experiment"] = {
            "parent": parent_path.name,
            "parent_sha256": parent_sha256,
            "parent_source_sha256": parent_source_sha256,
            "tag": args.tag,
            "patch_module": "admission_patch.py",
            "proof": "admission_proof.txt",
            "official_content_sha256": OFFICIAL_CONTENT_SHA256,
            "shared_layer": True,
            "expert_classes_unchanged": 8,
            "classifier_tree_unchanged": True,
            "local_certificate": (
                "At periodic next-INSERT overflow, spill the positive resident target b "
                "only if s+t<=M, at least one other positive resident partition exists, "
                "and every such partition has size >= (s+t)*2^shift. Then total writes "
                "through that known INSERT are s+t, at most 2^-shift of the immediate "
                "write lower bound for keeping b resident."
            ),
            "shift": shift,
            "conservatism_factor": 1 << shift,
            "accepted_action": "one SPILL of the positive next-INSERT target",
            "choice_timing": (
                "Run the existing choose and requester/demand assignment before the "
                "certificate, consuming forceNext at this event; on acceptance set "
                "spilled, remember(cause=-1), increment advanced_builds, and skip plan."
            ),
            "callback_cost": (
                "O(Q) worst-case certificate scan, early rejection at the first smaller "
                "eligible partition; accepted path skips plan. Full callback D and "
                "future IO/misses must be measured, not inferred from the certificate."
            ),
            "limitations": (
                "Only one known next INSERT is used. Later growth, future probes, "
                "append writes and callback D can reverse the full-Score benefit. "
                "This is a common action layer, not a ninth expert or a new class."
            ),
            "next_validation_only": [
                "Toy cases: zero target must reject; equality accepts; one smaller victim rejects; no eligible victim rejects.",
                "M=64MiB, A=63MiB, B=1MiB, grow B to 10MiB, periodic interval 1: verify capacity, append bytes and target history.",
                "840 independent train cases before candidate selection, then 785 member cases with unchanged official timers.",
            ],
        }
        encoded = (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf8")
        prepared.append((target, encoded))
        candidate_records.append({
            "name": target.stem,
            "path": target.name,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "periodic_admission_shift": shift,
            "conservatism_factor": 1 << shift,
        })

    manifest = {
        "schema_version": 1,
        "kind": "periodic_admission_manifest",
        "tag": args.tag,
        "candidate_prefix": prefix,
        "parent": parent_path.name,
        "parent_sha256": parent_sha256,
        "parent_source": parent_source.name if parent_source_sha256 is not None else None,
        "parent_source_sha256": parent_source_sha256,
        "official_content_sha256": OFFICIAL_CONTENT_SHA256,
        "patch_module": "admission_patch.py",
        "patch_sha256": hashlib.sha256((ROOT / 'admission_patch.py').read_bytes()).hexdigest(),
        "generator": Path(__file__).name,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "proof": "admission_proof.txt",
        "proof_sha256": hashlib.sha256((ROOT / 'admission_proof.txt').read_bytes()).hexdigest(),
        "classes": 8,
        "tree_unchanged": True,
        "common_periodic_layer_changed": True,
        "candidate_count": len(candidate_records),
        "candidates": candidate_records,
        "candidate_has_measured_fitness": False,
        "compilation_or_evaluation_performed_by_generator": False,
    }
    encoded_manifest = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    # The manifest is written last, after all four candidate files succeed.
    prepared.append((manifest_path, encoded_manifest))

    # Preflight all five names before writing any. Exclusive mode also protects
    # against a different process creating one between this check and the write.
    for target, _ in prepared:
        if target.exists():
            raise FileExistsError("refusing to overwrite " + str(target))
    if hashlib.sha256(parent_path.read_bytes()).hexdigest() != parent_sha256:
        raise RuntimeError("parent changed during candidate preparation")
    if parent_source_sha256 is not None and (
            not parent_source.is_file() or
            hashlib.sha256(parent_source.read_bytes()).hexdigest() != parent_source_sha256):
        raise RuntimeError("parent source changed during candidate preparation")
    for target, encoded in prepared:
        with target.open("xb") as stream:
            stream.write(encoded)
        print(target.name, flush=True)


if __name__ == "__main__":
    main()
