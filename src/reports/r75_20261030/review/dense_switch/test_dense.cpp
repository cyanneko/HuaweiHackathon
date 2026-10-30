#include "test_policy_include.hpp"
SystemState fixture(){SystemState s{};s.num_partitions=3;s.memory_limit=s.memory_used=200;s.read_bandwidth=s.write_bandwidth=100.;OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;for(int i=0;i<3;++i){PartitionState p;p.partition_id=i;p.data_size=100;p.in_memory=i!=2;o.partitions.push_back(p);}s.operators.push_back(o);return s;}
void near(double a,double b){assert(std::abs(a-b)<1e-9);}
int main(){
 {r74::Risk slow,dense; r75op::Risk fast,fdense;slow.begin(0);dense.begin(0);fast.begin(0);fdense.begin(0);slow.advance(256);fast.advance(256);for(int q=1;q<=256;++q){dense.advance(q);fdense.advance(q);}near(slow.exposure,512.*(1.-std::exp(-.5)));near(fast.exposure,128.*(1.-std::exp(-2.)));near(slow.exposure,dense.exposure);near(fast.exposure,fdense.exposure);assert(fast.exposure<slow.exposure);fast.end(256,true);near(fast.events,1.);assert(fast.active==0);}
 {MySpillScheduler m;auto s=fixture();s.hit_count=9;s.miss_count=1;m.update(s);m.risk_[2].begin(0);m.operator_risk_[0].begin(0);std::vector<Action>a;m.release(s,0,2,100,a);double before=m.cached_priors_[0];assert(m.cached_valid_[0]);near(before,64.+128.*(1.-std::exp(-10./128.)));auto actions=m.onPartitionMiss(s,0,2);assert(actions.size()==2);near(m.cached_priors_[0],before/2.);near(m.operator_risk_[0].events,1.);}
 {MySpillScheduler m;auto s=fixture();m.update(s);m.risk_[2].begin(0);m.operator_risk_[0].begin(0);s.hit_count=128;m.coverage_q_=128;m.coverage_=.75*(1.-std::exp(-128./256.));near(m.demandWeight(128),1.);near(m.refaultReuse(0,128,.123,1.),.123);assert(m.operator_risk_[0].last==0);s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=0;std::vector<Action>a;m.release(s,0,2,100,a);assert(a.size()==1&&a[0].partition_id==1);assert(m.operator_risk_[0].last==0);s.hit_count=255;s.miss_count=1;s.next_op.type="";m.coverage_=0;m.onPartitionMiss(s,0,2);near(m.risk_[2].exposure,512.*(1.-std::exp(-.5)));near(m.operator_risk_[0].exposure,128.*(1.-std::exp(-2.)));near(m.risk_[2].events,1.);near(m.operator_risk_[0].events,1.);}
 {MySpillScheduler m;auto s=fixture();m.update(s);m.coverage_q_=128;m.coverage_=.375*(1.-std::exp(-.5));near(m.demandWeight(128),.25);m.coverage_=0;near(m.demandWeight(128),.25);}

 {MySpillScheduler m;auto s=fixture();m.update(s);m.risk_[2].begin(0);m.operator_risk_[0].begin(0);
  s.hit_count=10;std::vector<Action>a;m.release(s,0,2,100,a);double before=m.cached_priors_[0];assert(m.cached_valid_[0]);
  s.hit_count=20;m.coverage_q_=20;m.coverage_=.751*(1.-std::exp(-20./256.));near(m.demandWeight(20),1.);a.clear();m.release(s,0,2,100,a);assert(!m.cached_valid_[0]);assert(m.operator_risk_[0].last==10);
  s.hit_count=30;m.coverage_q_=30;m.coverage_=.749*(1.-std::exp(-30./256.));near(m.demandWeight(30),.25);a.clear();m.release(s,0,2,100,a);assert(m.cached_valid_[0]);assert(m.cached_priors_[0]>before);near(m.cached_priors_[0],64.+128.*(1.-std::exp(-30./128.)));
  m.coverage_q_=256;m.coverage_=.75*(1.-std::exp(-1.));near(m.demandWeight(256),1.);
 }
 std::cout<<"dense switch thresholds, cache, tau, dense guard and next protection tests passed\n";
}
