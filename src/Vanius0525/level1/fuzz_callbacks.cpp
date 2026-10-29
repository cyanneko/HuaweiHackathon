// Abstract callback-state safety properties; no reference engine is modified.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <random>
#include <string>
#include <vector>
#include <stdexcept>
// OFFICIAL_DECLARATIONS
// POLICY_DEFINITION
static void require(bool v,const char* message){if(!v)throw std::runtime_error(message);}
static void execute(SystemState& s,const std::vector<Action>& a,char kind,int target_op,int target_pid,int64_t z) {
    std::vector<int> seen(s.operators.size()*s.num_partitions,0);
    if(kind=='M')require(!a.empty() && a.back().type==Action::LOAD && a.back().op_id==target_op && a.back().partition_id==target_pid,"miss last load");
    for(const auto& x:a) {
        require(x.op_id>=0 && x.op_id<static_cast<int>(s.operators.size()),"bad operator");
        require(x.partition_id>=0 && x.partition_id<s.num_partitions,"bad partition");
        auto& p=s.operators[x.op_id].partitions[x.partition_id];
        int id=x.op_id*s.num_partitions+x.partition_id;
        if(x.type==Action::SPILL) {
            require(!seen[id],"duplicate spill");seen[id]|=1;
            require(kind!='O'||x.op_id!=target_op||x.partition_id!=target_pid,"protected spill");
            require(p.in_memory && p.data_size>0,"invalid spill");
            s.memory_used-=p.data_size;p.in_memory=false;
        } else {
            require(x.type==Action::LOAD && kind!='O',"invalid action type");
            require(!p.in_memory && s.operators[x.op_id].phase==Phase::PROBE,"invalid load");
            require(!(seen[id]&2),"duplicate load");seen[id]|=2;
            s.memory_used+=p.data_size;p.in_memory=true;
        }
        require(s.memory_used>=0 && s.memory_used<=s.memory_limit,"capacity");
    }
    if(kind=='O')require(s.memory_used+z<=s.memory_limit,"insufficient release");
    if(kind=='M')require(s.operators[target_op].partitions[target_pid].in_memory,"target missing");
}
int main(int argc,char**argv) {
    const int cases=argc>1?std::atoi(argv[1]):20000;
    std::mt19937_64 rng(290029);int callbacks=0;
    for(int trial=0;trial<cases;++trial) {
        const int k=1+rng()%8,p=2+rng()%63,n=k*p;
        SystemState s;s.memory_limit=(trial%3==0?4294967296LL:67108864LL);
        s.num_partitions=p;s.memory_used=0;s.hit_count=rng()%1000000;s.miss_count=1+rng()%10000;s.total_io_bytes=0;
        s.write_bandwidth=1+rng()%10000;s.read_bandwidth=1+rng()%10000;
        const int id=rng()%n,op=id/p,pid=id%p;const bool overflow=trial%2;
        for(int o=0;o<k;++o) {
            OperatorState a;a.op_id=o;a.phase=(o==op?(overflow?Phase::BUILD:Phase::PROBE):(rng()%2?Phase::BUILD:Phase::PROBE));a.partitions.resize(p);
            for(int j=0;j<p;++j) {
                auto& v=a.partitions[j];v.partition_id=j;
                v.data_size=1+rng()%std::max<int64_t>(1,s.memory_limit/16);
                v.in_memory=(o*p+j!=id || overflow) && s.memory_used+v.data_size<=s.memory_limit && rng()%4!=0;
                if(v.in_memory)s.memory_used+=v.data_size;
            }
            s.operators.push_back(a);
        }
        auto& target=s.operators[op].partitions[pid];
        if(overflow && !target.in_memory){target.in_memory=true;s.memory_used+=target.data_size;}
        // Make a full but feasible cache, without enlarging the protected target.
        bool filled=false;
        for(int o=0;o<k&&!filled;++o)for(int j=0;j<p&&!filled;++j) {
            if(o==op && j==pid)continue;
            auto& v=s.operators[o].partitions[j];
            if(!v.in_memory){v.data_size=1;v.in_memory=true;++s.memory_used;}
            if(s.memory_used<=s.memory_limit){v.data_size+=s.memory_limit-s.memory_used;s.memory_used=s.memory_limit;filled=true;}
        }
        if(s.memory_used>s.memory_limit){--trial;continue;}
        s.next_op=PendingOp{};
        if(trial%4!=0){s.next_op.type="PROBE";s.next_op.op_id=rng()%k;s.next_op.key=rng()%p;}
        MySpillScheduler scheduler;
        if(overflow) {
            int64_t z=1+rng()%1048576;
            auto actions=scheduler.onMemoryOverflow(s,op,pid,z);execute(s,actions,'O',op,pid,z);++callbacks;
            target.data_size+=z;s.memory_used+=z;
        } else {
            auto actions=scheduler.onPartitionMiss(s,op,pid);execute(s,actions,'M',op,pid,0);++callbacks;
        }
        auto actions=scheduler.onPeriodicAdjust(s);execute(s,actions,'P',-1,-1,0);++callbacks;
    }
    std::cout<<"property_cases="<<cases<<" callbacks="<<callbacks<<" passed\n";
}
