"""Compile and time the public engine without changing its execution or timer."""
from pathlib import Path
import argparse,collections,hashlib,json,math,os,platform,re,statistics,subprocess
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def resolve_file(value,manifest):
    s=str(value).replace('\\','/')
    if os.name=='nt' and s.startswith('/mnt/'):s=s[5].upper()+':'+s[6:]
    elif os.name!='nt' and len(s)>1 and s[1]==':':s='/mnt/'+s[0].lower()+s[2:]
    p=Path(s)
    for q in [p,manifest.parent/p,PROJECT/p,ROOT/p]:
        if q.is_file():return q.resolve()
    raise FileNotFoundError(value)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--repeats',type=int,default=3);ap.add_argument('--modes',default='-1,4,8,9');ap.add_argument('--split');ap.add_argument('--cxx',default='g++')
    a=ap.parse_args();assert a.repeats>0;modes=[int(x) for x in a.modes.split(',')];assert set(modes)<=set(range(10))|{-1}
    manifest=a.manifest.resolve();cases=json.loads(manifest.read_text('utf8'));cases=[r for r in cases if not a.split or r.get('split')==a.split];assert cases
    for r in cases:r['resolved']=resolve_file(r['file'],manifest);assert sha(r['resolved'])==r['sha256']
    reference=ROOT.parent/'holistic_20261026/reference_current.cpp';ref=reference.read_text('utf8')
    marker='/* ===== 执行引擎 ===== */';ctor='std::make_unique<NaiveSpillScheduler>()';assert ref.count(marker)==ref.count(ctor)==1
    ref=ref.replace(ctor,'makeScheduler(argc>2?std::stoi(argv[2]):-1)',1)
    neural=ROOT.parent/'MySpillScheduler_neural.cpp';old=ROOT.parent/'MySpillScheduler_final.cpp'
    include='#include '+json.dumps(neural.as_posix())+'\n#define MySpillScheduler OriginalScheduler\n#include '+json.dumps(old.as_posix())+'\n#undef MySpillScheduler\n'
    include+='static std::unique_ptr<SpillScheduler> makeScheduler(int m){if(m==8)return std::make_unique<OriginalScheduler>();if(m==9)return std::make_unique<NaiveSpillScheduler>();return std::make_unique<MySpillScheduler>(m);}\n'
    build=ROOT/'build';build.mkdir(exist_ok=True);cpp=build/'engine.cpp';binary=build/('engine.exe' if os.name=='nt' else 'engine')
    cpp.write_text(ref.replace(marker,include+marker,1),encoding='utf8')
    subprocess.run([a.cxx,'-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors',str(cpp),'-o',str(binary)],check=True)
    output=a.output.resolve();output.parent.mkdir(parents=True,exist_ok=True);rows=[]
    with output.with_suffix('.jsonl').open('w',encoding='utf8') as f:
        for rep in range(a.repeats):
            for i,r in enumerate(cases):
                for mode in (modes if (i+rep)%2==0 else modes[::-1]):
                    p=subprocess.run([str(binary),str(r['resolved']),str(mode)],capture_output=True,text=True,check=True,timeout=180)
                    v={k:float(x) for k,x in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([\d.eE+-]+)',p.stdout)}
                    assert len(v)==5 and abs(v['Total_Score']-v['Total_IO_Time']-v['Total_Decision_Time']-r['penalty']*v['Miss_Count'])<.05
                    row=dict(case=r['sha256'],mode=mode,repeat=rep,**v);rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
                if (i+1)%32==0:print(rep+1,i+1,flush=True)
    grouped=collections.defaultdict(list)
    for r in rows:grouped[r['case'],r['mode']].append(r)
    med={k:{n:statistics.median(v[n] for v in vs) for n in ['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']} for k,vs in grouped.items()}
    summary={}
    if 8 in modes:
        for mode in modes:
            pairs=[(med[c,mode],med[c,8]) for c,m in med if m==mode and med[c,8]['Total_Score']>0]
            ratios=[x['Total_Score']/y['Total_Score'] for x,y in pairs]
            if ratios:summary[str(mode)]=dict(cases=len(pairs),geometric_vs_previous=math.exp(statistics.mean(map(math.log,ratios))),worst=max(ratios),cpu=sum(x['Total_Decision_Time'] for x,y in pairs))
    result=dict(source_sha256=sha(neural),old_source_sha256=sha(old),reference_sha256=sha(reference),manifest_sha256=sha(manifest),host=platform.platform(),repeats=a.repeats,input_cases=len(cases),summary=summary,medians=[dict(case=c,mode=m,**v) for (c,m),v in med.items()])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
