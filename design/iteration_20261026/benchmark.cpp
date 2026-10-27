#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#define NOMINMAX
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#pragma comment(lib,"Psapi.lib")
#endif
#include "reference_types.hpp"
#include "MySpillScheduler.cpp"
#define MySpillScheduler ScoreFirstModel
#include "MySpillScheduler_score_first.cpp"
#undef MySpillScheduler
#include "../CostAwareScheduler.hpp"
#include "../PrefixScheduler.hpp"

struct Op {int type,o;int64_t key,size;};
struct Input {int k,p,b,penalty;int64_t m;double w,r;std::vector<Op> ops;int64_t probes=0;};
static Input read_input(const std::string& path){
    std::ifstream f(path);Input x;int64_t n;
    if(!(f>>x.k>>x.p>>x.m>>x.w>>x.r>>x.penalty>>n>>x.b))throw std::runtime_error("Bad header");
    if(x.k<1||x.k>8||x.p<2||x.p>64||n<1||n>5000000||x.b<1||x.b>10000)throw std::runtime_error("Bad limits");
    std::vector<int64_t> nb(x.k),np(x.k),ba(x.k),pa(x.k),sizes(x.k*x.p);
    std::vector<bool> phase(x.k,false),seen(x.k,false);
    for(int i=0;i<x.k;++i){int o;int64_t a,b;f>>o>>a>>b;if(o<0||o>=x.k||seen[o])throw std::runtime_error("Bad metadata");seen[o]=true;nb[o]=a;np[o]=b;}
    x.ops.reserve(size_t(n));
    for(int64_t i=0;i<n;++i){
        std::string t;Op z{0,0,0,0};if(!(f>>t>>z.o)||z.o<0||z.o>=x.k)throw std::runtime_error("Bad op");
        if(t=="SWITCH"){z.type=1;if(phase[z.o])throw std::runtime_error("Duplicate switch");phase[z.o]=true;}
        else if(t=="INSERT"){f>>z.key>>z.size;if(phase[z.o]||z.size<1||z.size>1048576)throw std::runtime_error("Bad insert");++ba[z.o];sizes[z.o*x.p+z.key%x.p]+=z.size;}
        else if(t=="PROBE"){z.type=2;f>>z.key;if(!phase[z.o])throw std::runtime_error("Early probe");++pa[z.o];++x.probes;}
        else throw std::runtime_error("Unknown op");
        if(!f||z.key<0||z.key>1000000000)throw std::runtime_error("Bad arguments");x.ops.push_back(z);
    }
    std::string extra;if(f>>extra)throw std::runtime_error("N mismatch");
    if(nb!=ba||np!=pa)throw std::runtime_error("Metadata mismatch");
    for(auto s:sizes)if(s>x.m)throw std::runtime_error("Partition exceeds M, forbidden by revised statement");
    return x;
}
static PendingOp pending(const Op& z){PendingOp p;p.type=z.type==0?"INSERT":z.type==1?"SWITCH":"PROBE";p.op_id=z.o;p.key=z.key;p.tuple_size=z.size;return p;}
static std::string quote(const std::string& s){std::string r="\"";for(char c:s){if(c=='\\'||c=='\"')r+='\\';r+=(c=='\n'?' ':c);}return r+'\"';}
static void run(const Input& in,const std::string& path,const std::string& name,bool strict){
    std::unique_ptr<SpillScheduler> policy;
    if(name=="baseline")policy.reset(new NaiveSpillScheduler());
    else if(name=="recommended")policy.reset(new MySpillScheduler());
    else if(name=="score_first")policy.reset(new ScoreFirstModel());
    else if(name=="old_prior32")policy.reset(new CostAwareScheduler(32.0));
    else if(name=="prefix_prior1")policy.reset(new PrefixScheduler(1.0));
    else policy.reset(new MySpillScheduler(name=="learned"?-1:std::stoi(name)));
    std::vector<OperatorState> ops;
    for(int o=0;o<in.k;++o){OperatorState a;a.op_id=o;a.phase=Phase::BUILD;a.partitions.resize(in.p);for(int p=0;p<in.p;++p)a.partitions[p].partition_id=p;ops.push_back(a);}
    int64_t used=0,hit=0,miss=0,wr=0,rd=0,count=0,peak=0,callbacks=0,spills=0,loads=0;
    double io=0,decision=0;std::string error;int64_t step=0;
    auto begin=std::chrono::steady_clock::now();
    auto check=[&](){if(used<0||used>in.m)throw std::runtime_error("Capacity violation");peak=std::max(peak,used);
        if(strict||count%4096==0){int64_t actual=0;for(const auto& o:ops)for(const auto& p:o.partitions)if(p.in_memory)actual+=p.data_size;if(actual!=used)throw std::runtime_error("Resident ledger mismatch");}};
    auto execute=[&](const std::vector<Action>& actions,int overflow_o,int overflow_p){
        for(const auto& a:actions){
            if(a.op_id<0||a.op_id>=in.k||a.partition_id<0||a.partition_id>=in.p)throw std::runtime_error("Action index");
            if(overflow_o>=0&&(a.type!=Action::SPILL||(a.op_id==overflow_o&&a.partition_id==overflow_p)))throw std::runtime_error("Illegal overflow action");
            auto& p=ops[a.op_id].partitions[a.partition_id];
            if(a.type==Action::SPILL){if(!p.in_memory||p.data_size==0)continue;wr+=p.data_size;io+=double(p.data_size)/in.w;used-=p.data_size;p.in_memory=false;++spills;}
            else{if(ops[a.op_id].phase!=Phase::PROBE)throw std::runtime_error("LOAD during BUILD");if(p.in_memory)continue;if(used+p.data_size>in.m)throw std::runtime_error("LOAD OOM");rd+=p.data_size;io+=double(p.data_size)/in.r;used+=p.data_size;p.in_memory=true;++loads;}
            check();
        }
    };
    try{
        for(step=0;step<int64_t(in.ops.size());++step){
            const auto& z=in.ops[size_t(step)];int pid=int(z.key%in.p);
            if(z.type==1){ops[z.o].phase=Phase::PROBE;continue;}
            PendingOp next=step+1<int64_t(in.ops.size())?pending(in.ops[size_t(step+1)]):PendingOp{};
            auto state=[&](){return SystemState{used,in.m,in.p,in.w,in.r,hit,miss,wr+rd,ops,next};};
            // Same measured region as the published timedSchedulerCall: includes
            // getSystemState()'s by-value snapshot, which is inside its lambda.
            auto call=[&](int kind)->std::vector<Action>{
                ++callbacks;auto t0=std::chrono::high_resolution_clock::now();
                auto a=kind==0?policy->onMemoryOverflow(state(),z.o,pid,z.size):kind==1?policy->onPartitionMiss(state(),z.o,pid):policy->onPeriodicAdjust(state());
                auto t1=std::chrono::high_resolution_clock::now();decision+=std::chrono::duration<double,std::micro>(t1-t0).count();return a;
            };
            auto& p=ops[z.o].partitions[pid];
            if(z.type==0){
                if(p.in_memory){if(used+z.size>in.m){auto a=call(0);execute(a,z.o,pid);if(used+z.size>in.m)throw std::runtime_error("INSERT OOM");}used+=z.size;p.data_size+=z.size;}
                else{p.data_size+=z.size;wr+=z.size;io+=double(z.size)/in.w;}
            }else if(p.in_memory)++hit;
            else{++miss;auto a=call(1);if(a.empty()||a.back().type!=Action::LOAD||a.back().op_id!=z.o||a.back().partition_id!=pid)throw std::runtime_error("Last action must LOAD target");execute(a,-1,-1);if(!p.in_memory)throw std::runtime_error("Unloaded target");}
            ++count;check();if(count%in.b==0){auto a=call(2);execute(a,-1,-1);}
        }
    }catch(const std::exception& e){error=e.what();}
    double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
    uint64_t rss=0;
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS pmc{};if(GetProcessMemoryInfo(GetCurrentProcess(),&pmc,sizeof(pmc)))rss=pmc.PeakWorkingSetSize;
#endif
    std::cout<<std::setprecision(17)<<"{\"input\":"<<quote(path)<<",\"policy\":"<<quote(name)<<",\"ok\":"<<(error.empty()?"true":"false")<<",\"error\":"<<quote(error)
        <<",\"io\":"<<io<<",\"decision_us\":"<<decision<<",\"score\":"<<io+in.penalty*double(miss)+decision<<",\"hit\":"<<hit<<",\"miss\":"<<miss<<",\"write_bytes\":"<<wr<<",\"read_bytes\":"<<rd
        <<",\"peak\":"<<peak<<",\"callbacks\":"<<callbacks<<",\"spills\":"<<spills<<",\"loads\":"<<loads<<",\"wall_s\":"<<wall<<",\"rss\":"<<rss;
    auto mine=dynamic_cast<MySpillScheduler*>(policy.get());
    auto first=dynamic_cast<ScoreFirstModel*>(policy.get());
    std::cout<<",\"selected_mode\":"<<(mine?mine->selectedMode():first?first->selectedMode():-9)<<",\"thrashing_detected\":"<<(mine&&mine->detectedThrashing()?"true":"false")<<",\"has_features\":"<<((mine&&mine->hasDecision())||(first&&first->hasDecision())?"true":"false")<<",\"features\":[";
    auto feat=mine?mine->featureSnapshot():first?first->featureSnapshot():std::array<double,16>{};for(int i=0;i<16;++i){if(i)std::cout<<',';std::cout<<feat[i];}
    std::cout<<"]}"<<std::endl;
}
int main(int argc,char** argv){
    try{
        if(argc<3)return 2;
        bool batch=std::string(argv[1])=="--batch";
        std::string policy_arg=argv[batch?3:2];bool strict=!(argc>(batch?4:3)&&std::string(argv[batch?4:3])=="fast");
        std::vector<std::string> paths;if(batch){std::ifstream list(argv[2]);std::string p;while(std::getline(list,p))if(!p.empty())paths.push_back(p);}else paths.push_back(argv[1]);
        for(const auto& path:paths){auto in=read_input(path);std::istringstream names(policy_arg);std::string name;while(std::getline(names,name,','))run(in,path,name,strict);}
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 2;}
}
