
#include <iostream>
#include <cstdlib>
#define CHECK(x) do { if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n"; std::exit(1);} }while(0)
SystemState fixture(){SystemState s{};s.num_partitions=3;s.memory_limit=100;s.memory_used=100;s.read_bandwidth=1;s.write_bandwidth=1;s.operators.resize(1);auto&o=s.operators[0];o.op_id=0;o.phase=Phase::PROBE;o.partitions.resize(3);for(int i=0;i<3;++i){o.partitions[i].partition_id=i;o.partitions[i].data_size=(i==0?10:90);o.partitions[i].in_memory=i<2;}return s;}
void tick(SystemState&s,long long t){s.hit_count=t;s.miss_count=0;}
void reward(R65TurnoverRisk&p,SystemState&s,int t){tick(s,t);s.operators[0].partitions[0].in_memory=true;s.memory_used=100;auto a=p.onMemoryOverflow(s,0,2,10);CHECK(a.size()==1&&a[0].partition_id==0);s.operators[0].partitions[0].in_memory=false;s.memory_used=90;p.onPeriodicAdjust(s);tick(s,t+1);a=p.onPartitionMiss(s,0,0);CHECK(a.back().type==Action::LOAD);s.operators[0].partitions[0].in_memory=true;s.memory_used=100;p.onPeriodicAdjust(s);}
int main(){auto s=fixture();R65TurnoverRisk p;reward(p,s,0);CHECK(p.debugHeat(0,0)==1);CHECK(p.debugAnchor(0,0)==1);
// Confirmed spill retains existing heat.
auto a=p.onMemoryOverflow(s,0,2,10);CHECK(a[0].partition_id==0);s.operators[0].partitions[0].in_memory=false;s.memory_used=90;p.onPeriodicAdjust(s);CHECK(p.debugHeat(0,0)==1);
// Reserved reward ages from miss, not confirmation, across delayed LOAD.
tick(s,2);p.onPartitionMiss(s,0,0);tick(s,65);s.operators[0].partitions[0].in_memory=true;s.memory_used=100;p.onPeriodicAdjust(s);CHECK(p.debugHeat(0,0)==1);CHECK(p.debugAnchor(0,0)==65);
tick(s,128);p.onMemoryOverflow(s,0,2,1);CHECK(p.debugHeat(0,0)==1);tick(s,129);p.onMemoryOverflow(s,0,2,1);CHECK(p.debugHeat(0,0)==0);
// Same-clock confirmation cannot reward twice; ignored spill creates no ghost.
auto z=fixture();R65TurnoverRisk q;q.onMemoryOverflow(z,0,2,10);q.onPeriodicAdjust(z);z.operators[0].partitions[0].in_memory=false;z.memory_used=90;q.onPartitionMiss(z,0,0);z.operators[0].partitions[0].in_memory=true;q.onPeriodicAdjust(z);CHECK(q.debugHeat(0,0)==0);
// Reset and size identity invalidate.
s.operators[0].partitions[0].data_size=11;p.onMemoryOverflow(s,0,2,1);CHECK(p.debugHeat(0,0)==0);tick(s,0);p.onPeriodicAdjust(s);CHECK(p.debugHeat(0,0)==0);
// No single sufficient: exact BF fallback.
auto f=fixture();f.operators[0].partitions[0].data_size=40;f.operators[0].partitions[1].data_size=60;R65TurnoverRisk r;R53BestFit bf;auto aa=r.onMemoryOverflow(f,0,2,100),bb=bf.onMemoryOverflow(f,0,2,100);CHECK(aa.size()==bb.size());for(size_t i=0;i<aa.size();++i)CHECK(aa[i].partition_id==bb[i].partition_id);

// Ignored LOAD is discarded at first observation; external later residency earns nothing.
auto ig=fixture();R65TurnoverRisk ignored;ignored.onMemoryOverflow(ig,0,2,10);ig.operators[0].partitions[0].in_memory=false;ig.memory_used=90;ignored.onPeriodicAdjust(ig);tick(ig,1);ignored.onPartitionMiss(ig,0,0);ignored.onPeriodicAdjust(ig);ig.operators[0].partitions[0].in_memory=true;ig.memory_used=100;ignored.onPeriodicAdjust(ig);CHECK(ignored.debugHeat(0,0)==0);
// First confirmation delayed >128 references decays reserved reward to zero.
auto dl=fixture();R65TurnoverRisk delayed;delayed.onMemoryOverflow(dl,0,2,10);dl.operators[0].partitions[0].in_memory=false;dl.memory_used=90;delayed.onPeriodicAdjust(dl);tick(dl,1);delayed.onPartitionMiss(dl,0,0);tick(dl,131);dl.operators[0].partitions[0].in_memory=true;dl.memory_used=100;delayed.onPeriodicAdjust(dl);CHECK(delayed.debugHeat(0,0)==0);
// Repeated successful own cycles at one clock cannot accumulate reward.
auto du=fixture();R65TurnoverRisk dedup;reward(dedup,du,0);for(int j=0;j<3;++j){dedup.onMemoryOverflow(du,0,2,10);du.operators[0].partitions[0].in_memory=false;du.memory_used=90;dedup.onPeriodicAdjust(du);dedup.onPartitionMiss(du,0,0);du.operators[0].partitions[0].in_memory=true;du.memory_used=100;dedup.onPeriodicAdjust(du);}CHECK(dedup.debugHeat(0,0)==1);
// Positive-heat reward retains fractional aging remainder; cap floor(M/b).
auto ca=fixture();R65TurnoverRisk capped;reward(capped,ca,0);for(int t=2;t<20;++t){capped.onMemoryOverflow(ca,0,1,10);ca.operators[0].partitions[0].in_memory=false;ca.memory_used=90;capped.onPeriodicAdjust(ca);tick(ca,t);capped.onPartitionMiss(ca,0,0);ca.operators[0].partitions[0].in_memory=true;ca.memory_used=100;capped.onPeriodicAdjust(ca);}CHECK(capped.debugHeat(0,0)==10);CHECK(capped.debugAnchor(0,0)==1);auto heated=capped.onMemoryOverflow(ca,0,2,10);CHECK(heated[0].partition_id==1);tick(ca,64);capped.onMemoryOverflow(ca,0,1,10);CHECK(capped.debugHeat(0,0)==10);tick(ca,65);capped.onMemoryOverflow(ca,0,1,10);CHECK(capped.debugHeat(0,0)==9);ca.memory_limit=101;capped.onPeriodicAdjust(ca);CHECK(capped.debugHeat(0,0)==0);
// Reverse lifecycle clears heat.
auto rv=fixture();R65TurnoverRisk reverse;reward(reverse,rv,0);rv.operators[0].phase=Phase::BUILD;reverse.onPeriodicAdjust(rv);CHECK(reverse.debugHeat(0,0)==0);
// Candidate outside half-largest and top-four must remain eligible.
auto all=fixture();all.num_partitions=7;all.operators[0].partitions.resize(7);all.memory_limit=1000;all.memory_used=501;for(int i=0;i<7;++i){auto&x=all.operators[0].partitions[i];x.partition_id=i;x.data_size=i==0?1:100;x.in_memory=i<6;}R65TurnoverRisk scan;auto best=scan.onMemoryOverflow(all,0,6,500);CHECK(best.size()==1&&best[0].partition_id==0);
// Unsupported >512 shape uses exact BF and no adaptation.
auto un=fixture();un.num_partitions=513;un.operators[0].partitions.resize(513);for(int i=3;i<513;++i){un.operators[0].partitions[i].partition_id=i;un.operators[0].partitions[i].data_size=0;un.operators[0].partitions[i].in_memory=false;}R65TurnoverRisk unsupported;auto ua=unsupported.onMemoryOverflow(un,0,2,10),ub=bf.onMemoryOverflow(un,0,2,10);CHECK(ua.size()==ub.size()&&ua[0].partition_id==ub[0].partition_id);CHECK(unsupported.debugHeat(0,0)==0);
// Large clock and byte boundaries avoid multiplication and clock overflow.
auto edge=fixture();edge.memory_limit=std::numeric_limits<std::int64_t>::max();edge.memory_used=edge.memory_limit;edge.operators[0].partitions[0].data_size=edge.memory_limit-90;tick(edge,std::numeric_limits<std::int64_t>::max());R65TurnoverRisk boundary;CHECK(!boundary.onMemoryOverflow(edge,0,2,1).empty());edge.miss_count=1;boundary.onPeriodicAdjust(edge);CHECK(boundary.debugHeat(0,0)==0);
SystemState empty{};r.onPeriodicAdjust(empty);std::cout<<"PASS heat contracts\n";}
