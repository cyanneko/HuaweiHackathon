"""Metadata, parser, and repeat handling; importing this never runs a policy."""
from pathlib import Path
import hashlib,importlib.util,json,math,re,sys
O=Path(__file__).resolve().parent
ROOT=O.parents[1]

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending')
 tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(p)
def fixed(p,x):
 if Path(p).exists():assert load(p)==x,('frozen metadata changed',str(p))
 else:save(p,x)
def locate(value):
 p=Path(value);assert not p.is_absolute() and '\\' not in value and not re.match(r'^[A-Za-z]:',value)
 p=(ROOT/p).resolve();assert p.is_relative_to(ROOT.resolve());return p
def imported(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def parser(s):
 path=locate(s['parser_path']);assert sha(path)==s['parser_sha256'];sys.path.insert(0,str(path.parent))
 return imported('r74_frozen_official_parser',path)
def validate_release(r):
 assert all(r.get(k) is True for k in ['released','final_sources_frozen','review_passed','diagnostics_compute_released','all_compilation_released']),'Root release incomplete'
def skeleton(policy,tu):
 body=Path(policy).read_text(encoding='utf-8-sig');text=Path(tu).read_text(encoding='utf-8-sig')
 assert text.count(body)==1,'formal TU must contain the complete flattened scheduler exactly once'
 return hashlib.sha256(text.replace(body,'<SCHEDULER>').encode()).hexdigest()
def verify_sources(s):
 for m in s['methods']:
  policy=locate(m['source_path']);tu=locate(m['translation_unit_path'])
  assert sha(policy)==m['source_sha256'] and sha(tu)==m['translation_unit_sha256']
  assert not re.search(r'^\s*#\s*include\s*"',policy.read_text(encoding='utf-8-sig'),re.M),'flatten scheduler dependencies before freezing'
  assert skeleton(policy,tu)==s['framework_skeleton_sha256']
  assert m['instrumented'] is False and m['compile_flags']==['-std=c++14','-O2']
  assert m['framework_sha256']==s['methods'][0]['framework_sha256']
 for key in ['process_helper','parser']:
  assert sha(locate(s[key+'_path']))==s[key+'_sha256']
def index_grid(rows,methods,cases,repeats):
 by={}
 for r in rows:
  key=(r['method'],r['case_id'],r['repeat']);assert key not in by,'duplicate formal cell';by[key]=r
 assert set(by)=={(m,c,j) for m in methods for c in cases for j in range(repeats)},'incomplete/unknown method-case-repeat grid'
 return by
def mean_metrics(rows):
 assert rows
 if not all(r['valid'] for r in rows):return None
 keys=set(rows[0]['metrics']);assert all(set(r['metrics'])==keys for r in rows)
 return {k:math.fsum(r['metrics'][k] for r in rows)/len(rows) for k in keys}
