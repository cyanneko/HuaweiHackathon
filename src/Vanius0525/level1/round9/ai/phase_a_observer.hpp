// Offline observer only. Sampling seed never reaches the underlying scheduler.
#include <array>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>
#include <cmath>
#include <cstdint>
struct PhaseAPair {
    int eligible=0,reason=0;bool different=false,chosen=false;
    double immediate=0,mean=0,sd=0,effective=0,margin=0;
    std::vector<Action> history,dynamic;
};
struct PhaseACoverage {
    bool active=false,initialized=false,prefetched=false;
    int64_t start=0,q=0,h=0,m=0,pending_q=-1,exact=0,anonymous=0,known_hit=0,prefetch_hit=0;
    int pending_id=-1,pending_sources=0;
    int64_t last_dq=0,last_exact=0,last_anonymous=0;
    std::array<int64_t,8> sources{{}},op_exact{{}};
    std::vector<bool> after_mask;
    void add(int id,int source,int parts){++exact;++sources[source];++op_exact[id/parts];++last_exact;}
    bool before(const SystemState& s,char tag,int op,int pid) {
        active=true;for(const auto& o:s.operators)if(o.phase!=Phase::PROBE)active=false;
        if(!active){initialized=false;pending_q=-1;return false;}
        const int64_t now=s.hit_count+s.miss_count;
        std::vector<bool> before_mask(s.operators.size()*s.num_partitions);
        for(const auto& o:s.operators)for(const auto& p:o.partitions)before_mask[o.op_id*s.num_partitions+p.partition_id]=p.in_memory;
        const bool first=!initialized;last_dq=last_exact=last_anonymous=0;
        if(first){initialized=true;start=now;q=now;h=s.hit_count;m=s.miss_count;}
        else {
            if(before_mask!=after_mask)throw std::runtime_error("PhaseA unstable resident set");
            last_dq=now-q;const int64_t dh=s.hit_count-h,dm=s.miss_count-m;
            if(last_dq<0 || dh<0 || dm!=(tag=='M'?1:0))throw std::runtime_error("PhaseA clock/miss mismatch");
            const bool known=pending_q>q && pending_q<=now;
            const bool hit=known && after_mask[pending_id];
            const bool same=known && tag=='M' && pending_q==now;
            if(same && pending_id!=op*s.num_partitions+pid)throw std::runtime_error("PhaseA known identity mismatch");
            if(known && !hit && !same)throw std::runtime_error("PhaseA skipped known miss");
            if(known)add(pending_id,pending_sources|(same?4:0),s.num_partitions);
            if(tag=='M' && !same)add(op*s.num_partitions+pid,4,s.num_partitions);
            last_anonymous=dh-static_cast<int>(hit);
            if(last_anonymous<0 || last_exact+last_anonymous!=last_dq)throw std::runtime_error("PhaseA coverage identity");
            anonymous+=last_anonymous;known_hit+=hit;prefetch_hit+=hit && prefetched;
            if(known){pending_q=-1;pending_id=-1;pending_sources=0;prefetched=false;}
            q=now;h=s.hit_count;m=s.miss_count;
        }
        if(s.next_op.type=="PROBE") {
            const int id=s.next_op.op_id*s.num_partitions+s.next_op.key%s.num_partitions;
            if(pending_q==now+1){if(pending_id!=id)throw std::runtime_error("PhaseA duplicate next mismatch");}
            else {pending_q=now+1;pending_id=id;pending_sources=0;prefetched=false;}
            pending_sources|=tag=='P'?1:2;
        }else if(pending_q>now)throw std::runtime_error("PhaseA unexecuted next disappeared");
        if(exact+anonymous!=q-start)throw std::runtime_error("PhaseA cumulative coverage");
        return first;
    }
    void after(const SystemState& s,char tag,const std::vector<Action>& actions) {
        if(!active)return;
        after_mask.assign(s.operators.size()*s.num_partitions,false);
        for(const auto& o:s.operators)for(const auto& p:o.partitions)after_mask[o.op_id*s.num_partitions+p.partition_id]=p.in_memory;
        for(const auto& a:actions){const int id=a.op_id*s.num_partitions+a.partition_id;after_mask[id]=a.type==Action::LOAD;if(tag=='P' && id==pending_id && a.type==Action::LOAD)prefetched=true;}
    }
    std::string json()const {
        std::ostringstream o;o<<"{\"start_q\":"<<start<<",\"last_q\":"<<q<<",\"span\":"<<q-start<<",\"exact\":"<<exact<<",\"anonymous\":"<<anonymous<<",\"known_hit\":"<<known_hit<<",\"periodic_prefetch_hit\":"<<prefetch_hit<<",\"last_dq\":"<<last_dq<<",\"last_exact\":"<<last_exact<<",\"last_anonymous\":"<<last_anonymous<<",\"source_bits\":[";
        for(int i=0;i<8;++i)o<<(i?",":"")<<sources[i];o<<"],\"op_exact\":[";for(int i=0;i<8;++i)o<<(i?",":"")<<op_exact[i];o<<"]}";return o.str();
    }
};
struct PhaseABin {
    int64_t pressure=0,eligible=0,different=0,chosen=0,negative=0,nonnegative=0;
    double margin_sum=0,margin_min=0,margin_max=0;
    void add(const PhaseAPair& p){++pressure;eligible+=p.eligible;different+=p.different;chosen+=p.chosen;if(p.different){negative+=p.margin<0;nonnegative+=p.margin>=0;margin_sum+=p.margin;if(different==1)margin_min=margin_max=p.margin;else{margin_min=std::min(margin_min,p.margin);margin_max=std::max(margin_max,p.margin);}}}
    std::string json()const{std::ostringstream o;o<<std::setprecision(17)<<"{\"pressure\":"<<pressure<<",\"eligible\":"<<eligible<<",\"different\":"<<different<<",\"chosen_dynamic\":"<<chosen<<",\"negative_margin\":"<<negative<<",\"nonnegative_margin\":"<<nonnegative<<",\"margin_sum\":"<<margin_sum<<",\"margin_min\":"<<margin_min<<",\"margin_max\":"<<margin_max<<"}";return o.str();}
};
inline uint64_t phaseAMix(uint64_t z){z+=0x9e3779b97f4a7c15ULL;z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;z=(z^(z>>27))*0x94d049bb133111ebULL;return z^(z>>31);}
struct PhaseASample {uint64_t key;int64_t q;std::string json;};
template<class Base> class PhaseAWrapper: public SpillScheduler {
    Base base_;PhaseACoverage coverage_;std::array<PhaseABin,4> bins_;
    std::array<std::vector<PhaseASample>,8> samples_;
    uint64_t seed_=0;bool seed_set_=false;int64_t callbacks_=0;
    static int stratum(int64_t q){return q<1024?0:q<16384?1:q<262144?2:3;}
    static void actionsJson(std::ostream& o,const std::vector<Action>& a){o<<'[';for(size_t i=0;i<a.size();++i){if(i)o<<',';o<<"[\""<<(a[i].type==Action::SPILL?'S':'L')<<"\","<<a[i].op_id<<','<<a[i].partition_id<<']';}o<<']';}
    void sample(const SystemState& s,int op,int pid,const PhaseAPair& p,const std::vector<Action>& actual,int bin,bool diff) {
        if(!seed_set_){const char* value=std::getenv("PHASE_A_SAMPLE_SEED");if(!value)throw std::runtime_error("PhaseA sampling seed absent");seed_=std::stoull(value);seed_set_=true;}
        const int64_t q=s.hit_count+s.miss_count;const uint64_t salt=diff?0xd1ff3e5a7b9c2046ULL:0xa110ca7e5319bdf2ULL;
        const uint64_t key=phaseAMix(seed_^static_cast<uint64_t>(q)^salt);auto& pool=samples_[bin*2+diff];const size_t limit=diff?4:2;
        auto worst=std::max_element(pool.begin(),pool.end(),[](const PhaseASample&a,const PhaseASample&b){return a.key!=b.key?a.key<b.key:a.q<b.q;});
        if(pool.size()>=limit && (key>worst->key || (key==worst->key && q>=worst->q)))return;
        std::ostringstream o;o<<std::setprecision(17)<<"{\"kind\":\""<<(diff?"different":"all")<<"\",\"stratum\":"<<bin<<",\"key\":"<<key<<",\"q\":"<<q<<",\"callback_index\":"<<callbacks_<<",\"op\":"<<op<<",\"pid\":"<<pid<<",\"memory\":"<<s.memory_limit<<",\"used\":"<<s.memory_used<<",\"target_size\":"<<s.operators[op].partitions[pid].data_size<<",\"write_bandwidth\":"<<s.write_bandwidth<<",\"read_bandwidth\":"<<s.read_bandwidth<<",\"next_id\":"<<(s.next_op.type=="PROBE"?s.next_op.op_id*s.num_partitions+s.next_op.key%s.num_partitions:-1)<<",\"eligible\":"<<p.eligible<<",\"reason\":"<<p.reason<<",\"different\":"<<p.different<<",\"chosen_dynamic\":"<<p.chosen<<",\"immediate\":"<<p.immediate<<",\"mean\":"<<p.mean<<",\"sd\":"<<p.sd<<",\"effective\":"<<p.effective<<",\"margin\":"<<p.margin<<",\"coverage\":"<<coverage_.json()<<",\"history\":";
        actionsJson(o,p.history);o<<",\"dynamic\":";actionsJson(o,p.dynamic);o<<",\"actual\":";actionsJson(o,actual);
        std::vector<int> ids;for(const auto& a:p.history)ids.push_back(a.op_id*s.num_partitions+a.partition_id);for(const auto& a:p.dynamic)ids.push_back(a.op_id*s.num_partitions+a.partition_id);std::sort(ids.begin(),ids.end());ids.erase(std::unique(ids.begin(),ids.end()),ids.end());
        o<<",\"probabilities\":[";for(size_t i=0;i<ids.size();++i){if(i)o<<',';o<<'['<<ids[i]<<','<<base_.phaseAProbability(ids[i])<<']';}o<<"]}";
        PhaseASample item{key,q,o.str()};if(pool.size()<limit)pool.push_back(item);else *worst=item;
    }
    std::vector<Action> call(const SystemState& s,char tag,int op=-1,int pid=-1,int64_t z=0) {
        const bool first=coverage_.before(s,tag,op,pid);
        if(first){std::cerr<<"PA_SIZES "<<s.operators.size()<<' '<<s.num_partitions;for(const auto& o:s.operators)for(const auto& p:o.partitions)std::cerr<<' '<<p.data_size;std::cerr<<'\n';}
        base_.resetPhaseA();std::vector<Action> a;
        if(tag=='O')a=base_.onMemoryOverflow(s,op,pid,z);else if(tag=='M')a=base_.onPartitionMiss(s,op,pid);else a=base_.onPeriodicAdjust(s);
        coverage_.after(s,tag,a);
        if(tag=='M' && coverage_.active && s.operators[op].partitions[pid].data_size>s.memory_limit-s.memory_used) {
            const auto& p=base_.phaseAInfo();const int64_t q=s.hit_count+s.miss_count;const int bin=stratum(q);bins_[bin].add(p);
            std::cerr<<std::setprecision(17)<<"PA_GATE "<<q<<' '<<bin<<' '<<p.eligible<<' '<<p.different<<' '<<p.chosen<<' '<<p.reason<<' '<<p.margin<<'\n';
            sample(s,op,pid,p,a,bin,false);if(p.different)sample(s,op,pid,p,a,bin,true);
        }
        ++callbacks_;return a;
    }
public:
    std::vector<Action> onMemoryOverflow(const SystemState&s,int op,int pid,int64_t z)override{return call(s,'O',op,pid,z);}
    std::vector<Action> onPartitionMiss(const SystemState&s,int op,int pid)override{return call(s,'M',op,pid);}
    std::vector<Action> onPeriodicAdjust(const SystemState&s)override{return call(s,'P');}
    ~PhaseAWrapper(){
        for(auto& pool:samples_){std::sort(pool.begin(),pool.end(),[](const PhaseASample&a,const PhaseASample&b){return a.q<b.q;});for(const auto& s:pool)std::cerr<<"PA_SAMPLE "<<s.json<<'\n';}
        std::cerr<<"PA_SUMMARY {\"callbacks\":"<<callbacks_<<",\"coverage\":"<<coverage_.json()<<",\"bins\":[";for(int j=0;j<4;++j)std::cerr<<(j?",":"")<<bins_[j].json();std::cerr<<"]}\n";
    }
};
