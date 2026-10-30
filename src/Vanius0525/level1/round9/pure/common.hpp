// Offline diagnostic helpers, never part of the submitted policy.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
static uint64_t mix(uint64_t h,uint64_t x) {
    for(int j=0;j<8;++j){h^=(x&255);h*=1099511628211ULL;x>>=8;}return h;
}
static uint64_t stateHash(const SystemState& s) {
    uint64_t h=1469598103934665603ULL;
    for(uint64_t x:{static_cast<uint64_t>(s.memory_limit),static_cast<uint64_t>(s.memory_used),
        static_cast<uint64_t>(s.num_partitions),static_cast<uint64_t>(s.read_bandwidth),
        static_cast<uint64_t>(s.write_bandwidth),static_cast<uint64_t>(s.hit_count),
        static_cast<uint64_t>(s.miss_count),static_cast<uint64_t>(s.total_io_bytes)})h=mix(h,x);
    for(const auto& o:s.operators){h=mix(h,o.op_id);h=mix(h,static_cast<int>(o.phase));
        for(const auto& p:o.partitions){h=mix(h,p.partition_id);h=mix(h,p.data_size);h=mix(h,p.in_memory);}}
    for(char c:s.next_op.type)h=mix(h,static_cast<unsigned char>(c));
    h=mix(h,s.next_op.op_id);h=mix(h,s.next_op.key);h=mix(h,s.next_op.tuple_size);return h;
}
static bool pressure(const SystemState& s,int op,int pid) {
    for(const auto& o:s.operators)if(o.phase!=Phase::PROBE)return false;
    return s.operators[op].partitions[pid].data_size>s.memory_limit-s.memory_used;
}
static bool residentNext(const SystemState& s,int op,int pid) {
    if(s.next_op.type!="PROBE" || s.next_op.op_id<0 || s.next_op.op_id>=static_cast<int>(s.operators.size()))return false;
    const int o=s.next_op.op_id,p=s.next_op.key%s.num_partitions;
    return (o!=op || p!=pid) && s.operators[o].partitions[p].in_memory && s.operators[o].partitions[p].data_size>0;
}
static bool eligible(const SystemState& s,int op,int pid) {
    if(!pressure(s,op,pid) || !residentNext(s,op,pid))return false;
    return s.operators[s.next_op.op_id].partitions[s.next_op.key%s.num_partitions].data_size>=
        s.operators[op].partitions[pid].data_size-(s.memory_limit-s.memory_used);
}
static void emitActions(const std::vector<Action>& a) {
    std::cout<<'[';bool comma=false;for(const auto& x:a){if(comma)std::cout<<',';comma=true;
        std::cout<<'['<<(x.type==Action::SPILL?0:1)<<','<<x.op_id<<','<<x.partition_id<<']';}std::cout<<']';
}
static void emitResident(const SystemState& s) {
    std::cout<<'[';bool comma=false;for(const auto& o:s.operators)for(const auto& p:o.partitions){
        if(comma)std::cout<<',';comma=true;std::cout<<(p.in_memory?1:0);}std::cout<<']';
}
