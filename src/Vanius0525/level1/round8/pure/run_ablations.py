"""Fixed old-train sigma0/next0 ablations; case-level shared locking."""
import hashlib,json,statistics,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];F=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from build import build
from round6.prepare import DATA,manifest,put
from round7.cost_replay import replay,parse_output
from round7.metrics import physical,ratio
from workflow import experiment_lock

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    plan=json.loads((F/'ABLATION_PLAN.json').read_text());index={Path(r['path']).name:r for r in manifest()['cases']}
    baseline=json.loads((F/'PAIRED_CONFIDENCE_RESULTS.json').read_text())['rows'];best=json.loads((ROOT/'round7/BEST_RESULTS.json').read_text())['rows']
    out=ROOT/'build/round8_pure_ablations';out.mkdir(parents=True,exist_ok=True)
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';ledger_sha=sha(ledger);summary={}
    for name,fingerprint in plan['sources'].items():
        source=F/(name+'.cpp');assert sha(source)==fingerprint
        with experiment_lock():exe=build(source,'round8_pure_'+name,audit=True)
        rows=[]
        for b in baseline:
            rec=index[b['file']];assert rec['split']=='train';path=DATA/rec['path'];assert sha(path)==b['input_sha256']
            cache=out/(name+'_'+path.stem+'.json')
            if cache.exists():row=json.loads(cache.read_text())
            else:
                with experiment_lock():p=subprocess.run([str(exe),str(path)],check=True,capture_output=True,text=True,timeout=120)
                row={'file':path.name,'family':rec['family'],'source_sha256':sha(source),'input_sha256':sha(path),'audit':replay(path,p.stderr,p.stdout),'metrics':parse_output(p.stdout)}
                put(cache,(json.dumps(row,indent=2)+'\n').encode())
            assert row['source_sha256']==fingerprint and row['input_sha256']==sha(path)
            rows.append(row);(out/'status.json').write_text(json.dumps({'name':name,'done':len(rows),'total':len(baseline)})+'\n')
        stats={}
        for label,base in [('paired_confidence',baseline),('best',best)]:
            rs=[ratio(physical(r),physical(b)) for r,b in zip(rows,base)]
            stats[label]={'mean_ratio':statistics.mean(rs),'worst_ratio':max(rs),'wins_over_1pct':sum(x<.99 for x in rs),'regressions_over_1pct':sum(x>1.01 for x in rs),'same_audit_rows':sum(r['audit']==b['audit'] for r,b in zip(rows,base))}
        put(F/(name.upper()+'_RESULTS.json'),(json.dumps({'summary':stats,'rows':rows},indent=2)+'\n').encode());summary[name]=stats;print(name,json.dumps(stats),flush=True)
    assert sha(ledger)==ledger_sha
    put(F/'ABLATION_RESULTS.json',(json.dumps({'complete':True,'audited_runs':160,'test_queries':0,'dev_queries':0,'new48_queries':0,'summary':summary},indent=2)+'\n').encode())
if __name__=='__main__':main()
