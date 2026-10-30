#include TEST_INCLUDE
#include "oracle.hpp"
void totals(MySpillScheduler&x,const Oracle&o,int64_t q){auto v=o.at(q);assert(near(x.operator_fast_total_,v.tf)&&near(x.operator_slow_total_,v.ts));assert(x.operator_total_q_==q);assert(near(x.operator_fast_weight_,o.w));assert(x.operator_fast_weight_>=1./256&&x.operator_fast_weight_<=255./256);}
int main(){
 // Independent full weighted vector at irregular observation/query clocks.
 for(int k:{1,2,4})for(int p:{1,5}){
  auto s=fixture(k,p);MySpillScheduler x;x.update(s);Oracle o(k,p);int64_t q=0;
  o.check_probabilities(x,s,q);totals(x,o,q);
  for(int t=1;t<=120;++t){q+=t%17==0?9000:(t%7==0?251:(t%3==0?17:1));int op=(t*t+t/5)%k,pid=(t*7)%p;
   o.sample(op,pid,q);x.sampleNext(op,pid,q);totals(x,o,q);
   auto fw=x.operator_fast_weight_,tf=x.operator_fast_total_,ts=x.operator_slow_total_;auto last=x.next_sample_q_;
   x.sampleNext((op+1)%k,(pid+1)%p,q);x.sampleNext(op,pid,q-1);
   assert(x.operator_fast_weight_==fw&&x.operator_fast_total_==tf&&x.operator_slow_total_==ts&&x.next_sample_q_==last);
   o.check_probabilities(x,s,q);totals(x,o,q);
  }
  // A query-only gap decays masses, never applies another share transition.
  double w=x.operator_fast_weight_;q+=10000000;o.check_probabilities(x,s,q);totals(x,o,q);assert(x.operator_fast_weight_==w);
  o.sample(0,0,q+1);x.sampleNext(0,0,q+1);o.check_probabilities(x,s,q+1);totals(x,o,q+1);
  x.probability_epoch_=std::numeric_limits<uint64_t>::max();o.check_probabilities(x,s,q+1);assert(x.probability_epoch_==1);
 }
 // With K=1 both predictive likelihoods are 1. Sharing to OTHER expert has
 // contraction 1-2*alpha, and .5 is invariant; uniform-pool sharing fails here.
 {auto s=fixture(1,2);MySpillScheduler x;x.update(s);x.sampleNext(0,0,1);assert(x.operator_fast_weight_==.5);
  x.operator_fast_weight_=.83;double previous=.83;x.sampleNext(0,1,2);
  assert(near(x.operator_fast_weight_,.5L+(1-2*ALPHA)*(previous-.5L)));
  assert(x.operator_fast_weight_<previous&&x.operator_fast_weight_>.5);
 }
 // First label is scored under uniform pre-insertion forecasts even though
 // its fast and slow POST-insertion forecasts differ. No label leakage.
 {auto s=fixture(3,2);MySpillScheduler x;x.update(s);x.sampleNext(1,0,1);assert(near(x.operator_fast_weight_,.5L));}
 // Miss observations do not become next trials, and q+1 cannot rewind to q.
 {auto s=fixture(2,2);MySpillScheduler x;x.update(s);s.miss_count=10;x.update(s,0,0);assert(x.operator_fast_total_==0&&x.operator_slow_total_==0);
  s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=1;x.update(s,0,0);assert(x.operator_total_q_==11&&x.operator_fast_total_==1&&x.operator_fast_weight_==.5);
  double w=x.operator_fast_weight_;x.update(s,1,0);x.ensureProbabilities(s);assert(x.operator_total_q_==11&&x.operator_fast_total_==1&&x.operator_fast_weight_==w);
 }
 // Actual dimension reset clears persistent mixture statistics and cache.
 {auto s=fixture(2,2);MySpillScheduler x;x.update(s);for(int q=1;q<100;++q)x.sampleNext(q%2,q%2,q);s.hit_count=99;x.ensureProbabilities(s);
  auto z=fixture(3,1);x.update(z);assert(x.operator_fast_weight_==.5&&x.operator_fast_total_==0&&x.operator_slow_total_==0&&x.operator_total_q_==0&&x.next_sample_q_==-1);Oracle fresh(3,1);fresh.check_probabilities(x,z,0);
 }
 // Defensive invalid weight recovers through the same first-label prior.
 {auto s=fixture(2,2);MySpillScheduler x;x.update(s);x.operator_fast_weight_=std::numeric_limits<double>::quiet_NaN();x.sampleNext(0,0,1);assert(x.operator_fast_weight_==.5);}
 std::cout<<"weighted-vector/log-loss oracle; pre-insert; duplicates; query-gap; other-expert share; K1/reset/finite PASS\n";
}
