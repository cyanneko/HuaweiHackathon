#include TEST_INCLUDE
#include <cassert>
SystemState fixture(){
 SystemState s{};s.num_partitions=4;s.memory_limit=1000;s.memory_used=1000;
 s.read_bandwidth=1.;s.write_bandwidth=2.;
 for(int o=0;o<2;++o){OperatorState op{};op.op_id=o;op.phase=Phase::PROBE;
  for(int p=0;p<4;++p){PartitionState x{};x.partition_id=p;x.in_memory=true;x.data_size=0;op.partitions.push_back(x);}s.operators.push_back(op);}
 s.operators[0].partitions[0].data_size=100;s.operators[0].partitions[1].data_size=300;
 s.operators[0].partitions[2].data_size=200;s.operators[1].partitions[0].data_size=200;
 return s;
}
bool same(const std::vector<Action>&a,const std::vector<Action>&b){if(a.size()!=b.size())return false;for(size_t i=0;i<a.size();++i)if(a[i].type!=b[i].type||a[i].op_id!=b[i].op_id||a[i].partition_id!=b[i].partition_id)return false;return true;}
void original(SystemState s,int64_t z,MySpillScheduler& m,std::vector<Action>& a){m.active_=true;m.update(s);m.release(s,0,3,z,a);m.pruneSpills(s,z,a);m.record(s,a);}
int main(){
 {auto s=fixture();MySpillScheduler m;auto a=m.onMemoryOverflow(s,0,3,150);assert(a.size()==1&&a[0].op_id==0&&a[0].partition_id==2);assert(m.intents_.size()==1&&m.intents_[0].id==2);}
 {auto s=fixture();s.operators[0].partitions[3].data_size=150;s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=2;MySpillScheduler m;auto a=m.onMemoryOverflow(s,0,3,150);assert(a.size()==1&&a[0].op_id==1&&a[0].partition_id==0);assert(m.intents_.size()==1&&m.intents_[0].id==4);s.operators[1].partitions[0].in_memory=false;s.memory_used-=200;s.next_op.type="";m.onPeriodicAdjust(s);assert(m.risk_[4].active==1&&m.risk_[2].active==0);}
 {auto s=fixture();s.operators[0].partitions[2].in_memory=false;MySpillScheduler m;auto a=m.onMemoryOverflow(s,0,3,150);assert(a.size()==1&&a[0].op_id==1&&a[0].partition_id==0);}
 {auto s=fixture();MySpillScheduler m,b;auto a=m.onMemoryOverflow(s,0,3,500);std::vector<Action> expected;original(s,500,b,expected);assert(same(a,expected));}
 {auto s=fixture();s.memory_used=700;MySpillScheduler m;assert(m.onMemoryOverflow(s,0,3,150).empty());assert(m.intents_.empty());}
 {auto s=fixture();s.hit_count=1;MySpillScheduler m,b;auto a=m.onMemoryOverflow(s,0,3,150);std::vector<Action> expected;original(s,150,b,expected);
#if BUILD0
 assert(same(a,expected));
#else
 assert(a.size()==1&&a[0].op_id==0&&a[0].partition_id==2);
#endif
 }
 {auto s=fixture();for(auto& o:s.operators)o.phase=Phase::BUILD;MySpillScheduler m;auto a=m.onMemoryOverflow(s,0,3,150);assert(a.size()==1&&a[0].partition_id==2);assert(m.intents_.empty());}
 std::cout<<"singlefit targeted tests PASS\n";
}
