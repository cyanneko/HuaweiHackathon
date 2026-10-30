"""Independent completion/source/gate check of the closed cold-BUILD trial."""
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    freeze = json.loads((HERE/"COLD_BUILD_BUILD_FREEZE_V1.json").read_text())
    for name, expected in freeze["files"].items():
        assert sha(HERE/name) == expected, name
    previous_checks = {}
    for name, expected in freeze["previous_closed_freezes"].items():
        assert sha(HERE/name) == expected, name
        closed = json.loads((HERE/name).read_text())
        for file, digest in closed.get("files", {}).items():
            assert sha(HERE/file) == digest, file
        previous_checks[name] = True
    result = json.loads((HERE/"COLD_BUILD_RESULTS_V1.json").read_text())
    summary = json.loads((HERE/"COLD_BUILD_SUMMARY_V1.json").read_text())
    plan = json.loads((HERE/"COLD_BUILD_PLAN_V1.json").read_text())
    base = json.loads((ROOT/"round9/PROXY100_BASELINE_RESULTS_V3.json").read_text())
    assert sha(ROOT/"round9/PROXY100_BASELINE_RESULTS_V3.json") == plan["baseline_results_sha256"]
    original = {r["case"]: r for r in base["cases"]}
    rows = result["records"]
    assert len(rows) == 60 and len({r["seed"] for r in rows}) == 60
    assert [r["case"] for r in rows] == [r["case"] for r in plan["cases"]]
    component_keys = ("build_write_us", "probe_write_us", "probe_read_us", "miss_us")
    ratios, old_scores, new_scores = [], [], []
    build_same_naive = 0
    for r in rows:
        c = original[r["case"]]
        assert r["all_checks_passed"] and len(r["runs"]) == 3
        assert r == json.loads((ROOT/"build/round9_pure_cold_build_v1"/(Path(r["case"]).stem+".json")).read_text())
        a, b = r["audit"]["costs"], c["audit"]["paired100"]["costs"]
        ratios.append(math.fsum(a[k] for k in component_keys)/math.fsum(b[k] for k in component_keys))
        n = c["audit"]["naive"]["costs"]
        build_same_naive += a["build_spill_bytes"]+a["build_append_bytes"] == n["build_spill_bytes"]+n["build_append_bytes"]
        for j in range(3):
            denominator = c["runs"]["naive"][j]["Total_Score"]
            old_scores.append(min(10, max(0, 10*(1-c["runs"]["paired100"][j]["Total_Score"]/denominator))))
            new_scores.append(min(10, max(0, 10*(1-r["runs"][j]["Total_Score"]/denominator))))
        prefix = r["prefix_comparison"]
        if not r["read_ge_write"]:
            assert prefix["full_trace_equal"] and prefix["q0_prefix_equal"]
        if not prefix["q0_prefix_equal"]:
            assert prefix["first_q0_difference"]["probe_q"] == 0
            assert prefix["first_q0_difference"]["reference_trace"].startswith("TRACE O ")
    mean_ratio, worst_ratio = math.fsum(ratios)/60, max(ratios)
    score_delta = math.fsum(new_scores)/180-math.fsum(old_scores)/180
    assert abs(mean_ratio-summary["all"]["mean_physical_ratio"]) < 1e-14
    assert abs(worst_ratio-summary["all"]["worst_physical_ratio"]) < 1e-14
    assert abs(score_delta-summary["all"]["mean_score_delta"]) < 1e-14
    checks = {"mean_physical_ratio": mean_ratio <= .995, "worst_physical_ratio": worst_ratio <= 1.02,
              "decision_inclusive_score": score_delta >= 0, "all_audit_and_trace_checks": True}
    assert checks == summary["gate_checks"]
    assert summary["eligible_for_root_dev_review"] == all(checks.values())
    pairs = [(r["prefix_comparison"]["reference_prefix"], r["prefix_comparison"]["candidate_prefix"]) for r in rows]
    total_new = math.fsum(r["audit"]["costs"][k] for r in rows for k in component_keys)
    total_old = math.fsum(original[r["case"]]["audit"]["paired100"]["costs"][k] for r in rows for k in component_keys)
    output = {"results_sha256": sha(HERE/"COLD_BUILD_RESULTS_V1.json"),
              "summary_sha256": sha(HERE/"COLD_BUILD_SUMMARY_V1.json"),
              "reviewer_sha256": sha(Path(__file__)),
              "previous_closed_files_unchanged": previous_checks,
              "cases": 60, "independent_seeds": 60, "new_solver_runs": 240,
              "candidate_build_total_bytes_equal_naive_cases": build_same_naive,
              "aggregate_physical_ratio": total_new/total_old,
              "recomputed_gate_checks": checks,
              "prefix_totals": {
                  "reference_overflows": sum(a["overflow_callbacks"] for a,b in pairs),
                  "candidate_overflows": sum(b["overflow_callbacks"] for a,b in pairs),
                  "reference_build_spill_actions": sum(a["build_spill_actions"] for a,b in pairs),
                  "candidate_build_spill_actions": sum(b["build_spill_actions"] for a,b in pairs),
                  "mixed_phase_overflows_both": sum(a["mixed_phase_overflows"]+b["mixed_phase_overflows"] for a,b in pairs),
                  "q0_loads_both": sum(a["loads"]+b["loads"] for a,b in pairs),
                  "same_preprobe_resident_set": sum(r["prefix_comparison"]["resident_symmetric_difference_bytes"] == 0 for r in rows)},
              "decision_us_sum_case_mean_reference": math.fsum(st.mean(x["Total_Decision_Time"] for x in original[r["case"]]["runs"]["paired100"]) for r in rows),
              "decision_us_sum_case_mean_candidate": math.fsum(st.mean(x["Total_Decision_Time"] for x in r["runs"]) for r in rows),
              "max_candidate_wall_seconds": max(x["wall_seconds"] for r in rows for x in r["runs"]),
              "scope": "No new solver or input-stream replay; independent arithmetic and frozen provenance checks. No dev/eval access."}
    p = HERE/"COLD_BUILD_INDEPENDENT_REVIEW_V1.json"
    assert not p.exists()
    p.write_text(json.dumps(output, indent=2)+"\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    with experiment_lock():
        main()
