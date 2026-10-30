"""Freeze one exact cold-start gate and the existing 60 successful references."""
import difflib
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock
from round9.cost_replay_precise import parse_output


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def put(path, data):
    if path.exists():
        assert path.read_bytes() == data, path
    else:
        path.write_bytes(data)


def save(path, value):
    put(path, (json.dumps(value, indent=2)+"\n").encode())


def main():
    parent = ROOT / "round9/candidates/paired_penalty100.cpp"
    assert sha(parent) == "3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15"
    raw = parent.read_bytes()
    old = b"if ((evidence || s.read_bandwidth>=s.write_bandwidth) && !victims_.empty()) {"
    new = b"if (evidence && !victims_.empty()) {"
    assert raw.count(old) == 1
    candidate = HERE / "cold_build_after_probe100_v1.cpp"
    put(candidate, raw.replace(old, new))
    assert candidate.read_bytes().replace(new, old) == raw
    diff = "".join(difflib.unified_diff(raw.decode().splitlines(True), candidate.read_text().splitlines(True),
                                     fromfile="paired_penalty100.cpp", tofile=candidate.name))
    put(HERE / "COLD_BUILD_SOURCE_DIFF_V1.patch", diff.encode())
    lockpath = ROOT / "round9/V21_DATASET_LOCK.json"
    resultpath = ROOT / "round9/PROXY100_BASELINE_RESULTS_V3.json"
    result = json.loads(resultpath.read_text()); lock = json.loads(lockpath.read_text())
    assert result["complete"]
    assert [c["case"] for c in result["cases"]] == lock["pilot_train"]
    assert len(result["cases"]) == 60
    assert set(lock["pilot_train"]) <= set(lock["train"])
    refs = ROOT / "build/round9/proxy100_baseline_v2"
    records = []
    for c in result["cases"]:
        stem = Path(c["case"]).stem
        canonical = refs / (stem+".json")
        assert json.loads(canonical.read_text()) == c
        valid = []
        for d in sorted(refs.glob(stem+"_attempt*")):
            out, err = d / "paired100_audit.stdout", d / "paired100_audit.stderr"
            if not out.exists() or not err.exists():
                continue
            v = parse_output(out.read_text()); a = c["audit"]["paired100"]
            if v["Hit_Count"] == a["hits"] and v["Miss_Count"] == a["misses"] and abs(v["Total_IO_Time"]-a["io"]) < .011:
                valid.append((out, err))
        assert len(valid) == 1, (stem, valid)
        out, err = valid[0]
        records.append({"case": c["case"], "seed": c["seed"], "family": c["family"],
                        "input_sha256": c["input_sha256"],
                        "reference_record_path": str(canonical.relative_to(ROOT)),
                        "reference_record_sha256": sha(canonical),
                        "reference_stdout_path": str(out.relative_to(ROOT)), "reference_stdout_sha256": sha(out),
                        "reference_stderr_path": str(err.relative_to(ROOT)), "reference_stderr_sha256": sha(err)})
    plan = {"candidate": str(candidate.relative_to(ROOT)), "candidate_sha256": sha(candidate),
            "parent": str(parent.relative_to(ROOT)), "parent_sha256": sha(parent),
            "baseline_results_sha256": sha(resultpath), "dataset_lock_sha256": sha(lockpath),
            "timed_repeats": 3, "audit_timeout_seconds": 240, "timed_timeout_seconds": 60,
            "gate": {"mean_physical_ratio_max": .995, "worst_physical_ratio_max": 1.02,
                     "mean_decision_inclusive_score_min_delta": 0.0, "all_legal_and_equivalence": True},
            "scope": "One cold q0 gate only; 60 existing train, no new baseline solver, no old1, no dev/eval.",
            "cases": records}
    save(HERE / "COLD_BUILD_PLAN_V1.json", plan)
    names = ["COLD_BUILD_CONTRACT_V1.md", "COLD_BUILD_PLAN_V1.json", "COLD_BUILD_SOURCE_DIFF_V1.patch",
             candidate.name, "prepare_cold_build_v1.py", "run_cold_build_v1.py", "cold_build_prefix_v1.py",
             "summarize_cold_build_v1.py"]
    previous = {}
    for name in ("DIAGNOSTIC_FREEZE_V2.json", "CORE_SHADOW_FINAL_FREEZE_V1.json", "BOUNDED_HIT_FINAL_FREEZE_V1.json",
                 "RETURN_RISK_FINAL_FREEZE_V1.json", "RETURN_RISK_SCALE_FINAL_FREEZE_V1.json"):
        p = HERE / name
        if p.exists():
            previous[name] = sha(p)
            x = json.loads(p.read_text())
            if "files" in x and isinstance(x["files"], dict):
                for file, expected in x["files"].items():
                    assert sha(HERE / file) == expected, file
    save(HERE / "COLD_BUILD_BUILD_FREEZE_V1.json", {
        "status": "frozen before candidate solver", "files": {n: sha(HERE/n) for n in names},
        "build_tool_sha256": sha(ROOT/"build.py"),
        "independent_replay_sha256": sha(ROOT/"round9/cost_replay_precise.py"),
        "previous_closed_freezes": previous})
    print("candidate", sha(candidate), "freeze", sha(HERE/"COLD_BUILD_BUILD_FREEZE_V1.json"), "references", len(records))


if __name__ == "__main__":
    with experiment_lock():
        main()
