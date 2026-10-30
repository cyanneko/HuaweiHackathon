"""Build frozen R49 engine with fixed legal witness, assert every visible callback.
Only scheduler class is replaced. Engine source provenance is recorded.
"""
from core import *
import subprocess
O=Path(__file__).resolve().parent
def linux(p):return '/mnt/'+str(p)[0].lower()+str(p)[2:].replace('\\','/')
def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--input');ap.add_argument('--out',default='verification');ap.add_argument('--seconds',type=float,default=2);args=ap.parse_args()
    out=O/args.out;out.mkdir(exist_ok=True)
    # Valid >=64 MiB, tuple <=1 MiB, each partition <=M.
    ops=[('INSERT',0,p,1<<20) for _ in range(30) for p in range(3)]+[('SWITCH',0)]+[('PROBE',0,p) for _ in range(8) for p in (0,2,1)]
    c=Case(1,3,64<<20,100,200,7,7,ops)
    text='1 3 67108864 100 200 7\n%d 7\n0 90 24\n'%len(ops)+'\n'.join(' '.join(map(str,x)) for x in ops)+'\n'
    ip=Path(args.input) if args.input else out/'valid64MiB.in'
    if not args.input:ip.write_text(text)
    c=Case.read(ip);best,stats=search(c,seconds=args.seconds,width=8)
    (out/'witness.json').write_text(json.dumps(best.path,indent=2))
    (out/'search_stats.json').write_text(json.dumps(stats,indent=2))
    s=State(c);j=0;bodies=[]
    while s.advance():
        kind,t,need=s.callback;a=tuple(best.path[j]['spill']);n=next_public(s)
        checks=[f'assert(tag==\'{kind}\');',f'assert(s.memory_used=={s.used}LL && s.hit_count=={s.hit}LL && s.miss_count=={s.miss}LL && s.total_io_bytes=={s.write+s.read}LL);',f'assert(s.next_op.type=="{n[0]}");']
        checks.append('h.observe(s);')
        for i,x in enumerate(s.h.slots):
            for field,value in zip(('size','h','anchor','ghost','reward'),x):checks.append(f'assert(h.slots_[{i}].{field}=={value}LL);')
        if kind!='P':
            plans=pool(s)
            checks.append(f'auto plans=r66::pool(s,h,o,p,need,tag==\'M\');assert(plans.size()=={len(plans)});')
            for pi,plan in enumerate(plans):
                checks.append(f'assert(plans[{pi}].spill==std::vector<int>{{{",".join(map(str,plan))}}});')
                for fi,value in enumerate(features(s,plan)):
                    checks.append(f'assert(plans[{pi}].x[{fi}]==static_cast<float>({value!r}));')
        if n[0]:checks.append(f'assert(s.next_op.op_id=={n[1]});')
        if len(n)>2:checks.append(f'assert(s.next_op.key=={n[2]}LL);')
        if len(n)>3:checks.append(f'assert(s.next_op.tuple_size=={n[3]}LL);')
        for i,z in enumerate(s.sizes):checks.append(f'assert(s.operators[{i//c.p}].partitions[{i%c.p}].data_size=={z}LL && s.operators[{i//c.p}].partitions[{i%c.p}].in_memory=={str(s.mem[i]).lower()});')
        for i,p in enumerate(s.phase):checks.append(f'assert(s.operators[{i}].phase==Phase::{"PROBE" if p else "BUILD"});')
        if kind!='P':checks.append(f'assert(o=={t//c.p} && p=={t%c.p} && need=={need}LL);')
        actions=[f'Action(Action::SPILL,{i//c.p},{i%c.p})' for i in a]
        if kind=='M':actions.append(f'Action(Action::LOAD,{t//c.p},{t%c.p})')
        dispatch='std::vector<Action>a={%s};'%','.join(actions)
        if kind!='P':dispatch+='h.record(s,a,o,p,need,tag==\'M\');'
        bodies.append('case %d: {%s %s return a;}'%(j,''.join(checks),dispatch))
        s.apply(a);j+=1
    scheduler='''class NaiveSpillScheduler:public SpillScheduler {int index=0;R66History h; std::vector<Action> step(const SystemState&s,char tag,int o,int p,int64_t need){switch(index++){BODY} assert(false);return {}; } public:
    ~NaiveSpillScheduler(){assert(index==CALLBACKS);}
    std::vector<Action> onMemoryOverflow(const SystemState&s,int o,int p,int64_t n) override{return step(s,'O',o,p,n);}
    std::vector<Action> onPartitionMiss(const SystemState&s,int o,int p) override{return step(s,'M',o,p,s.operators[o].partitions[p].data_size);}
    std::vector<Action> onPeriodicAdjust(const SystemState&s) override{return step(s,'P',-1,-1,0);}};
    '''.replace('BODY',''.join(bodies)).replace('CALLBACKS',str(j))
    source=O.parent/'round49_latency_baseline/reference_compilable.cpp';raw=source.read_text(encoding='utf-8')
    cpp=out/'witness_engine.cpp';cpp.write_text(raw[:raw.index('class NaiveSpillScheduler')]+(O/'shared_pool.hpp').read_text()+scheduler+raw[raw.index('class HashJoinEngine'):],encoding='utf-8')
    exe=out/'witness_engine'
    build=subprocess.run(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',linux(cpp),'-o',linux(exe)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60)
    (out/'compile.log').write_text(build.stdout+build.stderr,encoding='utf-8');assert build.returncode==0,repr(build.stderr)
    run=subprocess.run(['wsl','-d','Ubuntu','--',linux(exe),linux(ip)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
    (out/'official.log').write_text(run.stdout+run.stderr,encoding='utf-8');assert run.returncode==0,repr(run.stderr)
    result={a:float(b.strip()) for line in run.stdout.splitlines() if ':' in line for a,b in [line.split(':',1)]}
    assert result['Miss_Count']==s.miss and result['Hit_Count']==s.hit
    assert abs(result['Total_IO_Time']-s.ordered_io)<1e-3
    stats['replay_verified']=True;stats['verification_method']='frozen_R49_engine_full_callback_assertions'
    (out/'search_stats.json').write_text(json.dumps(stats,indent=2))
    report={'engine_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'core_sha256':hashlib.sha256((O/'core.py').read_bytes()).hexdigest(),'callbacks_asserted':j,'physical_and_public_state_parity':True,'history_cpp_parity':True,'pool_and_fp32_features_cpp_parity':True,'input_sha256':c.input_hash,'write_bytes':s.write,'read_bytes':s.read,'misses':s.miss,'ordered_io':s.ordered_io,'grouped_io':s.write/c.w+s.read/c.r,'official':result,'search':stats}
    (out/'official_parity.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    rows=demonstrations(c,best.path,stats,ip.stem)
    for row in rows:
        row['search_status']=row['teacher_status'];row['teacher_status']='timeout_feasible' if stats['status']=='timeout_feasible' else 'best_found'
        row['replay_verified']=True;row['verification_method']='frozen_R49_engine_full_callback_assertions';row['verification_report_sha256']=hashlib.sha256((out/'official_parity.json').read_bytes()).hexdigest()
    (out/'path_demo.jsonl').write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
    print('verified path_demo rows',len(rows))
if __name__=='__main__':main()

