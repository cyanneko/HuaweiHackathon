"""Run under existing WSL Ubuntu: actual public engine, C++14, same compiler.
Old sources are immutable snapshots. No timing is subtracted from Total_Score.
"""
import collections,hashlib,json,math,re,statistics,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def linux(p):
    p=str(p).replace('\\','/')
    return '/mnt/'+p[0].lower()+p[2:] if len(p)>2 and p[1]==':' else p
def fast_old():
    s=(ROOT/'old_balanced.cpp').read_text('utf8')
    start=s.index('        std::sort(c.begin()')
    stop=s.index('        int take=0;',start)
    block='''        auto cmp=[](const Victim& a,const Victim& b){
            if(a.key!=b.key)return a.key<b.key;
            if(a.bytes!=b.bytes)return a.bytes>b.bytes;
            return a.id>b.id;
        };
        int best=-1;
        for(int i=0;i<n;++i)if(best<0||cmp(c[i],c[best]))best=i;
        if(best>=0 && c[best].bytes>=deficit){
            int chosen=best;
            if(rule==2||rule==4)for(int i=0;i<n;++i)if(c[i].bytes>=deficit &&
                (c[i].value<c[chosen].value || (c[i].value==c[chosen].value&&cmp(c[i],c[chosen]))))chosen=i;
            return {Action(Action::SPILL,c[chosen].o,c[chosen].p)};
        }
        std::sort(c.begin(),c.begin()+n,cmp);
'''
    (ROOT/'FastOld.cpp').write_text(s[:start]+block+s[stop:],encoding='utf8')
PROFILES={'baseline':None,'base':'BaseScheduler.cpp','forced':1,'b1':3,'b1_feedback':11,'all_feedback':13,'all_physical':5,'build_safe':104,'pair':101,'pair_half':103,'pair_feedback':109,'pair_half_feedback':111,'pair_half_build_feedback':115,'pair_threequarter':125,'guard_feedback':141,'guard_build_feedback':145,'guard_half_build_feedback':147,'guard_physical':133,'selected':141,'slow_selected':'SlowSelected.cpp','safe_base':'SafeBase.cpp','gated':'GatedScheduler.cpp','envelope':'FinalScheduler.cpp'}

def compile_all(profiles):
    ref=(ROOT/'reference_current.cpp').read_text('utf8');cut=ref.index('/* ===== 执行引擎 ===== */')
    for name in profiles:
        setting=PROFILES[name]
        if setting is None:src=ref
        else:
            include=setting if isinstance(setting,str) else ('PairScheduler.cpp' if setting>=100 else 'PrepareScheduler.cpp')
            ctor='' if isinstance(setting,str) else str(setting-100 if setting>=100 else setting)
            src=ref[:cut]+'\n#include "'+include+'"\n'+ref[cut:]
            src=src.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<MySpillScheduler>('+ctor+')')
        p=ROOT/('engine_'+name+'.cpp');p.write_text(src,encoding='utf8')
        c=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors',str(p),'-o',str(ROOT/('bin_'+name))],capture_output=True,text=True,timeout=60)
        if c.returncode:raise RuntimeError(c.stderr)
        print('compiled',name,flush=True)
def run_case(row,name):
    begin=time.perf_counter();r=subprocess.run([str(ROOT/('bin_'+name)),linux(row['file'])],capture_output=True,text=True,timeout=60)
    wall=time.perf_counter()-begin
    if r.returncode:raise RuntimeError((name,row['id'],r.stderr))
    v={k:float(x) for k,x in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([\d.eE+-]+)',r.stdout)}
    assert len(v)==5 and v['Hit_Count']+v['Miss_Count']==row['probes'],(name,row,v)
    assert abs(v['Total_Score']-v['Total_IO_Time']-v['Total_Decision_Time']-row['penalty']*v['Miss_Count'])<.05,(name,row,v)
    return dict(case=row['id'],profile=name,wall_s=wall,**v)
def summarize(rows,results,profiles):
    g=collections.defaultdict(list)
    for x in results:g[x['case'],x['profile']].append(x)
    med={}
    for k,xs in g.items():
        assert len({(x['Total_IO_Time'],x['Miss_Count']) for x in xs})==1
        med[k]={k2:statistics.median(x[k2] for x in xs) for k2 in ['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score','wall_s']}
    valid=[r['id'] for r in rows if med[r['id'],'baseline']['Total_Score']>0]
    report={}
    for name in profiles:
        rs=[med[i,name]['Total_Score']/med[i,'baseline']['Total_Score'] for i in valid]
        worst=sorted(valid,key=lambda i:med[i,name]['Total_Score']/med[i,'baseline']['Total_Score'],reverse=True)
        report[name]=dict(cases=len(rows),ratio_cases=len(valid),geometric_ratio=math.exp(statistics.mean(math.log(x) for x in rs)),
          mean_single_score=statistics.mean(10*max(0,1-x) for x in rs),wins=sum(x<.999999 for x in rs),losses=sum(x>1.000001 for x in rs),
          worst_ratio=max(rs),p95_ratio=sorted(rs)[int(.95*len(rs))],sum_decision_us=sum(med[r['id'],name]['Total_Decision_Time'] for r in rows),
          total_misses=sum(med[r['id'],name]['Miss_Count'] for r in rows),sum_io_us=sum(med[r['id'],name]['Total_IO_Time'] for r in rows),
          worst_cases=[dict(case=i,ratio=med[i,name]['Total_Score']/med[i,'baseline']['Total_Score']) for i in worst[:6]])
    eq=[]
    if 'fast_old' in profiles and 'old_balanced' in profiles:
        eq=[r['id'] for r in rows if any(med[r['id'],'fast_old'][k]!=med[r['id'],'old_balanced'][k] for k in ['Total_IO_Time','Miss_Count','Hit_Count'])]
        assert not eq,eq
    return dict(summary=report,fast_old_non_timing_differences=eq,medians=[dict(case=k[0],profile=k[1],**v) for k,v in med.items()])
def evaluate(manifest,profiles,reps,label):
    rows=json.loads(Path(manifest).read_text('utf8'));results=[];start=time.perf_counter()
    with (ROOT/(label+'_runs.jsonl')).open('w',encoding='utf8') as f:
        for rep in range(reps):
            for i,row in enumerate(rows):
                order=profiles if (i+rep)%2==0 else profiles[::-1]
                for name in order:
                    x=run_case(row,name);x['repeat']=rep;results.append(x);f.write(json.dumps(x)+'\n')
                if (i+1)%64==0 or i+1==len(rows):f.flush();print(label,rep+1,i+1,len(rows),round(time.perf_counter()-start,1),flush=True)
    out=summarize(rows,results,profiles);out.update(repetitions=reps,manifest=str(manifest),actual_published_engine=True,compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0])
    dump(ROOT/(label+'_summary.json'),out)
    print(json.dumps({k:{a:b for a,b in v.items() if a!='worst_cases'} for k,v in out['summary'].items()},indent=2),flush=True)
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='compile':compile_all(sys.argv[2:] or list(PROFILES))
    elif mode=='run':evaluate(sys.argv[2],sys.argv[5].split(','),int(sys.argv[3]),sys.argv[4])
