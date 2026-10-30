from pathlib import Path
import sys,json,subprocess,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import replay
from workflow import experiment_lock
with experiment_lock():
    records=json.loads((ROOT/'round4/CALLBACK_CONTEXT_FAST_VARIANTS.json').read_text());rows={};start=time.time()
    cases=[]
    for folder in ['val','round4-fresh','round4-ood']:cases+=sorted((ROOT/'build/data'/folder).glob('*.txt'))
    for name,d in records.items():
        old=build(ROOT/'round4'/(d['parent']+'.cpp'),'r4_ctx_old_'+name,audit=True);new=build(ROOT/'round4'/(name+'.cpp'),'r4_ctx_fast_'+name,audit=True)
        for i,case in enumerate(cases):
            a=subprocess.run([str(old),str(case)],capture_output=True,text=True,check=True,timeout=60)
            b=subprocess.run([str(new),str(case)],capture_output=True,text=True,check=True,timeout=60)
            assert a.stderr==b.stderr,(name,case,'trace mismatch');assert replay(case,a.stderr,a.stdout)==replay(case,b.stderr,b.stdout)
            if i%32==0:print(name,i+1,len(cases),flush=True)
        rows[name]={'cases':len(cases),'action_trace_byte_equality':True,'independent_replay_equality':True,'parent_sha256':d['parent_sha256'],'source_sha256':d['sha256']}
    (ROOT/'round4/CALLBACK_CONTEXT_FAST_EQUIVALENCE.json').write_text(json.dumps({'candidates':rows,'seconds':time.time()-start,'scope':'actual complete trajectories; cold/cycle shortcuts rely on saved valid protocol, not arbitrary mutations of abstract states'},indent=2)+'\n')
