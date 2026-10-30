// Observer-only serialization; never receives a reference to the live scheduler.
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
namespace obs11 {
inline void require(bool ok,const char* message) {
    if(!ok){std::cerr << "OBS_ERROR " << message << '\n';std::abort();}
}
inline void number(std::ostream& out,double value) {
    require(std::isfinite(value),"nonfinite snapshot value");out << value;
}
inline void actions(std::ostream& out,const std::vector<Action>& values) {
    out << '[';bool comma=false;
    for(const auto& x:values){if(comma)out << ',';comma=true;
        out << "[\"" << (x.type==Action::SPILL?'S':'L') << "\"," << x.op_id << ',' << x.partition_id << ']';}
    out << ']';
}
inline bool same(const std::vector<Action>& a,const std::vector<Action>& b) {
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)
        if(a[i].type!=b[i].type || a[i].op_id!=b[i].op_id || a[i].partition_id!=b[i].partition_id)return false;
    return true;
}
inline void state(std::ostream& out,const SystemState& s) {
    out << "{\"memory_used\":" << s.memory_used << ",\"memory_limit\":" << s.memory_limit
        << ",\"num_partitions\":" << s.num_partitions << ",\"write_bandwidth\":";
    number(out,s.write_bandwidth);out << ",\"read_bandwidth\":";number(out,s.read_bandwidth);
    out << ",\"hit_count\":" << s.hit_count << ",\"miss_count\":" << s.miss_count
        << ",\"total_io_bytes\":" << s.total_io_bytes << ",\"next_op\":{\"type\":\"" << s.next_op.type
        << "\",\"op_id\":" << s.next_op.op_id << ",\"key\":" << s.next_op.key
        << ",\"tuple_size\":" << s.next_op.tuple_size << "},\"operators\":[";
    bool comma=false;
    for(const auto& o:s.operators){if(comma)out << ',';comma=true;
        out << "{\"op_id\":" << o.op_id << ",\"phase\":\"" << (o.phase==Phase::PROBE?"PROBE":"BUILD") << "\",\"partitions\":[";
        bool pc=false;for(const auto& p:o.partitions){if(pc)out << ',';pc=true;
            out << "{\"partition_id\":" << p.partition_id << ",\"data_size\":" << p.data_size
                << ",\"in_memory\":" << (p.in_memory?"true":"false") << '}';}
        out << "]}";
    }
    out << "]}";
}
}
