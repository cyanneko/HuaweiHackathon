"""Frozen aggregation and pass/fail rules for the single cold-BUILD candidate."""
import statistics as st

COMPONENTS = ("build_write_us", "probe_write_us", "probe_read_us", "miss_us")


def physical(audit):
    return sum(audit["costs"][key] for key in COMPONENTS)


def score(value, base):
    return max(0., min(10., 10.*(1.-value/base))) if value and base else 0.


def summarize(records, references, gate):
    comparisons = []
    for row in records:
        ref = references[row["case"]]
        a, b = row["audit"], ref["audit"]["paired100"]
        ratio = physical(a)/physical(b) if physical(b) else 1.0
        if not physical(b):
            assert physical(a) == 0
        old_score = st.mean(score(ref["runs"]["paired100"][j]["Total_Score"],
                                  ref["runs"]["naive"][j]["Total_Score"]) for j in range(3))
        new_score = st.mean(score(row["runs"][j]["Total_Score"],
                                  ref["runs"]["naive"][j]["Total_Score"]) for j in range(3))
        comparisons.append({"case": row["case"], "seed": row["seed"], "family": row["family"],
                            "physical_ratio": ratio, "candidate_score": new_score, "reference_score": old_score,
                            "score_delta": new_score-old_score,
                            "component_delta_us": {k: a["costs"][k]-b["costs"][k] for k in COMPONENTS},
                            "miss_delta": a["misses"]-b["misses"], "read_ge_write": row["read_ge_write"],
                            "full_trace_equal": row["prefix_comparison"]["full_trace_equal"],
                            "q0_prefix_equal": row["prefix_comparison"]["q0_prefix_equal"],
                            "resident_symmetric_difference_bytes": row["prefix_comparison"]["resident_symmetric_difference_bytes"]})

    def group(rows):
        return {"cases": len(rows), "mean_physical_ratio": st.mean(x["physical_ratio"] for x in rows),
                "worst_physical_ratio": max(x["physical_ratio"] for x in rows),
                "mean_candidate_score": st.mean(x["candidate_score"] for x in rows),
                "mean_reference_score": st.mean(x["reference_score"] for x in rows),
                "mean_score_delta": st.mean(x["score_delta"] for x in rows),
                "physical_improved": sum(x["physical_ratio"] < 1 for x in rows),
                "physical_equal": sum(x["physical_ratio"] == 1 for x in rows),
                "physical_worse": sum(x["physical_ratio"] > 1 for x in rows),
                "regressions_gt_1pct": sum(x["physical_ratio"] > 1.01 for x in rows),
                "regressions_gt_2pct": sum(x["physical_ratio"] > 1.02 for x in rows),
                "q0_prefix_equal": sum(x["q0_prefix_equal"] for x in rows),
                "full_trace_equal": sum(x["full_trace_equal"] for x in rows),
                "component_delta_us": {k: sum(x["component_delta_us"][k] for x in rows) for k in COMPONENTS}}

    overall = group(comparisons)
    checks = {"mean_physical_ratio": overall["mean_physical_ratio"] <= gate["mean_physical_ratio_max"],
              "worst_physical_ratio": overall["worst_physical_ratio"] <= gate["worst_physical_ratio_max"],
              "decision_inclusive_score": overall["mean_score_delta"] >= gate["mean_decision_inclusive_score_min_delta"],
              "all_audit_and_trace_checks": all(r["all_checks_passed"] for r in records)}
    return {"complete": len(records) == 60, "all": overall, "gate_checks": checks,
            "eligible_for_root_dev_review": len(records) == 60 and all(checks.values()),
            "groups": {"read_ge_write": group([r for r in comparisons if r["read_ge_write"]]),
                       "read_lt_write": group([r for r in comparisons if not r["read_ge_write"]])},
            "families": {f: group([r for r in comparisons if r["family"] == f]) for f in sorted({r["family"] for r in comparisons})},
            "cases": comparisons,
            "timing_limit": "Candidate three repeats and reused paired100/Naive repeats were measured in different shared-lock windows; no whole-host or contemporaneous timing claim.",
            "promotion_limit": "Only the predefined train gate; no dev/eval accessed and no automatic promotion."}
