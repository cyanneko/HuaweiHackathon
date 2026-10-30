"""Fixed new-train collector, exact PROBE endpoints, separate physical ledgers."""
import argparse,hashlib,json,re,subprocess,sys,time
from pathlib import Path
from local_build import HERE,ROOT,compile_text,declarations,official
from make_policy import source,FEATURES,put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import replay,parse_output

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=48);args=parser.parse_args()
    dataset=json.loads((ROOT/'round8/TRAIN_MANIFEST.json').read_text())['cases'];ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl'
    plan={'cases':[{'id':r['spec']['id'],'group':r['spec']['group'],'input_sha256':r['input_sha256']} for r in dataset],
          'collector_mode':0,'max_states_per_flow':6,'intervention_probes':1024,'rollout_probes':4096,'continuations':[0,1],'features':FEATURES,
          'label':'min over continuations of (mode0 physical-mode1 physical)/mode0 interval cost; separate bytes and misses retained',
          'sampling':'uniform reservoir over full-PROBE miss pressure states after512 probes and effective sample>=32, >=4096 remaining probes',
          'teacher_sha256':sha(HERE/'teacher.cpp'),'policy_sha256':sha(HERE/'forced0.cpp'),'test_ledger_sha256':sha(ledger),'eval_queries':0,'dev_queries':0}
    put(HERE/'COLLECT_PLAN.json',json.dumps(plan,indent=2)+'\n')
    build=HERE/'build';build.mkdir(exist_ok=True);records=[];started=time.time()
    with experiment_lock():
        teacher=compile_text('teacher_v1',(HERE/'teacher.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',declarations()).replace('// POLICY_DEFINITION',source(force=0)))
        forced0=official('forced0_check',HERE/'forced0.cpp');forced1=None
        for j,r in enumerate(dataset[:args.limit]):
            path=ROOT/'build/round8/data/train'/(r['spec']['id']+'.txt');assert sha(path)==r['input_sha256']
            cache=build/(path.stem+'.json')
            if cache.exists():
                record=json.loads(cache.read_text());assert record['input_sha256']==sha(path) and record['teacher_sha256']==plan['teacher_sha256'] and record['policy_sha256']==plan['policy_sha256']
            else:
                proc=subprocess.run([str(teacher),str(path),'6'],check=True,capture_output=True,text=True,timeout=600)
                put(build/(path.stem+'.rows'),proc.stdout);put(build/(path.stem+'.log'),proc.stderr)
                rows=[]
                for line in proc.stdout.splitlines():
                    v=line.split();assert v[0]=='ROW' and len(v)==42,(len(v),line)
                    rows.append({'operation':int(v[1]),'start_probe':int(v[2]),'end_operation':int(v[3]),'features':list(map(float,v[4:22])),
                                 'branches':[{'read_bytes':int(v[22+5*i]),'write_bytes':int(v[23+5*i]),'misses':int(v[24+5*i]),'terminal_resident_bytes':int(v[25+5*i]),'continuation_start_operation':int(v[26+5*i])} for i in range(4)]})
                    assert len({b['continuation_start_operation'] for b in rows[-1]['branches']})==1
                result=subprocess.run([str(forced0),str(path)],capture_output=True,text=True,check=True,timeout=120)
                metrics=parse_output(result.stdout);sim=re.search(r'SIM ([\deE.+-]+) (\d+) (\d+) (\d+) (\d+)',proc.stderr);assert sim
                physical=metrics['Total_IO_Time']+r['spec']['penalty']*metrics['Miss_Count']
                assert abs(float(sim[1])-physical)<.05 and int(sim[2])==metrics['Hit_Count'] and int(sim[3])==metrics['Miss_Count']
                record={'id':r['spec']['id'],'group':r['spec']['group'],'family':r['spec']['family'],'seed':r['spec']['seed'],'input_sha256':sha(path),
                        'teacher_sha256':plan['teacher_sha256'],'policy_sha256':plan['policy_sha256'],'bandwidths':[r['spec']['read'],r['spec']['write']],'penalty_offline_only':r['spec']['penalty'],
                        'simulator_matches_official':True,'rows':rows,'collector_metrics':metrics,'collector_read_bytes':int(sim[4]),'collector_write_bytes':int(sim[5])}
                put(cache,json.dumps(record,indent=2)+'\n')
            records.append(record)
            (build/'status.json').write_text(json.dumps({'completed':len(records),'planned':len(dataset),'states':sum(len(x['rows']) for x in records),'seconds':time.time()-started})+'\n')
            print('collector',len(records),r['spec']['id'],'states',len(record['rows']),'seconds',round(time.time()-started,1),flush=True)
        assert sha(ledger)==plan['test_ledger_sha256']
    if len(records)==len(dataset):
        put(HERE/'COLLECT_RESULTS.json',json.dumps({'complete':True,'flows':len(records),'states':sum(len(x['rows']) for x in records),'groups':sorted({r['group'] for r in records}),'official_metric_checks':len(records),'test_ledger_unchanged':True,'dev_queries':0,'test_queries':0,'rows':records},indent=2)+'\n')
if __name__=='__main__':main()
