"""Read-only paired-policy advice on the unchanged forced0 collector trajectory."""
import hashlib,json,os,re,subprocess,sys,time
import numpy as np
from local_build import HERE,ROOT,official
from make_policy import put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import parse_output

WRAPPER=r'''
#include <cstdlib>
#include <sstream>
#include <string>
#include <tuple>
class MySpillScheduler : public SpillScheduler {
    ForcedPolicy base_;PurePairPolicy shadow_;std::vector<int64_t> audit_q_;
    typedef std::tuple<int,int,int> Key;
    static std::vector<Key> keys(const std::vector<Action>& a,bool sort_keys) {
        std::vector<Key> k;for(const auto& x:a)k.emplace_back(static_cast<int>(x.type),x.op_id,x.partition_id);
        if(sort_keys)std::sort(k.begin(),k.end());return k;
    }
public:
    MySpillScheduler() {
        base_.forceMode(0);const char* raw=std::getenv("PAIR_AUDIT_Q");
        if(raw){std::istringstream in(raw);int64_t q;while(in>>q)audit_q_.push_back(q);}
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        shadow_.observeOnly(s,'O',op,pid);return base_.onMemoryOverflow(s,op,pid,z);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        const int64_t q=s.hit_count+s.miss_count;
        if(std::find(audit_q_.begin(),audit_q_.end(),q)==audit_q_.end()) {
            shadow_.observeOnly(s,'M',op,pid);return base_.onPartitionMiss(s,op,pid);
        }
        ForcedPolicy alternate=base_;alternate.forceMode(1);
        const auto a1=alternate.onPartitionMiss(s,op,pid);
        const auto advice=shadow_.onPartitionMiss(s,op,pid);
        const auto a0=base_.onPartitionMiss(s,op,pid);
        const bool load_same=!a0.empty() && !a1.empty() && !advice.empty() &&
            a0.back().type==Action::LOAD && a1.back().type==Action::LOAD && advice.back().type==Action::LOAD &&
            a0.back().op_id==op && a1.back().op_id==op && advice.back().op_id==op &&
            a0.back().partition_id==pid && a1.back().partition_id==pid && advice.back().partition_id==pid;
        const auto k0=keys(a0,true),k1=keys(a1,true),kp=keys(advice,true);
        const int mode=kp==k0?0:(kp==k1?1:-1);
        const bool exact_order=mode>=0 && keys(advice,false)==keys(mode?a1:a0,false);
        std::cerr<<"PAIR_ADVICE "<<q<<' '<<mode<<' '<<(k0!=k1)<<' '<<load_same<<' '<<exact_order<<'\n';
        return a0; // The shadow advice is never applied to the real engine.
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        shadow_.observeOnly(s,'P');return base_.onPeriodicAdjust(s);
    }
};
'''

