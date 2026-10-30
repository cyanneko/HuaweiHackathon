import csv, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
METHODS = ["Naive", "R75_dense_switch", "R80_next_hier_fast100", "R81_op256_cond2048", "Van_latest", "R85_fast_prior8", "R85_hier_anchor"]
SETS = {
    "dyna": (ROOT/"tmp/r85_full_eval/dyna/rows.json", ROOT/"tmp/r87_eval/dyna/rows.json"),
    "final": (ROOT/"tmp/r85_full_eval/final/rows.json", ROOT/"tmp/r87_eval/final/rows.json"),
}
METRICS = ["Total_IO_Time", "Hit_Count", "Miss_Count"]
def load(p): return json.loads(p.read_text(encoding="utf-8"))

details=[]; summary={}
for dataset,(oldp,newp) in SETS.items():
    old,new=load(oldp),load(newp)
    om={(r["case_id"],r["method"]):r for r in old}
    nm={(r["case_id"],r["method"]):r for r in new}
    cases=sorted({r["case_id"] for r in new})
    checked=identical=sha_ok=source_ok=0
    bad=[]
    for case in cases:
        for method in METHODS:
            a,b=om[(case,method)],nm[(case,method)]
            checked+=1
            same_sha=a["input_sha256"]==b["input_sha256"]
            same_src=a["source_sha256"]==b["source_sha256"]
            sha_ok+=same_sha; source_ok+=same_src
            vals={m:(a["metrics"][m],b["metrics"][m]) for m in METRICS}
            same=all(x==y for x,y in vals.values())
            identical+=same
            if not same_sha or not same_src or not same:
                bad.append({"case_id":case,"method":method,"input_sha_equal":same_sha,"source_sha_equal":same_src,"metrics":vals})
            details.append({"dataset":dataset,"case_id":case,"method":method,"input_sha_equal":same_sha,"source_sha_equal":same_src,**{f"old_{m}":vals[m][0] for m in METRICS},**{f"new_{m}":vals[m][1] for m in METRICS},"metrics_equal":same})
    summary[dataset]={"cases":len(cases),"controls":len(METHODS),"comparisons":checked,"input_sha_equal":sha_ok,"source_sha_equal":source_ok,"IO_hit_miss_exact_equal":identical,"pass":not bad,"mismatches":bad}
(OUT/"control_comparison.json").write_text(json.dumps({"status":"PASS" if all(x["pass"] for x in summary.values()) else "FAIL","methods":METHODS,"datasets":summary},indent=2),encoding="utf-8")
with (OUT/"control_comparison.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=details[0].keys());w.writeheader();w.writerows(details)
print(json.dumps({k:{x:v for x,v in val.items() if x!="mismatches"} for k,val in summary.items()},indent=2))
