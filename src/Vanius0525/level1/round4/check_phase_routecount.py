from pathlib import Path
import sys,json,subprocess,hashlib,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import replay
from workflow import experiment_lock
OUT=ROOT/'build/round4/phase_routecount_checks';OUT.mkdir(parents=True,exist_ok=True)
def main():
    start=time.time();records=json.loads((ROOT/'round4/PHASE_ROUTECOUNT_VARIANTS.json').read_text());checks={}
    cases=[]
    for folder in ['val','round4-fresh','round4-ood']:cases+=sorted((ROOT/'build/data'/folder).glob('*.txt'))
    for name,d in records.items():
        old=build(ROOT/d['parent'],'r4_route_old_'+name,audit=True);new=build(ROOT/'round4'/(name+'.cpp'),'r4_route_new_'+name,audit=True)
        for i,case in enumerate(cases):
            a=subprocess.run([str(old),str(case)],capture_output=True,text=True,check=True,timeout=60)
            b=subprocess.run([str(new),str(case)],capture_output=True,text=True,check=True,timeout=60)
            assert a.stderr==b.stderr,(name,case.name,'action trace mismatch')
            assert replay(case,a.stderr,a.stdout)==replay(case,b.stderr,b.stdout)
            if i%32==0:print(name,i+1,len(cases),flush=True)
        checks[name]={'cases':len(cases),'action_trace_byte_equality':True,'independent_replay_equality':True,'parent_sha256':d['parent_sha256'],'source_sha256':d['sha256']}
    (ROOT/'round4/PHASE_ROUTECOUNT_EQUIVALENCE.json').write_text(json.dumps({'candidates':checks,'seconds':time.time()-start,'scope':'trajectory tests plus graph necessary-condition reasoning; no full formal verification'},indent=2)+'\n')
if __name__=='__main__':
    with experiment_lock():main()
