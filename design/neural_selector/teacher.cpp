// Offline-only counterfactual teacher. Future input is NEVER part of deployed features.
#include <algorithm>
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
#include "reference_types.hpp"
#include "../MySpillScheduler_neural.cpp"
struct Operation {int kind,o,p;int64_t key,bytes;};
struct Input {int k,p,b,pen;int64_t m;double w,r;std::vector<Operation> rows;std::array<int,8> switched;};
static std::string quoted(const std::string& s){std::string r="\"";for(char c:s){if(c=='\\'||c=='\"')r+='\\';r+=c;}return r+'\"';}
static Input read(const std::string& path){
    std::ifstream f(path);Input x;int64_t n;if(!(f>>x.k>>x.p>>x.m>>x.w>>x.r>>x.pen>>n>>x.b))throw std::runtime_error("header");
    if(x.k<1||x.k>8||x.p<2||x.p>64||n<1||n>5000000||x.b<1||x.b>10000||x.m<64LL*1024*1024||x.m>4LL*1024*1024*1024||x.w<1||x.w>10000||x.r<1||x.r>10000||x.pen<1||x.pen>1000)throw std::runtime_error("limits");
    std::array<int64_t,8> ba{},pa{},want_b{},want_p{};std::array<bool,8> phase{};std::vector<int64_t> size(x.k*x.p);x.switched.fill(int(n));
    for(int o=0;o<x.k;++o){int id;f>>id>>want_b[o]>>want_p[o];if(id!=o)throw std::runtime_error("metadata order");}
    for(int i=0;i<n;++i){std::string t;Operation z{};f>>t>>z.o;if(!f||z.o<0||z.o>=x.k)throw std::runtime_error("operator");
        if(t=="SWITCH"){z.kind=1;if(phase[z.o])throw std::runtime_error("duplicate switch");phase[z.o]=true;x.switched[z.o]=i;}
        else {f>>z.key;if(z.key<0||z.key>1000000000)throw std::runtime_error("key");z.p=int(z.key%x.p);
            if(t=="INSERT"){f>>z.bytes;if(phase[z.o]||z.bytes<1||z.bytes>1048576)throw std::runtime_error("insert");++ba[z.o];size[z.o*x.p+z.p]+=z.bytes;}
            else if(t=="PROBE"){z.kind=2;if(!phase[z.o])throw std::runtime_error("probe");++pa[z.o];}else throw std::runtime_error("type");}
        if(!f)throw std::runtime_error("truncated");x.rows.push_back(z);}
    if(ba!=want_b||pa!=want_p)throw std::runtime_error("counts");for(auto z:size)if(z>x.m)throw std::runtime_error("partition>M");std::string extra;if(f>>extra)throw std::runtime_error("extra");return x;
}
struct Point {int event,kind,pos;};
struct Simulator {
    const Input* input;MySpillScheduler policy;std::vector<OperatorState> ops;
    int pos=0,count=0,event=0;int64_t used=0,hit=0,miss=0,io_bytes=0;double io=0,cpu=0;uint64_t action_hash=1469598103934665603ULL;
    std::vector<Point>* points=nullptr;const std::vector<int>* selected=nullptr;std::ostream* labels=nullptr;std::string filename;
    int continuation=7;
    Simulator(const Input& x,int mode):input(&x),policy(mode){
        for(int o=0;o<x.k;++o){OperatorState op;op.op_id=o;op.phase=Phase::BUILD;for(int p=0;p<x.p;++p){PartitionState z;z.partition_id=p;op.partitions.push_back(z);}ops.push_back(op);}
    }
    SystemState state() const {const auto& x=*input;SystemState s;s.memory_used=used;s.memory_limit=x.m;s.num_partitions=x.p;s.write_bandwidth=x.w;s.read_bandwidth=x.r;s.hit_count=hit;s.miss_count=miss;s.total_io_bytes=io_bytes;s.operators=ops;
        if(pos+1<int(x.rows.size())){const auto& z=x.rows[pos+1];s.next_op.type=z.kind==0?"INSERT":z.kind==1?"SWITCH":"PROBE";s.next_op.op_id=z.o;s.next_op.key=z.key;s.next_op.tuple_size=z.bytes;}return s;}
    void actions(const std::vector<Action>& as,int exclude_o=-1,int exclude_p=-1){
        for(const auto& a:as){if(a.op_id<0||a.op_id>=input->k||a.partition_id<0||a.partition_id>=input->p)throw std::runtime_error("action id");auto& z=ops[a.op_id].partitions[a.partition_id];
            if(a.type==Action::SPILL){if(!z.in_memory||(a.op_id==exclude_o&&a.partition_id==exclude_p))throw std::runtime_error("illegal spill");z.in_memory=false;used-=z.data_size;io+=double(z.data_size)/input->w;}
            else {if(z.in_memory||ops[a.op_id].phase!=Phase::PROBE)throw std::runtime_error("illegal load");z.in_memory=true;used+=z.data_size;io+=double(z.data_size)/input->r;}
            io_bytes+=z.data_size;if(used<0||used>input->m)throw std::runtime_error("capacity");
            action_hash^=uint64_t(a.type*512+a.op_id*64+a.partition_id);action_hash*=1099511628211ULL;
        }
    }
    bool isChoice(int kind,const SystemState& s) const {if(kind<2)return true;if(s.next_op.type!="INSERT")return false;int o=s.next_op.op_id,p=int(s.next_op.key%input->p);return ops[o].partitions[p].in_memory&&s.next_op.tuple_size>input->m-used;}
    std::vector<Action> invoke(int kind,int o,int p,int64_t bytes){
        auto current=state();if(isChoice(kind,current)){
            if(points)points->push_back({event,kind,pos});
            if(labels&&selected&&std::binary_search(selected->begin(),selected->end(),event))label(kind,o,p,bytes,current);
            ++event;
        }
        auto start=std::chrono::steady_clock::now();std::vector<Action> as;
        if(kind==0)as=policy.onMemoryOverflow(state(),o,p,bytes);
        else if(kind==1)as=policy.onPartitionMiss(state(),o,p);
        else as=policy.onPeriodicAdjust(state());
        cpu+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();return as;
    }
    void finish(){if(++count%input->b==0)actions(invoke(2,-1,-1,0));++pos;}
    void step(){const auto& z=input->rows[pos];auto& part=ops[z.o].partitions[z.p];
        if(z.kind==1){ops[z.o].phase=Phase::PROBE;++pos;return;}
        if(z.kind==0){if(part.in_memory){if(used+z.bytes>input->m)actions(invoke(0,z.o,z.p,z.bytes),z.o,z.p);part.data_size+=z.bytes;used+=z.bytes;}
            else {part.data_size+=z.bytes;io+=double(z.bytes)/input->w;io_bytes+=z.bytes;}}
        else if(part.in_memory)++hit;else {++miss;auto as=invoke(1,z.o,z.p,part.data_size);if(as.empty()||as.back().type!=Action::LOAD||as.back().op_id!=z.o||as.back().partition_id!=z.p)throw std::runtime_error("last action");actions(as);}
        if(used>input->m)throw std::runtime_error("post-operation capacity");finish();
    }
    void run(int end){while(pos<end)step();}
    void label(int kind,int o,int p,int64_t bytes,const SystemState& current){
        int co=o,cp=p;if(kind==2){co=current.next_op.op_id;cp=int(current.next_op.key%input->p);bytes=current.next_op.tuple_size;}
        auto f=policy.features(current,co,cp,kind!=1,bytes);
        int end=std::min(int(input->rows.size()),pos+384);
        if(kind!=1)end=std::min(int(input->rows.size()),std::min(pos+2048,std::max(end,input->switched[co]+128)));
        std::array<double,8> costs{},timers{};std::array<int64_t,8> misses{};
        for(int e=0;e<8;++e){Simulator b=*this;b.points=nullptr;b.selected=nullptr;b.labels=nullptr;b.policy.setMode(continuation);b.policy.forceNext(e);
            auto as=b.invoke(kind,o,p,bytes);
            if(kind==0){b.actions(as,o,p);auto& t=b.ops[o].partitions[p];t.data_size+=bytes;b.used+=bytes;b.finish();}
            else if(kind==1){if(as.empty()||as.back().type!=Action::LOAD||as.back().op_id!=o||as.back().partition_id!=p)throw std::runtime_error("teacher last action");b.actions(as);b.finish();}
            else {b.actions(as);++b.pos;}
            b.run(end);timers[e]=b.cpu-cpu;misses[e]=b.miss-miss;costs[e]=b.io-io+input->pen*double(misses[e])+timers[e];
        }
        *labels<<std::setprecision(10)<<"{\"file\":"<<quoted(filename)<<",\"pos\":"<<pos<<",\"kind\":"<<kind<<",\"end\":"<<end<<",\"features\":[";
        for(int i=0;i<32;++i)*labels<<(i?",":"")<<f[i];*labels<<"],\"costs\":[";for(int i=0;i<8;++i)*labels<<(i?",":"")<<costs[i];
        *labels<<"],\"decision_us\":[";for(int i=0;i<8;++i)*labels<<(i?",":"")<<timers[i];*labels<<"],\"misses\":[";for(int i=0;i<8;++i)*labels<<(i?",":"")<<misses[i];*labels<<"]}\n";
    }
};
int main(int argc,char** argv){try{
    if(argc<4)return 2;std::ifstream list(argv[1]);std::ofstream out(argv[2]);int cap=std::stoi(argv[3]),mode=argc>4?std::stoi(argv[4]):7,files=0,continuation=argc>5?std::stoi(argv[5]):7;std::string path;
    while(std::getline(list,path)){if(!path.empty()&&path.back()=='\r')path.pop_back();if(path.empty())continue;Input x=read(path);std::vector<Point> pts;Simulator first(x,mode);first.points=&pts;first.run(int(x.rows.size()));
        std::vector<int> selected;for(int kind=0;kind<3;++kind){std::vector<int> group;for(const auto& p:pts)if(p.kind==kind)group.push_back(p.event);int take=std::min(int(group.size()),kind==1?cap:std::max(4,cap/3));
            for(int j=0;j<take;++j)selected.push_back(group[size_t(j)*group.size()/take]);}
        std::sort(selected.begin(),selected.end());Simulator second(x,mode);second.selected=&selected;second.labels=&out;second.filename=path;second.continuation=continuation;second.run(int(x.rows.size()));
        if(++files%32==0)std::cerr<<"Collected "<<files<<" cases\n";
    }return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
