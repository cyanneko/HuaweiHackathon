// Tiny callback/state probes only. Never linked into timing binaries.
#include "effectiveness.generated.hpp"
#include <iostream>
#include <stdexcept>
void check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
bool near(double a,double b){return std::abs(a-b)<1e-10;}
SystemState state(int k=2,int p=4){
    SystemState s{};s.num_partitions=p;s.memory_limit=10000;s.write_bandwidth=10;s.read_bandwidth=20;s.hit_count=1;
    for(int op=0;op<k;++op){OperatorState o{};o.op_id=op;o.phase=Phase::PROBE;
        for(int pid=0;pid<p;++pid){PartitionState q;q.partition_id=pid;q.data_size=100;q.in_memory=true;o.partitions.push_back(q);s.memory_used+=100;}
        s.operators.push_back(o);
    }return s;
}
template<class T> void initialize(T& a,const SystemState& s){a.update(s);}
template<class T> void uneven(T& a){for(int q=1;q<=128;++q)a.sampleNext(0,0,q);}
template<class T> double priority(T& a,int op,int pid){for(const auto& v:a.victims_)if(v.op==op&&v.pid==pid)return v.priority;throw std::runtime_error("missing victim");}
template<class T> void cycle(T& a,const SystemState& s,bool cached=false){
    initialize(a,s);const int n=s.num_partitions;for(int i=0;i<n;++i){a.successor_[i]=(i+1)%n;a.confidence_[i]=3;}
    a.confirmed_edges_=n;a.last_op_=0;a.last_pid_=n-1;a.graph_version_=7;a.analyzed_version_=cached?7:-1;a.uniform_cycle_=cached;
    a.recent_[0]=1;a.recent_[1]=0;a.recent_head_=2;a.recent_count_=2;
}
int main(){
    int tests=0;
    {auto s=state();Full a;FixedShare075 b;initialize(a,s);initialize(b,s);uneven(a);uneven(b);
     check(a.sharing_[0].heterogeneity>0&&a.sharing_[0].share<.75,"Full adaptive share active");
     check(near(b.sharing_[0].share,.75)&&b.sharing_[0].heterogeneity>0,"fixed share, retained heterogeneity");
     check(near(a.fast_operator_[0].mass,b.fast_operator_[0].mass)&&near(a.next_mass_[0].mass,b.next_mass_[0].mass),"sharing retains counters");++tests;}
    {auto s=state();Full a;UnifiedSlow2048 b;initialize(a,s);initialize(b,s);
     a.fast_operator_[0].mass=b.fast_operator_[0].mass=1;a.fast_operator_[0].last=b.fast_operator_[0].last=0;
     a.advanceFast(0,256);b.advanceFast(0,256);check(near(a.fast_operator_[0].mass,.5),"Full half256");
     check(near(b.fast_operator_[0].mass,std::pow(.5,256./2048.)),"slow half2048");
     check(near(Full::nextDecay(256),UnifiedSlow2048::nextDecay(256)),"conditional decay unchanged");++tests;}
    {auto s=state();s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=0;s.operators[0].partitions[0].in_memory=false;s.memory_used-=100;
     Full a;NoPeriodicPrefetch b;a.active_=b.active_=true;
     auto x=a.onPeriodicAdjust(s),y=b.onPeriodicAdjust(s);check(x.size()==1&&x[0].type==Action::LOAD&&y.empty(),"periodic actions disabled");
     check(a.next_sample_q_==b.next_sample_q_&&near(a.coverage_,b.coverage_)&&near(a.fast_operator_[0].mass,b.fast_operator_[0].mass),"periodic observation retained");++tests;}
    {auto s=state(2,2);s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=0;s.memory_limit=s.memory_used;
     s.operators[1].partitions[0].in_memory=false;s.operators[1].partitions[1].in_memory=false;
     Full a;NoNextProtection b;initialize(a,s);initialize(b,s);for(int q=1;q<=128;++q){a.sampleNext(0,1,q);b.sampleNext(0,1,q);}
     std::vector<Action>x,y;a.propose(s,1,0,100,x,2);b.propose(s,1,0,100,y,2);
     check(x.size()==1&&x[0].partition_id==1&&y.size()==1&&y[0].partition_id==0,"next priority disabled current target excluded");++tests;}
    {auto s=state(1,3);s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=0;s.memory_limit=s.memory_used;s.operators[0].partitions[2].in_memory=false;
     Full a;NoNextProtection b;cycle(a,s,true);cycle(b,s,true);std::vector<Action>x,y;
     a.propose(s,0,2,100,x,2);b.propose(s,0,2,100,y,2);
     check(x[0].partition_id==1&&y[0].partition_id==0,"cycle next exclusion disabled");++tests;}
    {auto s=state(1,3);s.memory_limit=s.memory_used;s.operators[0].partitions[2].in_memory=false;s.operators[0].partitions[1].data_size=200;
     UnitMissCost a,b;Full f,g;initialize(a,s);initialize(b,s);initialize(f,s);initialize(g,s);std::vector<Action>x;
     a.propose(s,0,2,100,x,2);f.propose(s,0,2,100,x,2);auto t=s;t.read_bandwidth=2;t.write_bandwidth=1;
     b.propose(t,0,2,100,x,2);g.propose(t,0,2,100,x,2);
     check(near(priority(a,0,0)*100,priority(a,0,1)*200),"unit loss equal at equal reuse");
     check(near(priority(a,0,0),priority(b,0,0))&&!near(priority(f,0,0),priority(g,0,0)),"cost ranking bandwidth neutral");++tests;}
    {auto s=state(1,3);Full a;NoStructurePolicy b;cycle(a,s);cycle(b,s);a.analyzeCycle(s);b.analyzeCycle(s);
     check(a.uniform_cycle_&&!b.uniform_cycle_,"cycle route disabled");check(a.confirmed_edges_==b.confirmed_edges_&&a.successor_==b.successor_,"graph maintenance retained");++tests;}
    {auto s=state(1,3);s.memory_limit=s.memory_used;Full a;NoStructurePolicy b;initialize(a,s);initialize(b,s);
     a.last_op_=b.last_op_=0;a.last_pid_=b.last_pid_=0;a.streak_=b.streak_=6;a.stride_=b.stride_=1;a.observed_count_=b.observed_count_=10;
     a.step_distance_=b.step_distance_={3,1,2};std::vector<Action>x,y;a.propose(s,0,0,100,x,2);b.propose(s,0,0,100,y,2);
     check(!near(priority(a,0,1),priority(a,0,2))&&near(priority(b,0,1),priority(b,0,2)),"scan override disabled");
     check(a.streak_==b.streak_&&a.step_distance_==b.step_distance_,"stride maintenance retained");++tests;}
    {auto s=state();Full a;UniformOperatorMarginal b;initialize(a,s);initialize(b,s);uneven(a);uneven(b);a.ensureProbabilities(s);b.ensureProbabilities(s);
     const double prior=64./2;double am=a.operator_scale_[0]*(a.sharing_[0].mass+prior),bm=b.operator_scale_[0]*(b.sharing_[0].mass+prior);
     check(!near(am,.5)&&near(bm,.5),"operator marginal uniform");
     check(near(a.fast_operator_[0].mass,b.fast_operator_[0].mass)&&near(a.sharing_[0].share,b.sharing_[0].share),"operator observations and sharing retained");++tests;}
    std::cout<<"EFFECTIVENESS_PASS "<<tests<<"\n";return 0;
}
