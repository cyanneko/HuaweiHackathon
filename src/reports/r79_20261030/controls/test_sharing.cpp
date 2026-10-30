#include TEST_INCLUDE
#include <cassert>
bool near(double a,double b){return std::abs(a-b)<=2e-9*std::max(1.,std::max(std::abs(a),std::abs(b)));}
SystemState fixture(int p=64){SystemState s{};s.num_partitions=p;s.memory_limit=1000;s.read_bandwidth=100;s.write_bandwidth=100;for(int o=0;o<2;++o){OperatorState op{};op.op_id=o;op.phase=Phase::PROBE;for(int i=0;i<p;++i){PartitionState pa{};pa.partition_id=i;pa.data_size=100;pa.in_memory=true;op.partitions.push_back(pa);}s.operators.push_back(op);}return s;}
double expectedShare(double S,double Q,double W2,int P){if(S<=8||W2<=1e-200||P<=1)return .75;double n=S*S/W2;if(n<=8)return .75;double v=std::max(0.,(P*Q/(S*S)-1.-(P-1)/n)/(1.-1./n));double x=v*(S-8)/(S+P);return .75/(1.+x);}
int main(){
 MySpillScheduler m;auto s=fixture();m.update(s);assert(m.sharing_[0].share==.75);
 std::vector<double> c(64,0.);double W2=0;int64_t last=0;double uniform=0,hot=0;
 for(int64_t q=1;q<=24576;++q){int pid=q>4096&&q<=8192?0:int((q-1)%64);double f=std::exp(-std::log(2.)*(q-last)/2048.);for(double&v:c)v*=f;W2*=f*f;c[pid]+=1;W2+=1;last=q;m.sampleNext(0,pid,q);double S=0,Q=0;for(double v:c){S+=v;Q+=v*v;}const auto&g=m.sharing_[0];assert(near(S,g.mass)&&near(Q,g.squares)&&near(W2,g.weight2));assert(near(expectedShare(S,Q,W2,64),g.share));assert(std::isfinite(g.share)&&g.share>=0&&g.share<=.75);
  assert(g.heterogeneity>=0&&g.heterogeneity<=1);assert(near(g.share,.75*(1.-g.heterogeneity)));
  auto saved=g;m.sampleNext(0,pid,q);assert(m.sharing_[0].mass==saved.mass&&m.sharing_[0].squares==saved.squares&&m.sharing_[0].weight2==saved.weight2);
  if(q==4096)uniform=g.share;if(q==8192)hot=g.share;
 }
 assert(uniform>.74&&hot<.04&&m.sharing_[0].share>.74);
 for(const auto& g:m.sharing_) {assert(g.heterogeneity>=0&&g.heterogeneity<=1);assert(near(g.share,.75*(1.-g.heterogeneity)));}
 // Exact common decay on a long interval, then touch a different stale partition.
 m.sampleNext(0,0,24577);c[0]+=0; // independent reference below starts from stored moments.
 const auto before=m.sharing_[0];m.refreshSharing(0,1000000);assert(m.sharing_[0].share==.75);assert(m.sharing_[0].last==1000000);
 m.refreshSharing(0,999999);assert(m.sharing_[0].last==1000000);
 m.sampleNext(0,17,1000001);assert(near(m.sharing_[0].mass,1.)&&near(m.sharing_[0].squares,1.)&&near(m.sharing_[0].weight2,1.));
 // Subnormal/underflow regimes must remain finite and recover on new samples.
 m.refreshSharing(0,10000000);assert(m.sharing_[0].share==.75);m.sampleNext(0,18,10000001);assert(m.sharing_[0].mass==1&&m.sharing_[0].squares==1&&m.sharing_[0].weight2==1);
 m.sharing_[0].weight2=0;m.refreshSharing(0,10000001);assert(m.sharing_[0].share==.75);
 {MySpillScheduler one;auto a=fixture(1);one.update(a);for(int q=1;q<50;++q)one.sampleNext(0,0,q);assert(one.sharing_[0].share==.75);}
 {MySpillScheduler x;auto a=fixture();x.update(a);x.risk_[0].starts=1;x.risk_[0].exposure=640;x.risk_[0].events=9;double h=x.partitionBase(0,0,.2);x.operator_risk_[0].starts=1e6;x.operator_risk_[0].exposure=1e9;x.cached_priors_[0]=1e7;assert(x.partitionBase(0,0,.2)==h);x.risk_[1].starts=0;assert(x.partitionBase(1,0,.2)==.2);assert(x.refaultReuse(0,0,.123,1.)==.123);}
 {MySpillScheduler x;auto a=fixture();x.update(a);a.miss_count=1;x.update(a,0,0);assert(x.sharing_[0].mass==0);a.next_op.type="PROBE";a.next_op.op_id=0;a.next_op.key=1;x.update(a,-1,-1,true);assert(x.next_sample_q_==2&&x.sharing_[0].mass==1);auto g=x.sharing_[0];x.update(a,0,0);assert(x.sharing_[0].mass==g.mass&&x.sharing_[0].weight2==g.weight2);a.miss_count=2;a.next_op.type="";x.risk_[1].begin(0);x.operator_risk_[0].begin(0);x.update(a,0,1);assert(x.risk_[1].events==1&&x.sharing_[0].mass==1&&x.sharing_[0].last==2);}
 {MySpillScheduler x;auto a=fixture();x.update(a);x.sampleNext(0,0,1);x.sampleNext(1,0,2);x.sampleNext(0,7,100);double f=std::exp(-std::log(2.)*99/2048.);assert(near(x.sharing_[0].mass,f+1)&&near(x.sharing_[0].squares,f*f+1)&&near(x.sharing_[0].weight2,f*f+1));}
 std::cout<<"sharing exact-vector, recovery, dedup, independence PASS\n";
}
