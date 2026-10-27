#pragma once
#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <vector>

// Conservative alternative after broad testing exposed BUILD prediction failures.
// BUILD uses the deterministic safe largest-first baseline. At a PROBE miss,
// compare legal plans for exactly the known (current,next) pair. Accept a joint
// plan only if its end cache contains the simulated baseline end cache and its
// exact two-request score is lower. No access to hits or to more future input.
// This is a LOCAL comparison, not a global competitive-ratio guarantee.
class PrefixScheduler final : public SpillScheduler {
    double penalty_;
    struct Flat {
        std::vector<int64_t> size;
        std::vector<bool> mem;
        int64_t used,limit;
        int width;
    };
    static Flat flat(const SystemState& s) {
        Flat f;f.used=s.memory_used;f.limit=s.memory_limit;f.width=s.num_partitions;
        for(const auto& o:s.operators)for(const auto& p:o.partitions){f.size.push_back(p.data_size);f.mem.push_back(p.in_memory);}
        return f;
    }
    static std::vector<int> cover(const Flat& f,int64_t need,int target,int protect=-1,bool minwrite=false) {
        int64_t deficit=need-(f.limit-f.used);
        if(deficit<=0)return {};
        std::vector<int> c;
        for(int i=0;i<int(f.size.size());++i)if(f.mem[i] && f.size[i]>0 && i!=target && i!=protect)c.push_back(i);
        std::sort(c.begin(),c.end(),[&](int a,int b){if(f.size[a]!=f.size[b])return f.size[a]>f.size[b];return a>b;});
        std::vector<int> best;int64_t freed=0;
        for(int i:c){best.push_back(i);freed+=f.size[i];if(freed>=deficit)break;}
        if(freed<deficit)throw std::runtime_error("No feasible protected-target allocation");
        if(minwrite){
            for(int i:c)if(f.size[i]>=deficit && f.size[i]<freed){best={i};freed=f.size[i];}
            std::vector<int> ascending_cover;int64_t total=0;
            for(auto it=c.rbegin();it!=c.rend();++it){ascending_cover.push_back(*it);total+=f.size[*it];if(total>=deficit)break;}
            if(total>=deficit && total<freed){best=ascending_cover;freed=total;}
            std::vector<int> compact;
            for(int i:best)if(freed-f.size[i]>=deficit)freed-=f.size[i];else compact.push_back(i);
            best=compact;
        }
        return best;
    }
    static double evict(Flat& f,const std::vector<int>& ids,double w){
        double cost=0;for(int i:ids){cost+=double(f.size[i])/w;f.used-=f.size[i];f.mem[i]=false;}return cost;
    }
    static double load(Flat& f,int id,double r){if(f.mem[id])return 0;f.mem[id]=true;f.used+=f.size[id];return double(f.size[id])/r;}
    static std::vector<Action> actions(const std::vector<int>& ids,int width){
        std::vector<Action> a;for(int id:ids)a.emplace_back(Action::SPILL,id/width,id%width);return a;
    }
public:
    explicit PrefixScheduler(double miss_penalty):penalty_(miss_penalty){}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t size)override{
        return actions(cover(flat(s),size,o*s.num_partitions+p),s.num_partitions);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{
        auto f=flat(s);int a=o*f.width+p;
        auto base_v=cover(f,f.size[a],a);
        auto base_actions=actions(base_v,f.width);base_actions.emplace_back(Action::LOAD,o,p);
        if(s.next_op.type!="PROBE")return base_actions;
        int no=s.next_op.op_id,np=int(s.next_op.key%f.width),b=no*f.width+np;
        if(a==b || s.operators[no].phase!=Phase::PROBE || f.size[a]+f.size[b]>f.limit)return base_actions;
        // Exact baseline trajectory through the NEXT request, with largest-first
        // victims at that request; the current miss penalty is common to both.
        auto baseline=f;
        double best=evict(baseline,base_v,s.write_bandwidth)+load(baseline,a,s.read_bandwidth);
        if(!baseline.mem[b]){
            auto next_v=cover(baseline,baseline.size[b],b);
            best+=evict(baseline,next_v,s.write_bandwidth)+load(baseline,b,s.read_bandwidth)+penalty_;
        }
        auto chosen=base_actions;
        for(bool minwrite:{false,true}){
            auto joint=f;
            int64_t need=f.size[a]+(f.mem[b]?0:f.size[b]);
            auto victims=cover(joint,need,a,b,minwrite);
            double cost=evict(joint,victims,s.write_bandwidth);
            cost+=load(joint,b,s.read_bandwidth)+load(joint,a,s.read_bandwidth);
            bool contains=true;
            for(size_t i=0;i<joint.mem.size();++i)if(baseline.mem[i] && !joint.mem[i]){contains=false;break;}
            if(contains && cost+1e-9<best){
                best=cost;chosen=actions(victims,f.width);
                if(!f.mem[b])chosen.emplace_back(Action::LOAD,no,np);
                chosen.emplace_back(Action::LOAD,o,p);
            }
        }
        return chosen;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s)override{
        if(s.next_op.type!="PROBE")return {};
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
        const auto& x=s.operators[o].partitions[p];
        if(s.operators[o].phase!=Phase::PROBE || x.in_memory || x.data_size>s.memory_limit-s.memory_used)return {};
        return {Action(Action::LOAD,o,p)}; // No extra SPILL to prefetch.
    }
};
