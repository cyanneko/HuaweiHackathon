"""Bitwise network checks and whole-trajectory action equivalence on exposed sets."""
from pathlib import Path
import sys,json,re,subprocess,hashlib,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import replay
from workflow import experiment_lock
OUT=ROOT/'build/round4/fast_checks';OUT.mkdir(parents=True,exist_ok=True)

def main():
    start=time.time();records=json.loads((ROOT/'round4/FAST_VARIANTS.json').read_text());checks={}
    # Extract the two standalone neural definitions and compare double output bits.
    a=(ROOT/'MySpillSchedulerAI.cpp').read_text();b=(ROOT/'round4/ai_fast.cpp').read_text()
    def nn(s):return s[s.index('    double neural('):s.index('    void release(')]
    harness='''#include <algorithm>\n#include <cstdint>\n#include <cstring>\n#include <random>\n#include <iostream>\nstruct Old { OLD };\nstruct New { NEW };\nint main(){Old a;New b;std::mt19937 gen(403000);std::uniform_real_distribution<float> u(0,1);\nfor(int n=0;n<1000000;++n){float f[12];for(int i=0;i<12;++i)f[i]=n<4096?float((n>>i)&1):u(gen);double x=a.neural(f),y=b.neural(f);if(std::memcmp(&x,&y,sizeof(double))){std::cerr<<n<<" mismatch\\n";return 1;}}std::cout<<"1000000 bitwise predictions passed\\n";}\n'''.replace('OLD',nn(a)).replace('NEW',nn(b))
    src=OUT/'network_equal.cpp';src.write_text(harness);exe=OUT/'network_equal'
    subprocess.run(['g++','-std=c++14','-O2',str(src),'-o',str(exe)],check=True)
    message=subprocess.check_output([str(exe)],text=True);print(message,flush=True)
    # Full action strings include order; metrics exclude instrumented decision time.
    cases=sorted((ROOT/'build/data/val').glob('*.txt'))+sorted((ROOT/'build/data/round4-ood').glob('*.txt'))
    for name,d in records.items():
        old=build(ROOT/d['parent'],'r4_equal_old_'+name,audit=True);new=build(ROOT/'round4'/(name+'.cpp'),'r4_equal_new_'+name,audit=True)
        for i,case in enumerate(cases):
            ra=subprocess.run([str(old),str(case)],capture_output=True,text=True,check=True,timeout=60)
            rb=subprocess.run([str(new),str(case)],capture_output=True,text=True,check=True,timeout=60)
            assert ra.stderr==rb.stderr,(name,case,'action trace mismatch')
            va=replay(case,ra.stderr,ra.stdout);vb=replay(case,rb.stderr,rb.stdout);assert va==vb
            if i%32==0:print(name,i+1,len(cases),flush=True)
        checks[name]={'cases':len(cases),'action_trace_byte_equality':True,'independent_replay_equality':True,'parent_sha256':d['parent_sha256'],'source_sha256':d['sha256']}
    (ROOT/'round4/FAST_EQUIVALENCE.json').write_text(json.dumps({'network_bitwise_inputs':1000000,'network_seed':403000,'feature_domain':'[0,1]^12 including all 4096 corners','candidates':checks,'seconds':time.time()-start,'scope':'tested prediction/action equivalence; not a proof for all possible floating-point platforms'},indent=2)+'\n')
if __name__=='__main__':
    with experiment_lock():main()
