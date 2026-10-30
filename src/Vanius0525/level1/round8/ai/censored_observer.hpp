// Diagnostic-only legal observer. No request-file access or ordinary-Hit callback.
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
class CensoredObserver {
    bool initialized_=false;
    int64_t last_q_=0,last_h_=0,last_m_=0,pending_q_=-1,last_exact_q_=-1;
    int pending_id_=-1,last_exact_id_=-1;
    std::vector<bool> after_;
    int64_t segments_=0,anonymous_=0,exact_=0,duplicates_=0,known_hits_=0,prefetched_hits_=0;
    bool pending_prefetched_=false;
    void exact(int64_t q,int id,char source) {
        if(q==last_exact_q_) {
            if(id!=last_exact_id_)throw std::runtime_error("same PROBE ordinal, different identity");
            ++duplicates_;return;
        }
        if(q<last_exact_q_)throw std::runtime_error("nonmonotone exact observation");
        last_exact_q_=q;last_exact_id_=id;++exact_;
        std::cerr<<"CS_EXACT "<<q<<' '<<id<<' '<<source<<'\n';
    }
public:
    void observe(const SystemState& s,char tag,int op,int pid,const std::vector<Action>& actions) {
        bool all_probe=true;for(const auto& o:s.operators)if(o.phase!=Phase::PROBE)all_probe=false;
        if(!all_probe){initialized_=false;pending_q_=-1;return;}
        const int n=s.operators.size()*s.num_partitions;
        std::vector<bool> before(n,false);
        for(const auto& o:s.operators)for(const auto& x:o.partitions)
            before[o.op_id*s.num_partitions+x.partition_id]=x.in_memory;
        const int64_t q=s.hit_count+s.miss_count;
        if(initialized_) {
            if(before!=after_)throw std::runtime_error("unstable resident set between callbacks");
            const int64_t dh=s.hit_count-last_h_,dm=s.miss_count-last_m_;
            if(dh<0 || dm<0 || dm!=(tag=='M'?1:0))throw std::runtime_error("unaccounted miss or reversed clock");
            const bool known_executed=pending_q_>last_q_ && pending_q_<=q;
            const bool known_hit=known_executed && after_[pending_id_];
            const int64_t hidden=dh-static_cast<int>(known_hit);
            if(hidden<0)throw std::runtime_error("known Hit exceeded aggregate Hit delta");
            if(q>last_q_) {
                std::string mask;for(bool x:after_)mask+=x?'1':'0';
                std::cerr<<"CS_SEG "<<last_q_<<' '<<q<<' '<<hidden<<' '
                         <<(known_executed?pending_q_:-1)<<' '<<(known_executed?pending_id_:-1)<<' '
                         <<(tag=='M'?q:-1)<<' '<<(tag=='M'?op*s.num_partitions+pid:-1)<<' '<<mask<<'\n';
                ++segments_;anonymous_+=hidden;known_hits_+=known_hit;
                prefetched_hits_+=known_hit && pending_prefetched_;
            }
        }
        if(tag=='M')exact(q,op*s.num_partitions+pid,'M');
        pending_q_=-1;pending_id_=-1;pending_prefetched_=false;
        if(s.next_op.type=="PROBE") {
            pending_q_=q+1;pending_id_=s.next_op.op_id*s.num_partitions+s.next_op.key%s.num_partitions;
            exact(pending_q_,pending_id_,'N');
        }
        after_=before;
        for(const auto& a:actions) {
            const int id=a.op_id*s.num_partitions+a.partition_id;
            after_[id]=a.type==Action::LOAD;
            if(id==pending_id_ && a.type==Action::LOAD)pending_prefetched_=true;
        }
        last_q_=q;last_h_=s.hit_count;last_m_=s.miss_count;initialized_=true;
    }
    ~CensoredObserver() {
        std::cerr<<"CS_STAT "<<segments_<<' '<<anonymous_<<' '<<exact_<<' '
                 <<duplicates_<<' '<<known_hits_<<' '<<prefetched_hits_<<'\n';
    }
};
