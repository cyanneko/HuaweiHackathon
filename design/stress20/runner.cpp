// Independent, strict replay engine using the real C++ scheduler headers.
#include <algorithm>
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
#include <tuple>
#include <vector>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <psapi.h>
#pragma comment(lib,"Psapi.lib")
#endif

enum class Phase { BUILD, PROBE };
struct PartitionState {int partition_id=-1;int64_t data_size=0;bool in_memory=true;};
struct OperatorState {int op_id;Phase phase=Phase::BUILD;std::vector<PartitionState> partitions;};
struct PendingOp {std::string type;int op_id=-1;int64_t key=0,tuple_size=0;};
struct SystemState {
    int64_t memory_used,memory_limit;int num_partitions;double write_bandwidth,read_bandwidth;
    int64_t hit_count,miss_count,total_io_bytes;std::vector<OperatorState> operators;PendingOp next_op;
};
struct Action {enum Type {SPILL,LOAD}type;int op_id,partition_id;Action(Type t,int o,int p):type(t),op_id(o),partition_id(p){}};
class SpillScheduler {
public:
    virtual ~SpillScheduler()=default;
    virtual std::vector<Action> onMemoryOverflow(const SystemState&,int,int,int64_t)=0;
    virtual std::vector<Action> onPartitionMiss(const SystemState&,int,int)=0;
    virtual std::vector<Action> onPeriodicAdjust(const SystemState&)=0;
};
#include "../CostAwareScheduler.hpp"
#include "../CostAwareSchedulerV2.hpp"
#include "../PrefixScheduler.hpp"

class Naive final:public SpillScheduler {
    bool literal_;
    std::vector<Action> plan(const SystemState& s,int o,int p,int64_t need,bool insert) {
        std::vector<std::tuple<int64_t,int,int>> c;
        for(const auto& op:s.operators)for(const auto& x:op.partitions)
            if(x.in_memory && x.data_size>0 && ((literal_ && insert)||!(op.op_id==o && x.partition_id==p)))
                c.emplace_back(x.data_size,op.op_id,x.partition_id);
        if(literal_)std::sort(c.begin(),c.end(),[](const auto& a,const auto& b){return std::get<0>(a)>std::get<0>(b);});
        else std::sort(c.rbegin(),c.rend());
        std::vector<Action> a;int64_t avail=s.memory_limit-s.memory_used;
        for(const auto& x:c) {if(avail>=need)break;a.emplace_back(Action::SPILL,std::get<1>(x),std::get<2>(x));avail+=std::get<0>(x);}
        if(avail<need)throw std::runtime_error("No feasible eviction");
        return a;
    }
public:
    explicit Naive(bool literal=false):literal_(literal){}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t n)override{return plan(s,o,p,n,true);}
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{auto a=plan(s,o,p,s.operators[o].partitions[p].data_size,false);a.emplace_back(Action::LOAD,o,p);return a;}
    std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};
