from pathlib import Path
import subprocess,time,json
r=Path(__file__).resolve().parent;root=r.parents[1];start=time.monotonic();records=[]
for effect in (1,2):
 cmd=['g++','-std=c++14','-O2','-DEFFECT='+str(effect),'-DTEST_INCLUDE="'+str(root/'tmp/r80_lazy_transfer/R80_next_hier_fast100/test_include.hpp')+'"',str(r/'test_effect.cpp'),'-o',str(r/('red'+str(effect)))];p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,p.stderr
 p=subprocess.run([str(r/('red'+str(effect)))],capture_output=True,text=True);(r/('red'+str(effect)+'.stdout')).write_text(p.stdout);(r/('red'+str(effect)+'.stderr')).write_text(p.stderr);assert p.returncode!=0;records.append(dict(effect=effect,returncode=p.returncode,stderr=p.stderr))
(r/'red_evidence.json').write_text(json.dumps(dict(seconds=time.monotonic()-start,records=records),indent=2));print((r/'red_evidence.json').read_text())
