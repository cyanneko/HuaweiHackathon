import csv,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
COMPS=["R85_fast_prior8","R85_hier_anchor","R81_op256_cond2048","Van_latest","R75_dense_switch"]
def q(v,p):
    a=sorted(v); return a[max(0,math.ceil(p*len(a))-1)]
out={}; rows_out=[]
for ds in ("dyna","final"):
    rev=json.loads((ROOT/f"tmp/r87_eval/root_review/{ds}/review.json").read_text())
    g={x["method"]:x for x in rev["groups"] if x["group"]=="all"}
    pc=list(csv.DictReader((ROOT/f"tmp/r87_eval/root_review/{ds}/per_case.csv").open(encoding="utf-8-sig")))
    by={m:[] for m in g}
    for r in pc: by[r["method"]].append(r)
    ref=g["R87_fixedshare_op"]
    out[ds]={"cases":ref["cases"],"score":{m:g[m]["score"] for m in g},"raw_points":{m:g[m]["raw_points"] for m in g},"D_mean_us":{m:g[m]["D_mean_us"] for m in g},"R87_vs":{}}
    for m in COMPS:
        cr=[float(r[f"cost_ratio_{m}"]) for r in by["R87_fixedshare_op"]]
        pr=[float(r[f"physical_ratio_{m}"]) for r in by["R87_fixedshare_op"]]
        d87=sum(float(r["D"]) for r in by["R87_fixedshare_op"]); dref=sum(float(r["D"]) for r in by[m])
        x={"score_delta":ref["score"]-g[m]["score"],"raw_delta":ref["raw_points"]-g[m]["raw_points"],"cost_ratio_mean":sum(cr)/len(cr),"cost_ratio_p50":q(cr,.5),"cost_ratio_p90":q(cr,.9),"cost_ratio_worst":max(cr),"physical_ratio_mean":sum(pr)/len(pr),"D_ratio_total":d87/dref if dref else None,"D_R87_mean_us":ref["D_mean_us"],"D_reference_mean_us":g[m]["D_mean_us"],"wins_ties_losses":[sum(v<1-1e-12 for v in cr),sum(abs(v-1)<=1e-12 for v in cr),sum(v>1+1e-12 for v in cr)]}
        out[ds]["R87_vs"][m]=x
        rows_out.append({"dataset":ds,"method":"R87_fixedshare_op","reference":m,**x})
    naive=[float(r["cost_ratio_Naive"]) for r in by["R87_fixedshare_op"]]
    out[ds]["R87_vs_Naive"]={"mean":sum(naive)/len(naive),"p50":q(naive,.5),"p90":q(naive,.9),"worst":max(naive),"worse_than_naive":sum(x>1+1e-12 for x in naive)}
(OUT/"performance_summary.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
with (OUT/"performance_comparisons.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=rows_out[0].keys());w.writeheader();w.writerows(rows_out)
print(json.dumps(out,indent=2))
