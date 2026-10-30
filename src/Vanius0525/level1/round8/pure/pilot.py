"""Train-only pilot; independent replay, source/data locks, global experiment lock."""
import hashlib,json,statistics,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from build import build
from round6.prepare import DATA,manifest,put
from round7.cost_replay import replay,parse_output
from round7.metrics import physical,ratio
from workflow import experiment_lock

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    baseline=json.loads((ROOT/'round7/BEST_RESULTS.json').read_text())['rows']
    fixed=json.loads((ROOT/'round7/PILOT_DECAY64_FIXED_POOL_V3.json').read_text())['rows']
    dynamic=json.loads((ROOT/'round7/PILOT_DECAY64_V3.json').read_text())['rows']
    index={Path(x['path']).name:x for x in manifest()['cases']}
    sources={n:FOLDER/(n+'.cpp') for n in ['paired_confidence','paired_source_guard']}
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';ledger_sha=sha(ledger)
    plan={'sources':{n:sha(p) for n,p in sources.items()},'cases':[{'file':b['file'],'sha256':b['input_sha256']} for b in baseline], 'test_ledger_sha256':ledger_sha,'test_queries':0,'dev_queries':0}
    put(FOLDER/'PILOT_PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
    out=ROOT/'build/round8_pure_pilot';out.mkdir(parents=True,exist_ok=True)
    summaries={}
    with experiment_lock():
        for name,source in sources.items():
            exe=build(source,'round8_pure_'+name,audit=True);rows=[]
            for b in baseline:
                rec=index[b['file']];assert rec['split']=='train';path=DATA/rec['path'];assert sha(path)==b['input_sha256']
                cache=out/(name+'_'+path.stem+'.json')
                if cache.exists():row=json.loads(cache.read_text())
                else:
                    p=subprocess.run([str(exe),str(path)],check=True,capture_output=True,text=True,timeout=120)
                    row={'file':path.name,'family':rec['family'],'source_sha256':sha(source),'input_sha256':sha(path),'audit':replay(path,p.stderr,p.stdout),'metrics':parse_output(p.stdout)}
                    put(cache,(json.dumps(row,indent=2)+'\n').encode())
                assert row['source_sha256']==sha(source) and row['input_sha256']==sha(path)
                rows.append(row);(out/'status.json').write_text(json.dumps({'name':name,'done':len(rows),'total':len(baseline)})+'\n')
            results={}
            for label,base in [('best',baseline),('fixed',fixed),('dynamic',dynamic)]:
                rs=[ratio(physical(r),physical(b)) for r,b in zip(rows,base)]
                results[label]={'mean_ratio':statistics.mean(rs),'worst_ratio':max(rs),'wins_over_1pct':sum(x<.99 for x in rs),'regressions_over_1pct':sum(x>1.01 for x in rs),'total_ratio':ratio(sum(map(physical,rows)),sum(map(physical,base)))}
            results['families']={family:statistics.mean(ratio(physical(r),physical(b)) for r,b in zip(rows,baseline) if r['family']==family) for family in sorted({r['family'] for r in rows})}
            put(FOLDER/(name.upper()+'_RESULTS.json'),(json.dumps({'summary':results,'rows':rows},indent=2)+'\n').encode());summaries[name]=results;print(name,json.dumps(results),flush=True)
        assert sha(ledger)==ledger_sha
    put(FOLDER/'PILOT_RESULTS.json',(json.dumps({'complete':True,'cases':len(baseline),'audited_runs':len(baseline)*len(sources),'test_queries':0,'dev_queries':0,'summary':summaries},indent=2)+'\n').encode())
if __name__=='__main__':main()
