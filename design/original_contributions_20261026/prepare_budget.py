"""Second iteration after observing the irreversible-growth counterexample.
The 610-case first test is now a regression/development set for this refinement.
"""
import hashlib,json,random,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from prepare_tests import chunks
from experiment import dump
import sys
sys.path.insert(0,str(ROOT.parent/'stress20'))
from retest import write_case,MIB
def main():
    s=(ROOT/'OriginalScheduler.cpp').read_text('utf8')
    s=s.replace('int options_;double scan_us_=0.25;','int options_;double scan_us_=0.25,risk_committed_=0;')
    s=s.replace('uint64_t target_pre_spills=0,guard_rejections=0;','uint64_t target_pre_spills=0,guard_rejections=0,risk_rejections=0;\n    double reserved_exposure_us=0;')
    s=s.replace('int flags=863','int flags=4959')
    needle='if((all_probe||(options_&2048))&&saving>std::max(.25,2.0*scan_us_)) {'
    s=s.replace(needle,'''double exposure=double(std::max(int64_t(0),s.memory_limit-target.data_size-s.next_op.tuple_size))/s.write_bandwidth
                    +double(s.memory_limit)/s.read_bandwidth+1000.0;
                double observed_lower_bound=double(s.total_io_bytes)/std::max(s.write_bandwidth,s.read_bandwidth)+double(s.miss_count);
                bool funded=!(options_&4096)||risk_committed_+exposure<=.05*observed_lower_bound;
                if(!funded)++risk_rejections;
                if(funded&&(all_probe||(options_&2048))&&saving>std::max(.25,2.0*scan_us_)) {
                    if(options_&4096){risk_committed_+=exposure;reserved_exposure_us=risk_committed_;}''')
    assert s!= (ROOT/'OriginalScheduler.cpp').read_text('utf8')
    (ROOT/'BudgetedScheduler.cpp').write_text(s,encoding='utf8')
    freeze=dict(source_sha256=hashlib.sha256(s.encode()).hexdigest(),budget=.05,meaning='Reserve worst growth writes plus first read plus maximum hidden miss penalty. Not a global Score competitive guarantee.')
    dump(ROOT/'budget_freeze.json',freeze)
    e=(ROOT/'experiment.py').read_text('utf8')
    a=e.index('PROFILES=');b=e.index('\ndef compile_all',a)
    e=e[:a]+"PROFILES={'baseline':None,'old_balanced':'old_balanced.cpp','core':351,'early':863,'budget':4959,'budget_externality':5983}\n"+e[b:]
    e=e.replace("else 'OriginalScheduler.cpp'","else 'BudgetedScheduler.cpp'")
    e=e.replace("('bin_'+name)","('budget_bin_'+name)").replace("('engine_'+name+'.cpp')","('budget_engine_'+name+'.cpp')")
    (ROOT/'budget_experiment.py').write_text(e,encoding='utf8')
    text=(ROOT/'strict_replay.cpp').read_text('utf8').replace('OriginalScheduler.cpp','BudgetedScheduler.cpp')
    text=text.replace('<<mine->interference_returns;', '<<mine->interference_returns<<",\\\"risk_rejections\\\":"<<mine->risk_rejections<<",\\\"reserved_exposure_us\\\":"<<mine->reserved_exposure_us;')
    (ROOT/'budget_strict_replay.cpp').write_text(text,encoding='utf8')
    run=ROOT/'funded_test';(run/'cases').mkdir(parents=True,exist_ok=True);rows=[];master=secrets.token_hex(16);rng=random.Random(master)
    for j in range(16):
        m=64*MIB;s0=rng.choice([MIB//8,MIB//2,MIB]);d=rng.choice([MIB//4,MIB]);hot=m-s0
        w,r=rng.choice([(1,10000),(10000,1),(1000,1000),(10000,10000)])
        prefix=chunks(0,0,hot)+chunks(0,1,hot)+[('SWITCH',0)]
        # Both programs pay this same forced warm-up. It is an explicit funding
        # test, not representative sampling or free performance improvement.
        prefix.extend(('PROBE',0,i%2) for i in range(65))
        prefix+=chunks(1,0,s0)+[('PROBE',0,0)]*16+[('INSERT',1,0,d)]
        for v in ['funded_preserve','funded_growth']:
            if v=='funded_preserve':ops=prefix+[('PROBE',0,0)]*512+[('SWITCH',1)]
            else:ops=prefix+chunks(1,0,m-s0-d)+[('SWITCH',1)]+[('PROBE',1,0)]*512
            row=write_case(run,f'{v}_{j:02}',(2,2,m,w,r,rng.choice([1,1000]),1),ops,family=v,paired_prefix=j,split='fresh_targeted_after_budget_freeze')
            row['file']=str((run/row['file']).resolve());rows.append(row)
    dump(run/'manifest.json',rows);dump(run/'entropy.json',dict(master=master,frozen=freeze));print('Budgeted source frozen; fresh targeted cases',len(rows),flush=True)
if __name__=='__main__':main()
