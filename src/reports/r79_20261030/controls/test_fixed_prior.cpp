#include TEST_INCLUDE
#include <cassert>
int main(){
 SystemState s{};s.num_partitions=2;s.memory_limit=1000;s.read_bandwidth=100;s.write_bandwidth=100;
 OperatorState op{};op.op_id=0;op.phase=Phase::PROBE;
 for(int i=0;i<2;++i){PartitionState p{};p.partition_id=i;p.data_size=100;p.in_memory=true;op.partitions.push_back(p);}s.operators.push_back(op);
 MySpillScheduler m;m.update(s);m.risk_[0].starts=1;m.risk_[0].exposure=640;m.risk_[0].events=9;
 m.operator_risk_[0].starts=1;m.operator_risk_[0].exposure=128;m.operator_risk_[0].events=1;
 const double hp=64./(64.+704./10.),ho=64./(64.+192./2.);
 const double expected=.75*(.25*hp+.75*ho)+.25*.2;
 assert(std::abs(m.refaultReuse(0,0,.2,.25)-expected)<1e-12);
 std::cout<<"independent fixed prior PASS\n";
}
