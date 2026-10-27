from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    base=(ROOT/'StackScheduler.cpp').read_text('utf8')
    tail=base.rindex('    std::vector<Action> onPeriodicAdjust')
    prefix,body=base[:tail],base[tail:]
    old='observe(o*s.num_partitions+p,o,tick(s)+1);'
    assert body.count(old)==1
    fixed=prefix+body.replace(old,'if(!x.in_memory||((tick(s)+1)&15)==0)observe(o*s.num_partitions+p,o,tick(s)+1);')
    (ROOT/'Sample16Scheduler.cpp').write_text(fixed,encoding='utf8')
    loc=prefix.index('    int rule_=4;')+len('    int rule_=4;')
    controller='''
    unsigned stride_=1,sample_measurements_=0;
    uint64_t control_at_=0,control_probe_=0,control_io_=0,control_miss_=0;
    double metadata_us_=0.04;
    void sampledObserve(const SystemState& s,int o,int p,bool resident) {
        uint64_t now=tick(s)+1;
        if(now>=control_at_) {
            uint64_t delta=now>control_probe_?now-control_probe_:1;
            double lower_per_probe=(double(uint64_t(s.total_io_bytes)-control_io_)/std::max(s.write_bandwidth,s.read_bandwidth)
                +double(uint64_t(s.miss_count)-control_miss_))/double(delta);
            double allowance=.02*lower_per_probe;
            stride_=1;while(stride_<64&&metadata_us_/stride_>allowance)stride_*=2;
            control_at_=now+256;control_probe_=now;control_io_=uint64_t(s.total_io_bytes);control_miss_=uint64_t(s.miss_count);
        }
        if(resident&&(now&(stride_-1))!=0)return;
        int id=o*s.num_partitions+p;
        if((++sample_measurements_&255)!=0){observe(id,o,now);return;}
        auto start=std::chrono::steady_clock::now();observe(id,o,now);
        double elapsed=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        metadata_us_=.875*metadata_us_+.125*elapsed;
    }
'''
    dynamic='#include <chrono>\n'+prefix[:loc]+controller+prefix[loc:]+body.replace(old,'sampledObserve(s,o,p,x.in_memory);')
    (ROOT/'DynamicScheduler.cpp').write_text(dynamic,encoding='utf8')
    # Reuse a checked public-engine runner, with each variant as a no-arg type.
    e=(ROOT.parent/'original_contributions_20261026'/'experiment.py').read_text('utf8')
    a=e.index('PROFILES=');b=e.index('\ndef compile_all',a)
    e=e[:a]+"PROFILES={'baseline':None,'previous':'PreviousScheduler.cpp','static':'StaticScheduler.cpp','stack':'StackScheduler.cpp','sample16':'Sample16Scheduler.cpp','dynamic':'DynamicScheduler.cpp'}\n"+e[b:]
    e=e.replace('    fast_old();ref=', '    ref=')
    e=e.replace("        assert len({(x['Total_IO_Time'],x['Miss_Count']) for x in xs})==1", "        if k[1] not in ['dynamic']:assert len({(x['Total_IO_Time'],x['Miss_Count']) for x in xs})==1")
    (ROOT/'experiment.py').write_text(e,encoding='utf8')
    print('Generated fixed/dynamic observation budgets and benchmark runner.')
if __name__=='__main__':main()
