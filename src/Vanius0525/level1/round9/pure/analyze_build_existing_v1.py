"""Read-only attribution of the already audited proxy100 pilot; no solver.

Only the 60 train inputs named in the completed baseline are opened, and only
their two header lines. No method is selected or fitted from this report.
"""
from pathlib import Path
import hashlib
import json
import statistics
import sys

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
sys.path.insert(0, str(BASE))
from workflow import experiment_lock


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def describe(rows):
    names = ("naive", "paired100", "ai100")
    report = {"cases": len(rows)}
    if not rows:
        return report
    for name in names:
        frac = [r["methods"][name]["build_fraction"] for r in rows]
        build = sum(r["methods"][name]["build_write_us"] for r in rows)
        total = sum(r["methods"][name]["physical_us"] for r in rows)
        report[name] = {
            "sum_build_write_us": build,
            "sum_physical_us": total,
            "aggregate_build_fraction": build / total,
            "mean_case_build_fraction": statistics.mean(frac),
            "median_case_build_fraction": statistics.median(frac),
            "maximum_case_build_fraction": max(frac),
            "cases_build_fraction_gt_1pct": sum(v > .01 for v in frac),
            "cases_build_fraction_gt_5pct": sum(v > .05 for v in frac),
            "cases_build_fraction_gt_10pct": sum(v > .10 for v in frac),
        }
    for name in ("paired100", "ai100"):
        delta = [r["methods"][name]["build_total_bytes"] -
                 r["methods"]["naive"]["build_total_bytes"] for r in rows]
        report[name + "_vs_naive_build_bytes"] = {
            "less": sum(v < 0 for v in delta),
            "equal": sum(v == 0 for v in delta),
            "more": sum(v > 0 for v in delta),
            "sum_delta_bytes": sum(delta),
            "sum_delta_write_us": sum(r["methods"][name]["build_write_us"] -
                                      r["methods"]["naive"]["build_write_us"] for r in rows),
        }
    return report


def main():
    result_path = BASE / "round9/PROXY100_BASELINE_RESULTS_V3.json"
    lock_path = BASE / "round9/V21_DATASET_LOCK.json"
    results = json.loads(result_path.read_text())
    lock = json.loads(lock_path.read_text())
    assert results["complete"] and len(results["cases"]) == 60
    root = BASE / "build/round9/dataset_snapshots" / lock["snapshot_revision"] / "final_dataset"
    permitted = set(lock["train"])
    # The split has path records, not necessarily bare strings.
    if permitted and not isinstance(next(iter(permitted)), str):
        raise AssertionError("Unexpected train split format")
    rows = []
    for c in results["cases"]:
        rel = c["case"]
        assert rel.startswith("train/") and rel in permitted
        with (root / rel).open() as f:
            a, b = f.readline().strip(), f.readline().strip()
        k, p, m, w, r, penalty = map(int, a.split())
        n, callback_b = map(int, b.split())
        assert penalty == c["penalty"]
        methods = {}
        for name, run in c["audit"].items():
            costs = run["costs"]
            build_bytes = costs["build_spill_bytes"] + costs["build_append_bytes"]
            assert abs(build_bytes / w - costs["build_write_us"]) < 1e-7
            physical = sum(costs[x] for x in ("build_write_us", "probe_write_us", "probe_read_us", "miss_us"))
            methods[name] = {
                **costs, "build_total_bytes": build_bytes,
                "physical_us": physical,
                "build_fraction": costs["build_write_us"] / physical,
                "misses": run["misses"],
            }
        rows.append({"case": rel, "seed": c["seed"], "family": c["family"],
                     "input_sha256_from_original_audit": c["input_sha256"],
                     "source_sha256": c["source_sha256"],
                     "header_sha256": hashlib.sha256((a+"\n"+b+"\n").encode()).hexdigest(),
                     "header": {"K": k, "P": p, "M": m, "W": w, "R": r,
                                "penalty": penalty, "N": n, "B": callback_b},
                     "read_ge_write": r >= w, "methods": methods})
    output = {
        "scope": "Only existing proxy100 train60 audited metrics and two-line input headers; no solver, no new action evidence, no dev/eval input access.",
        "causal_limit": "Whole policies differ in PROBE and prefetch; naive vs paired/AI is not a BUILD-only treatment. Small direct BUILD cost is not an upper bound on downstream residency effects.",
        "script_sha256": sha(Path(__file__)),
        "baseline_results_sha256": sha(result_path),
        "dataset_lock_sha256": sha(lock_path),
        "all": describe(rows),
        "read_ge_write": describe([r for r in rows if r["read_ge_write"]]),
        "read_lt_write": describe([r for r in rows if not r["read_ge_write"]]),
        "families": {f: describe([r for r in rows if r["family"] == f]) for f in sorted({r["family"] for r in rows})},
        "rows": rows,
    }
    (OUT / "BUILD_EXISTING_BASELINE_DIAG_V1.json").write_text(json.dumps(output, indent=2)+"\n")
    print(json.dumps({k: output[k] for k in ("all", "read_ge_write", "read_lt_write")}, indent=2))
    print("TOP_BUILD", [(r["case"], r["methods"]["paired100"]["build_fraction"], r["methods"]["paired100"]["build_total_bytes"]-r["methods"]["naive"]["build_total_bytes"]) for r in sorted(rows, key=lambda x: x["methods"]["paired100"]["build_fraction"], reverse=True)[:6]])


if __name__ == "__main__":
    with experiment_lock():
        main()