def source():
    base=(HERE/'local_forced0.cpp').read_text().replace('MySpillScheduler','ForcedPolicy')
    path=ROOT/'round8/pure/paired_confidence.cpp';pure=path.read_text().replace('MySpillScheduler','PurePairPolicy')
    marker='public:\n    std::vector<Action> onMemoryOverflow'
    observe='''public:
    void observeOnly(const SystemState& s,char tag,int op=-1,int pid=-1) {
        if(tag=='O') {active_=true;update(s);}
        else if(tag=='M') {active_=true;update(s,op,pid);sampleNext(s,2);}
        else {update(s);sampleNext(s,1);}
    }
    std::vector<Action> onMemoryOverflow'''
    assert pure.count(marker)==1;pure=pure.replace(marker,observe)
    return base+'\n'+pure+'\n'+WRAPPER,hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    dataset=HERE/'INDEPENDENT_COLLECT_RESULTS.json';data=json.loads(dataset.read_text());assert data['complete']
    policy,pure_sha=source();path=HERE/'paired_shadow_audit.cpp';put(path,policy)
    plan={'data_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),'pure_sha256':pure_sha,
          'policy_sha256':hashlib.sha256(policy.encode()).hexdigest(),'actual_policy':'forced0',
          'shadow_state':'Only genuine forced0 callbacks update observations. No shadow actions are applied; no ghost/residency derived from unexecuted actions.',
          'action_match':'Canonical (type,op,pid) multiset; separately require same final LOAD and record exact ordering.',
          'scope':'Conditional advice on forced0 trajectory; not paired closed-loop performance.'}
    put(HERE/'PAIRED_SHADOW_PLAN.json',json.dumps(plan,indent=2)+'\n')
    build=HERE/'build/paired_shadow';build.mkdir(parents=True,exist_ok=True)
    with experiment_lock():exe=official('paired_shadow_audit_v1',path)
    records=[];started=time.time()
    for flow in data['rows']:
        with experiment_lock():
            input_path=ROOT/'build/round8/data/learning_train'/(flow['id']+'.txt')
            assert hashlib.sha256(input_path.read_bytes()).hexdigest()==flow['input_sha256']
            cache=build/(flow['id']+'.json')
            if cache.exists():
                result=json.loads(cache.read_text());assert result['policy_sha256']==plan['policy_sha256']
            else:
                env=dict(os.environ,PAIR_AUDIT_Q=' '.join(str(x['start_probe']+1) for x in flow['rows']))
                run=subprocess.run([str(exe),str(input_path)],env=env,capture_output=True,text=True,check=True,timeout=120)
                metrics=parse_output(run.stdout);original=flow['collector_metrics']
                for key in ['Total_IO_Time','Miss_Count','Hit_Count']:
                    assert abs(metrics[key]-original[key])<.01,(flow['id'],key,metrics[key],original[key])
                entries=[]
                for line in run.stderr.splitlines():
                    if line.startswith('PAIR_ADVICE '):
                        _,q,mode,different,load_same,order=line.split()
                        assert int(mode) in [0,1] and int(different)==1 and int(load_same)==1,line
                        entries.append({'probe':int(q),'mode':int(mode),'different_candidates':True,'final_load_same':True,'exact_order_same':bool(int(order))})
                assert [e['probe'] for e in entries]==[x['start_probe']+1 for x in flow['rows']]
                result={'id':flow['id'],'policy_sha256':plan['policy_sha256'],'matches_collector_physical':True,'advice':entries}
                put(cache,json.dumps(result,indent=2)+'\n')
            records.append(result);print('shadow',len(records),flow['id'],'seconds',round(time.time()-started,1),flush=True)
    gains=[];relative=[];choices=[];components=[]
    for flow,result in zip(data['rows'],records):
        rd,wr=flow['bandwidths'];p=flow['penalty_offline_only'];unit=flow['memory_limit']*(1/rd+1/wr)
        for row,advice in zip(flow['rows'],result['advice']):
            cost=np.array([b['read_bytes']/rd+b['write_bytes']/wr+p*b['misses'] for b in row['branches']]).reshape(2,2)
            gain=(cost[:,0]-cost[:,1])/unit
            gains.append(min(gain));relative.append(min((cost[:,0]-cost[:,1])/cost[:,0]));choices.append(advice['mode']);components.append(gain)
    weight=np.ones(len(gains))/len(gains) # Exactly six states per independent seed.
    assert all(len(f['rows'])==6 for f in data['rows'])
    result={'flows':len(records),'states':len(gains),'collector_physical_checks':len(records),
            'different_candidate_and_final_load_checks':len(gains),
            'exact_action_order_matches':sum(a['exact_order_same'] for f in records for a in f['advice']),
            'paired_mode1_fraction':float(np.mean(choices)),
            'paired_conditional_min_gain_memory_transfer_units':float(np.sum(weight*np.array(choices)*gains)),
            'paired_conditional_min_gain_interval_ratio':float(np.sum(weight*np.array(choices)*relative)),
            'paired_per_continuation':[float(np.sum(weight*np.array(choices)*np.array(components)[:,j])) for j in [0,1]],
            'rows':records,'scope':plan['scope']}
    put(HERE/'PAIRED_SHADOW_RESULTS.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
