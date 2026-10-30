"""Generate three fixed-mode schedulers and one same-action verification build."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
NAMES=('pooling','no_pooling','global_scale')


def put(path,text):
    if path.exists():assert path.read_text()==text,path
    else:path.write_text(text)


def source(mode):
    raw=(ROOT/'round9/candidates/paired_penalty100.cpp').read_text()
    assert hashlib.sha256(raw.encode()).hexdigest()=='3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15'
    pre,body=raw.split('class MySpillScheduler : public SpillScheduler {',1)
    inner='class ReferencePair : public SpillScheduler {\n    RiskCore* deployed_=nullptr;\n    static constexpr int deployed_mode_='+str(mode)+';'+body
    old='        if(immediate+64.0*mean+2.0*sd>=0)return;'
    new='        const double deployed_future=deployed_->future(s,sign,64.0*mean,[&](int i){return probability(i);},deployed_mode_);\n        if(immediate+deployed_future+2.0*sd>=0)return;'
    assert inner.count(old)==1;inner=inner.replace(old,new)
    old='public:\n    std::vector<Action> onMemoryOverflow'
    new='public:\n    void riskHook(RiskCore* p){deployed_=p;}\n    double riskProbability(int id)const{return probability(id);}\n    std::vector<Action> onMemoryOverflow'
    assert inner.count(old)==1;inner=inner.replace(old,new)
    outer=r'''
    ReferencePair inner_;
    RiskCore risk_;
    void before(const SystemState& s,char tag,int id) {
        risk_.before(s,tag,id,[&](int i){return inner_.riskProbability(i);});
    }
public:
    MySpillScheduler(){inner_.riskHook(&risk_);}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t bytes) override {
        before(s,'O',op*s.num_partitions+pid);
        auto actions=inner_.onMemoryOverflow(s,op,pid,bytes);risk_.after(s,actions);return actions;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        before(s,'M',op*s.num_partitions+pid);
        auto actions=inner_.onPartitionMiss(s,op,pid);risk_.after(s,actions);return actions;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        before(s,'P',-1);
        auto actions=inner_.onPeriodicAdjust(s);risk_.after(s,actions);return actions;
    }
};
'''
    result=pre+'#include <array>\nclass MySpillScheduler : public SpillScheduler {\n'+(HERE/'return_risk_core_v1.hpp').read_text()+'\n'+inner+'\n'+outer
    assert result.count('class MySpillScheduler')==1 and 'std::cerr' not in result
    return result


def verifier():
    from run_return_risk_v1 import source_text
    raw=(ROOT/'round9/candidates/paired_penalty100.cpp').read_text()
    policy=source_text(raw)
    policy=(HERE/'return_risk_core_v1.hpp').read_text()+'\n'+policy
    # RiskCore requires the same standard headers before its declaration.
    policy='#include <array>\n#include <algorithm>\n#include <cmath>\n#include <cstdint>\n#include <vector>\n'+policy
    token='class ReturnRiskV1 {\npublic:'
    extra=r'''
    RiskCore* compact=nullptr;
    int64_t checked_states=0,checked_pairs=0,nonbit_coordinates=0;
    double dz_abs_max=0,dz_scaled_max=0,future_abs_max=0;
    void verify(const char*) {
        check(compact && compact->active()==active_,"compact activation");
        if(!active_)return;
        check(compact->size()==n_ && compact->q()==last_q_,"compact clock");
        ++checked_states;
        for(int i=0;i<n_;++i)for(int kind=0;kind<2;++kind) {
            const double a=kind?z[i]:d[i],b=kind?compact->z[i]:compact->d[i];
            const double delta=std::abs(a-b),scaled=delta/std::max(1.0,std::abs(a));
            nonbit_coordinates+=a!=b;dz_abs_max=std::max(dz_abs_max,delta);dz_scaled_max=std::max(dz_scaled_max,scaled);
            check(scaled<=2e-12,"compact D/Z mismatch");
        }
    }
    void print_deploy() {
        std::cerr<<std::setprecision(17)<<"DEPLOY_CHECK {\"states\":"<<checked_states<<",\"pairs\":"<<checked_pairs
                 <<",\"nonbit_coordinates\":"<<nonbit_coordinates<<",\"dz_abs_max\":"<<dz_abs_max
                 <<",\"dz_scaled_max\":"<<dz_scaled_max<<",\"future_abs_max\":"<<future_abs_max
                 <<",\"sizeof_compact\":"<<sizeof(RiskCore)<<"}\n";
    }
'''
    assert policy.count(token)==1;policy=policy.replace(token,token+extra)
    token='        c.base_alt+=base_alt;'
    insert=r'''
        const double compact_pool=compact->future(s,sign,base_future,probability,0);
        const double compact_flat=compact->future(s,sign,base_future,probability,1);
        const double compact_global=compact->future(s,sign,base_future,probability,2);
        const bool compact_global_alt=immediate+compact_global+risk<0;
        verify("pair");++checked_pairs;
        future_abs_max=std::max(future_abs_max,std::max(std::abs(compact_pool-pool_future),std::abs(compact_flat-flat_future)));
        check(std::abs(compact_pool-pool_future)<=2e-12*std::max(1.0,std::abs(pool_future)),"compact pooled future");
        check(std::abs(compact_flat-flat_future)<=2e-12*std::max(1.0,std::abs(flat_future)),"compact flat future");
        check((immediate+compact_pool+risk<0)==pool_alt && (immediate+compact_flat+risk<0)==flat_alt,"compact decision");
        std::cerr<<std::setprecision(17)<<"RR_GLOBAL {\"cb\":"<<c.callbacks<<",\"q\":"<<last_q_
                 <<",\"F\":"<<compact_global<<",\"choose\":"<<compact_global_alt<<"}\n";
'''
    assert policy.count(token)==1;policy=policy.replace(token,insert+token)
    old='ReferencePair inner_;ReturnRiskV1 stats_;'
    assert policy.count(old)==1;policy=policy.replace(old,old+'RiskCore core_;')
    old='stats_.before(s,tag,id,[&](int i){return inner_.diagnosticProbability(i);});'
    policy=policy.replace(old,old+'core_.before(s,tag,id,[&](int i){return inner_.diagnosticProbability(i);});stats_.verify("before");')
    old='stats_.after(s,tag,id,actions);'
    policy=policy.replace(old,old+'core_.after(s,actions);')
    old='next_checkpoint_=checkpoint_<4?thresholds[checkpoint_]:((stats_.q()/65536)+1)*65536;}'
    assert policy.count(old)==1;policy=policy.replace(old,old+'stats_.verify("after");')
    old='stats_.sync();std::cerr'
    assert policy.count(old)==1;policy=policy.replace(old,'stats_.sync();core_.sync();stats_.verify("snapshot");std::cerr')
    old='MySpillScheduler(){inner_.diagnosticHook(&stats_);}'
    policy=policy.replace(old,'MySpillScheduler(){inner_.diagnosticHook(&stats_);stats_.compact=&core_;}')
    old='stats_.print_stats();}'
    assert policy.count(old)==1;policy=policy.replace(old,'stats_.print_stats();stats_.print_deploy();}')
    return policy


def auditor():
    raw=(HERE/'audit_return_risk_scale_v1.py').read_text()
    raw=raw.replace('def audit_scale(path, stderr, final):','def audit_deploy(path, stderr, final):')
    raw=raw.replace('    attribution=ScaleAttribution()','    attribution=ScaleAttribution()\n    numeric={"global_pairs":0,"global_abs_error_max":0.,"global_scaled_error_max":0.}')
    raw=raw.replace('        pairs, snapshots = [], []','        pairs, snapshots = [], []\n        global_row=None')
    old="            if line.startswith('RR_PAIR '): pairs.append(json.loads(line[8:]))"
    new="            if line.startswith('RR_GLOBAL '): global_row=json.loads(line[10:])\n            elif line.startswith('RR_PAIR '):\n                row=json.loads(line[8:]);assert global_row is not None;row['deploy_global']=global_row;pairs.append(row);global_row=None"
    assert raw.count(old)==1;raw=raw.replace(old,new)
    old="                selected={op*p+pid for typ,op,pid in actions if typ=='S'}"
    new="""                gg=row['deploy_global'];assert gg['cb']==cb and gg['q']==q
                close(gg['F'],fs[3],'C++ global future');assert gg['choose']==choose[3]
                numeric['global_pairs']+=1
                numeric['global_abs_error_max']=max(numeric['global_abs_error_max'],abs(gg['F']-fs[3]))
                numeric['global_scaled_error_max']=max(numeric['global_scaled_error_max'],abs(gg['F']-fs[3])/max(1.,abs(fs[3])))
"""+old
    assert raw.count(old)==1;raw=raw.replace(old,new)
    old="return {'scale_attribution':attribution.export(loss,fields)"
    new="return {'deploy_numeric':numeric,'scale_attribution':attribution.export(loss,fields)"
    assert raw.count(old)==1;raw=raw.replace(old,new)
    return '# Derived by make_return_risk_deploy_v1.py; original scale audit retained.\n'+raw


def main():
    for mode,name in enumerate(NAMES):
        path=HERE/('return_risk_'+name+'100_v1.cpp');put(path,source(mode));print(name,hashlib.sha256(path.read_bytes()).hexdigest())
    put(HERE/'return_risk_deploy_verify_v1.cpp',verifier())
    put(HERE/'audit_return_risk_deploy_v1.py',auditor())


if __name__=='__main__':main()
