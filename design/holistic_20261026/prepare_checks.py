import json,random,secrets,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'next_probe_20261026'
# Strict replay: independent state ledger, public callbacks only.
s=(OLD/'strict_replay.cpp').read_text('utf8');a=s.index('#include "PrepareScheduler.cpp"');b=s.index('\nstruct Op ',a)
incs=[]
names={'previous':'Previous','staged':'Staged','pressure':'Pressure','cover':'Cover','mandatory':'Mandatory','pressure_cover':'PressureCover','stage_cover_mandatory':'StageCoverMandatory','integrated':'Integrated'}
for name,cls in names.items():
    incs.extend(['#define MySpillScheduler '+cls,'#include "'+('Previous.cpp' if name=='previous' else name+'.cpp')+'"','#undef MySpillScheduler'])
s=s[:a]+'\n'.join(incs)+'\n'+s[b:]
a=s.index('    else if(name=="base")');b=s.index('    std::vector<OperatorState> ops;',a)
s=s[:a]+''.join('    else if(name=="'+name+'")policy.reset(new '+cls+'());\n' for name,cls in names.items())+'    else throw std::runtime_error("Unknown policy");\n'+s[b:]
a=s.index('    auto mine=dynamic_cast');b=s.index('    std::cout<<",\\\"overflow_callbacks',a)
block=''
for name,cls in names.items():
    if name=='previous':continue
    block+='    if(auto mine=dynamic_cast<'+cls+'*>(policy.get()))std::cout<<",\\\"stage_rejections\\\":"<<mine->stage_rejections<<",\\\"restore_updates\\\":"<<mine->restore_updates<<",\\\"cover_searches\\\":"<<mine->cover_searches<<",\\\"cover_completed\\\":"<<mine->cover_completed<<",\\\"cover_accepts\\\":"<<mine->cover_accepts<<",\\\"forced_plans\\\":"<<mine->forced_plans<<",\\\"search_us\\\":"<<mine->searchSpentUs();\n'
s=s[:a]+block+s[b:];(ROOT/'strict_replay.cpp').write_text(s,encoding='utf8')
sys.path.insert(0,str(ROOT.parent/'stress20'));from retest import write_case,MIB
def chunks(o,p,n):
    out=[]
    while n:x=min(n,MIB);out.append(('INSERT',o,p,x));n-=x
    return out
run=ROOT/'cross_targets';(run/'cases').mkdir(parents=True,exist_ok=True);rows=[];master=secrets.token_hex(16);rng=random.Random(master)
for j in range(32):
    k=3;p=64;m=64*MIB;ops=[]
    for o in [0,1]:
        for pid in range(p):ops+=chunks(o,pid,2*MIB if pid==0 else (0 if pid==63 else MIB))
        ops.append(('SWITCH',o))
    # A pressured Probe warm-up, then an overlapping growing BUILD operator.
    for i in range(768):
        x=i%126;ops.append(('PROBE',x//63,x%63))
    for pid in range(p):
        ops+=chunks(2,pid,MIB//2)
        for t in range(4):ops.append(('PROBE',t%2,(pid+t)%16))
    for i in range(512):ops.append(('PROBE',i%2,(i//2)%16))
    grow=j*2+rng.randrange(2)
    ops+=chunks(2,grow,48*MIB-MIB//2)+[('SWITCH',2),('PROBE',2,grow)]
    for i in range(128):ops.append(('PROBE',i%2,i%16))
    row=write_case(run,f'grow_after_overlap_{j:02}',(k,p,m,10000,rng.choice([1,100,10000]),rng.choice([1,1000]),rng.choice([1,3,31,1000])),ops,family='grow_after_overlap',split='development_target',grow_partition=grow)
    row['file']=str((run/row['file']).resolve());rows.append(row)
(ROOT/'cross_target_manifest.json').write_text(json.dumps(rows,indent=2));(run/'entropy.json').write_text(json.dumps(dict(master=master)))
e=(ROOT/'experiment.py').read_text('utf8')
e=e.replace("        assert len({(x['Total_IO_Time'],x['Miss_Count']) for x in xs})==1", "        if k[1] not in ['cover','pressure_cover','stage_cover_mandatory','integrated','chosen']:assert len({(x['Total_IO_Time'],x['Miss_Count']) for x in xs})==1")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
print('Prepared strict metrics and',len(rows),'overlap/growth counterexamples.')
