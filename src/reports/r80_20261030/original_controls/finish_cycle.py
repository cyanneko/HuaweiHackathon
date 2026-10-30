from pathlib import Path
import json,hashlib,subprocess,time
r=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
save=lambda p,x:p.write_text(json.dumps(x,indent=2)+'\n')
old=json.loads((r/'producer.json').read_text());previous=json.loads((r/'test_summary.json').read_text())
save(r/'test_summary_lut.json',previous)
t=r/'test_transfer.cpp';s=t.read_text();s=s.replace('x.uniform_cycle_=true;x.recent_count_=0;','x.uniform_cycle_=true;x.analyzed_version_=x.graph_version_;x.recent_count_=0;');t.write_text(s)
start=time.monotonic();records=[]
def run(cmd,label,red=False):
 p=subprocess.run(cmd,cwd=r,capture_output=True,text=True,timeout=40-(time.monotonic()-start))
 (r/(label+'.stdout')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr)
 records.append(dict(name=label,returncode=p.returncode,argv=cmd,expected_failure=red))
 assert (p.returncode!=0 if red else p.returncode==0),(label,p.stdout,p.stderr)
run(['g++','-std=c++14','-O2','-DTEST_INCLUDE="R80_next_flat100/test_include.hpp"',str(t),'-o',str(r/'cycle_red')],'cycle_red_compile')
run([str(r/'cycle_red')],'cycle_red',True)
g=r/'generate.py';s=g.read_text();assert s.count('frequency_mode && o.phase==Phase::PROBE && !scan)')==1;s=s.replace('frequency_mode && o.phase==Phase::PROBE && !scan)','frequency_mode && o.phase==Phase::PROBE && !scan && !uniform_cycle_)');g.write_text(s)
run(['python3',str(g)],'cycle_generate')
m=json.loads((r/'producer.json').read_text())
for v in m['variants']:
 name=v['name'];d=r/name
 if name=='R80_penalty100':
  prev=next(x for x in old['variants'] if x['name']==name)
  assert v['source_sha256']==prev['source_sha256'] and v['translation_unit_sha256']==prev['translation_unit_sha256'] and sha(d/'scheduler')==prev['binary_sha256']
 else:
  run(['g++','-std=c++14','-O2',str(d/'main.cpp'),'-o',str(d/'scheduler')],name+'_cycle_compile')
  run(['g++','-std=c++14','-O2','-DTEST_INCLUDE="'+name+'/test_include.hpp"',str(t),'-o',str(d/'test')],name+'_cycle_test_compile')
  run([str(d/'test')],name+'_cycle_test')
 v['binary_sha256']=sha(d/'scheduler')
m['status']='READY';m['parent_sha256']=m['parent_source_sha256'];m['candidates']=m['variants'];save(r/'producer.json',m)
elapsed=time.monotonic()-start
summary=dict(status='PASS',seconds=previous['seconds']+elapsed,cycle_revision_seconds=elapsed,previous_build_seconds=previous['seconds'],records=previous['records']+records,performance_runs=0,training_runs=0)
save(r/'test_summary.json',summary)
save(r/'release.json',dict(status='RELEASED',ready=True,final=True,active_child_processes=0,seconds=elapsed,producer_sha256=sha(r/'producer.json'),test_summary_sha256=sha(r/'test_summary.json')))
print(json.dumps(summary))