struct Op {int type,o;int64_t key,size;}; // INSERT=0, SWITCH=1, PROBE=2
struct Input {int k,p,b,penalty;int64_t m;double w,r;std::vector<Op> ops;bool formal;};
static Input read_input(const std::string& path) {
    std::ifstream f(path);if(!f)throw std::runtime_error("Cannot open input");
    Input x;int64_t n; if(!(f>>x.k>>x.p>>x.m>>x.w>>x.r>>x.penalty>>n>>x.b))throw std::runtime_error("Bad header");
    if(x.k<1||x.k>8||x.p<2||x.p>64||n<1||n>5000000||x.b<1||x.b>10000||x.w<1||x.w>10000||x.r<1||x.r>10000||x.penalty<1||x.penalty>1000)throw std::runtime_error("Invalid input range");
    x.formal=x.m>=67108864LL && x.m<=4294967296LL;
    std::vector<int64_t> bc(x.k),pc(x.k),ba(x.k),pa(x.k);
    std::vector<bool> phase(x.k,false),seen(x.k,false);
    for(int i=0;i<x.k;++i) {int o;int64_t a,b;f>>o>>a>>b;if(o<0||o>=x.k||seen[o]||a<0||b<0)throw std::runtime_error("Bad metadata");seen[o]=true;bc[o]=a;pc[o]=b;}
    x.ops.reserve(size_t(n));
    for(int64_t i=0;i<n;++i) {
        std::string t;Op op{0,0,0,0};if(!(f>>t>>op.o)||op.o<0||op.o>=x.k)throw std::runtime_error("Bad operation");
        if(t=="SWITCH") {op.type=1;if(phase[op.o])throw std::runtime_error("Duplicate switch");phase[op.o]=true;}
        else if(t=="INSERT") {f>>op.key>>op.size;if(phase[op.o]||op.size<1||op.size>1048576)throw std::runtime_error("Invalid insert");++ba[op.o];}
        else if(t=="PROBE") {op.type=2;f>>op.key;if(!phase[op.o])throw std::runtime_error("Probe before switch");++pa[op.o];}
        else throw std::runtime_error("Unknown operation");
        if(!f||op.key<0||op.key>1000000000LL)throw std::runtime_error("Invalid operation argument");
        x.ops.push_back(op);
    }
    std::string trailing;if(f>>trailing)throw std::runtime_error("Trailing operations after N");
    if(ba!=bc||pa!=pc)throw std::runtime_error("Metadata count mismatch");
    return x;
}
static PendingOp pending(const Op& o){PendingOp a;a.type=o.type==0?"INSERT":o.type==1?"SWITCH":"PROBE";a.op_id=o.o;a.key=o.key;a.tuple_size=o.size;return a;}
static std::unique_ptr<SpillScheduler> make_policy(const std::string& name,int penalty){
    if(name=="naive")return std::make_unique<Naive>();
    if(name=="literal_naive")return std::make_unique<Naive>(true);
    if(name=="legacy_no_prefetch")return std::make_unique<CostAwareScheduler>(penalty,false);
    if(name=="legacy")return std::make_unique<CostAwareScheduler>(penalty,true);
    if(name=="lazy_equivalent")return std::make_unique<CostAwareSchedulerV2>(penalty,true,false,false,false);
    if(name=="v2")return std::make_unique<CostAwareSchedulerV2>(penalty,true,false,true,false);
    if(name=="protect")return std::make_unique<CostAwareSchedulerV2>(penalty,true,true,true,false);
    if(name=="aggressive")return std::make_unique<CostAwareSchedulerV2>(penalty,true,true,true,true);
    if(name=="prefix")return std::make_unique<PrefixScheduler>(penalty);
    throw std::runtime_error("Unknown policy");
}
static std::string quote(std::string s){std::string r="\"";for(char c:s){if(c=='\\'||c=='\"')r+='\\';r+=(c=='\n'?' ':c);}return r+'\"';}
static void run(const Input& in,const std::string& name,bool strict,const std::string& trace_path) {
    auto policy=make_policy(name,in.penalty);
    std::vector<OperatorState> operators;
    for(int o=0;o<in.k;++o){OperatorState a;a.op_id=o;for(int p=0;p<in.p;++p){PartitionState z;z.partition_id=p;a.partitions.push_back(z);}operators.push_back(a);}
    int64_t used=0,hit=0,miss=0,wr=0,rd=0,peak=0,count=0,spills=0,loads=0,callbacks=0,step=-1;
    int64_t max_partition=0;uint64_t digest=1469598103934665603ULL;
    double io=0;std::string error;
    std::ofstream trace;if(!trace_path.empty())trace.open(trace_path);
    auto start=std::chrono::steady_clock::now();
    auto check=[&](){
        if(used<0||used>in.m)throw std::runtime_error("Memory limit violation");
        peak=std::max(peak,used);
        if(strict || count%4096==0){int64_t actual=0;for(const auto& o:operators)for(const auto& p:o.partitions)if(p.in_memory)actual+=p.data_size;if(actual!=used)throw std::runtime_error("Resident byte accounting mismatch (INSERT target spilled)");}
    };
    auto execute=[&](const std::vector<Action>& a,bool overflow){
        for(const auto& ac:a){
            if(ac.op_id<0||ac.op_id>=in.k||ac.partition_id<0||ac.partition_id>=in.p)throw std::runtime_error("Invalid action index");
            if(overflow && ac.type!=Action::SPILL)throw std::runtime_error("LOAD in overflow callback");
            auto& p=operators[ac.op_id].partitions[ac.partition_id];
            // The reference skips no-op actions. Track the same effective state.
            if(ac.type==Action::SPILL){if(!p.in_memory||p.data_size==0)continue;used-=p.data_size;p.in_memory=false;wr+=p.data_size;io+=double(p.data_size)/in.w;++spills;}
            else {if(operators[ac.op_id].phase!=Phase::PROBE)throw std::runtime_error("LOAD during BUILD");if(p.in_memory)continue;if(used+p.data_size>in.m)throw std::runtime_error("LOAD exceeds memory");used+=p.data_size;p.in_memory=true;rd+=p.data_size;io+=double(p.data_size)/in.r;++loads;}
            digest^=(uint64_t(ac.type)*512+ac.op_id*64+ac.partition_id);digest*=1099511628211ULL;
            if(trace)trace<<step+1<<','<<(ac.type==Action::SPILL?"SPILL":"LOAD")<<','<<ac.op_id<<','<<ac.partition_id<<','<<p.data_size<<','<<used<<'\n';
            check();
        }
    };
    try{
        for(step=0;step<int64_t(in.ops.size());++step){
            const auto& o=in.ops[size_t(step)];int p=int(o.key%in.p);
            PendingOp next=step+1<int64_t(in.ops.size())?pending(in.ops[size_t(step+1)]):PendingOp{};
            auto state=[&](){++callbacks;return SystemState{used,in.m,in.p,in.w,in.r,hit,miss,wr+rd,operators,next};};
            auto& part=operators[o.o].partitions[p];
            if(o.type==1){operators[o.o].phase=Phase::PROBE;continue;}
            if(o.type==0){
                if(part.in_memory){
                    if(used+o.size>in.m){auto a=policy->onMemoryOverflow(state(),o.o,p,o.size);execute(a,true);if(used+o.size>in.m)throw std::runtime_error("INSERT exceeds memory");}
                    part.data_size+=o.size;used+=o.size; // Faithful to the reference's branch decision.
                }else{part.data_size+=o.size;wr+=o.size;io+=double(o.size)/in.w;}
                max_partition=std::max(max_partition,part.data_size);
            }else if(part.in_memory)++hit;
            else{++miss;auto a=policy->onPartitionMiss(state(),o.o,p);if(a.empty()||a.back().type!=Action::LOAD||a.back().op_id!=o.o||a.back().partition_id!=p)throw std::runtime_error("Miss callback last action must LOAD target");execute(a,false);if(!part.in_memory)throw std::runtime_error("Missing target after callback");}
            ++count;check();
            if(count%in.b==0){auto a=policy->onPeriodicAdjust(state());execute(a,false);}
        }
    }catch(const std::exception& e){error=e.what();}
    double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    uint64_t peak_working_set=0;
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS pmc{};
    if(GetProcessMemoryInfo(GetCurrentProcess(),&pmc,sizeof(pmc)))peak_working_set=pmc.PeakWorkingSetSize;
#endif
    std::cout<<std::setprecision(17)<<"{\"policy\":"<<quote(name)<<",\"ok\":"<<(error.empty()?"true":"false")<<",\"error\":"<<quote(error)
        <<",\"step\":"<<step+1<<",\"score\":"<<io+in.penalty*double(miss)<<",\"io\":"<<io<<",\"hit\":"<<hit<<",\"miss\":"<<miss
        <<",\"write_bytes\":"<<wr<<",\"read_bytes\":"<<rd<<",\"peak\":"<<peak<<",\"spills\":"<<spills<<",\"loads\":"<<loads
        <<",\"callbacks\":"<<callbacks<<",\"action_digest\":"<<quote(std::to_string(digest))<<",\"max_partition\":"<<max_partition<<",\"run_ms\":"<<ms<<",\"peak_process_working_set\":"<<peak_working_set<<"}"<<std::endl;
}
int main(int argc,char** argv){
    try{
        if(argc<3){std::cerr<<"runner input.txt policy[,policy...] [fast] [trace.csv]\n";return 2;}
        auto in=read_input(argv[1]);std::istringstream names(argv[2]);std::string name;
        bool strict=!(argc>3 && std::string(argv[3])=="fast");
        while(std::getline(names,name,','))run(in,name,strict,argc>4?argv[4]:"");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 2;}
}
