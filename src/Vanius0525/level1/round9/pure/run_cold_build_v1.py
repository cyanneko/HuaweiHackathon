"""One frozen candidate, 60 audits + 180 timed runs; all references reused."""
import json
import math
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from build import build
from workflow import experiment_lock
from round9.cost_replay_precise import replay, parse_output
from prepare_cold_build_v1 import sha, save
from cold_build_prefix_v1 import compare
from summarize_cold_build_v1 import summarize

OUT = ROOT / "build/round9_pure_cold_build_v1"


def execute(exe, path, timeout, target):
    started = time.perf_counter()
    try:
        proc = subprocess.run([str(exe), str(path)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        for suffix, data in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            (target.parent/(target.name+"."+suffix)).write_bytes(data.encode() if isinstance(data, str) else data or b"")
        (target.parent/(target.name+".timeout.json")).write_text(json.dumps({"timeout_seconds": timeout})+"\n")
        raise
    wall = time.perf_counter()-started
    (target.parent/(target.name+".stdout")).write_text(proc.stdout)
    (target.parent/(target.name+".stderr")).write_text(proc.stderr)
    assert proc.returncode == 0, (exe.name, path.name, proc.returncode, proc.stderr[:1000])
    metrics = parse_output(proc.stdout)
    assert all(math.isfinite(v) and v >= 0 for v in metrics.values())
    return proc, metrics, wall


def main():
    planpath = HERE / "COLD_BUILD_PLAN_V1.json"
    freezepath = HERE / "COLD_BUILD_BUILD_FREEZE_V1.json"
    plan = json.loads(planpath.read_text()); freeze = json.loads(freezepath.read_text())
    freeze_sha = sha(freezepath)
    for name, expected in freeze["files"].items():
        assert sha(HERE/name) == expected, name
    for name, expected in freeze["previous_closed_freezes"].items():
        assert sha(HERE/name) == expected, name
    assert sha(ROOT/"build.py") == freeze["build_tool_sha256"]
    assert sha(ROOT/"round9/cost_replay_precise.py") == freeze["independent_replay_sha256"]
    baseline_path = ROOT/"round9/PROXY100_BASELINE_RESULTS_V3.json"
    lockpath = ROOT/"round9/V21_DATASET_LOCK.json"
    assert sha(baseline_path) == plan["baseline_results_sha256"]
    assert sha(lockpath) == plan["dataset_lock_sha256"]
    baseline = {r["case"]: r for r in json.loads(baseline_path.read_text())["cases"]}
    lock = json.loads(lockpath.read_text())
    assert [c["case"] for c in plan["cases"]] == lock["pilot_train"]
    assert set(baseline) <= set(lock["train"])
    data = ROOT/"build/round9/dataset_snapshots"/lock["snapshot_revision"]/"final_dataset"
    source = ROOT/plan["candidate"]
    assert sha(source) == plan["candidate_sha256"]
    assert sha(ROOT/plan["parent"]) == plan["parent_sha256"]
    OUT.mkdir(parents=True, exist_ok=True)
    records = []; exe = audited = None

    def status(state, **extra):
        (OUT/"status.json").write_text(json.dumps({"state": state, "completed_cases": len(records),
            "total_cases": 60, "build_freeze_sha256": freeze_sha, **extra}, indent=2)+"\n")

    try:
        for c in plan["cases"]:
            path = data/c["case"]
            canonical = OUT/(path.stem+".json")
            status("waiting_for_shared_lock", current_case=c["case"])
            with experiment_lock():
                assert sha(path) == c["input_sha256"]
                assert sha(source) == plan["candidate_sha256"]
                for field in ("reference_record", "reference_stdout", "reference_stderr"):
                    assert sha(ROOT/c[field+"_path"]) == c[field+"_sha256"]
                ref = baseline[c["case"]]
                assert ref["source_sha256"]["paired100"] == plan["parent_sha256"]
                if canonical.exists():
                    row = json.loads(canonical.read_text())
                    assert row["build_freeze_sha256"] == freeze_sha
                    assert row["input_sha256"] == c["input_sha256"] and row["all_checks_passed"]
                else:
                    if exe is None:
                        status("compiling", current_case=c["case"])
                        stem = "round9_pure_cold_build_v1_"+plan["candidate_sha256"][:12]
                        exe = build(source, stem); audited = build(source, stem, audit=True)
                    attempt = 0
                    work = OUT/(path.stem+"_attempt0")
                    while work.exists():
                        attempt += 1; work = OUT/(path.stem+"_attempt"+str(attempt))
                    work.mkdir()
                    with path.open() as f:
                        k, p, m, w, r, penalty = map(int, f.readline().split())
                    assert penalty == ref["penalty"]
                    status("auditing", current_case=c["case"], attempt=attempt)
                    proc, metrics, wall = execute(audited, path, plan["audit_timeout_seconds"], work/"candidate_audit")
                    audit = replay(path, proc.stderr, proc.stdout)
                    audit["instrumented_wall_seconds"] = wall
                    prefix = compare(path, (ROOT/c["reference_stderr_path"]).read_text(), proc.stderr)
                    if r < w:
                        assert prefix["full_trace_equal"], (c["case"], "R<W changed")
                    row = {"case": c["case"], "seed": c["seed"], "family": c["family"],
                           "input_sha256": c["input_sha256"], "source_sha256": plan["candidate_sha256"],
                           "build_freeze_sha256": freeze_sha, "read_ge_write": r >= w,
                           "penalty": penalty, "audit": audit, "prefix_comparison": prefix,
                           "runs": [], "attempt": attempt, "all_checks_passed": False}
                    status("timing", current_case=c["case"], attempt=attempt)
                    for rep in range(plan["timed_repeats"]):
                        _, v, elapsed = execute(exe, path, plan["timed_timeout_seconds"], work/("candidate_repeat"+str(rep)))
                        assert v["Hit_Count"] == audit["hits"] and v["Miss_Count"] == audit["misses"]
                        assert abs(v["Total_IO_Time"]-audit["io"]) < .011
                        assert abs(v["Total_Score"]-(v["Total_IO_Time"]+penalty*v["Miss_Count"]+v["Total_Decision_Time"])) < .021
                        v["wall_seconds"] = elapsed; row["runs"].append(v)
                    row["all_checks_passed"] = True
                    save(canonical, row)
            records.append(row)
            status("running")
            print("complete", len(records), "/ 60", c["case"], flush=True)
        summary = summarize(records, baseline, plan["gate"])
        assert summary["groups"]["read_lt_write"]["cases"] == 34
        assert summary["groups"]["read_lt_write"]["full_trace_equal"] == 34
        save(HERE/"COLD_BUILD_RESULTS_V1.json", {"complete": True, "build_freeze_sha256": freeze_sha,
            "new_audited_runs": 60, "new_timed_runs": 180, "new_reference_runs": 0,
            "dev_accesses": 0, "eval_accesses": 0, "records": records})
        save(HERE/"COLD_BUILD_SUMMARY_V1.json", summary)
        status("complete", eligible_for_root_dev_review=summary["eligible_for_root_dev_review"])
        print(json.dumps({"all": summary["all"], "gate_checks": summary["gate_checks"],
                          "eligible_for_root_dev_review": summary["eligible_for_root_dev_review"]}, indent=2), flush=True)
    except BaseException as exc:
        status("failed_or_interrupted", error=type(exc).__name__+": "+str(exc))
        raise


if __name__ == "__main__":
    main()
