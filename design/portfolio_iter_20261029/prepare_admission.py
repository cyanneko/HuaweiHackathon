"""Prepare four opt-in periodic admission candidates; never compile or time.

Run explicitly after the current timing window.  build_candidates.py does not
yet consume periodic_admission_shift: its owner must opt in to admission_patch.
Existing candidate files are always refused, even when their bytes match.
"""

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OFFICIAL_CONTENT_SHA256 = "61b537b9ed5aa691f8a2bf8b628c3b7fdb45a09dd9ef4182733f1d209c7097db"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=ROOT/'tree_search_g1_1.json')
    parser.add_argument('--tag',default='')
    args=parser.parse_args()
    if args.tag and not all(c.isalnum() or c=='_' for c in args.tag):raise ValueError('Invalid candidate tag')
    parent_path = args.base.resolve()
    parent_bytes = parent_path.read_bytes()
    parent = json.loads(parent_bytes.decode("utf8"))
    if parent.get("classes") != 8 or parent.get("kind") != "cost_sensitive_cart":
        raise ValueError("expected the unchanged eight-class parent tree")
    if not parent.get("forced_cover") or "periodic_admission_shift" in parent:
        raise ValueError("expected the forced-cover parent without admission")
    parent_sha256 = hashlib.sha256(parent_bytes).hexdigest()
    prepared = []
    for shift in range(4):
        prefix='tree_admission_'+(args.tag+'_' if args.tag else '')
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

    # Preflight all four names before writing any. Exclusive mode also protects
    # against a different process creating one between this check and the write.
    if hashlib.sha256(parent_path.read_bytes()).hexdigest() != parent_sha256:
        raise RuntimeError("parent changed during candidate preparation")
    for target, encoded in prepared:
        with target.open("xb") as stream:
            stream.write(encoded)
        print(target.name, flush=True)


if __name__ == "__main__":
    main()
