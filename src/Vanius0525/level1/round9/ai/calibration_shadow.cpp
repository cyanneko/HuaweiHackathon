// Offline audit only: real trajectory is always FrozenPolicy forced0.
// Supplied probabilities are explicit diagnostic/oracle inputs, never deployable features.
struct Query {int prefix;std::string method;std::vector<double> p;};
static std::vector<std::string> expected_trace;
static std::map<int,std::vector<Query>> audit_queries;
static int callback_index=0,shadow_count=0;

std::string traceLine(char tag,int op,int pid,int64_t bytes,const std::vector<Action>& a) {
    std::ostringstream out;out<<"TRACE "<<tag<<' '<<op<<' '<<pid<<' '<<bytes<<' '<<a.size();
    for(const auto& x:a)out<<' '<<(x.type==Action::SPILL?'S':'L')<<' '<<x.op_id<<' '<<x.partition_id;
    return out.str();
}
std::vector<Action> invoke(FrozenPolicy& policy,const SystemState& s,char tag,int op,int pid,int64_t bytes) {
    if(tag=='O')return policy.onMemoryOverflow(s,op,pid,bytes);
    if(tag=='M')return policy.onPartitionMiss(s,op,pid);
    return policy.onPeriodicAdjust(s);
}
void shadowRecord(const SystemState& s,char tag,int op,int pid,int64_t bytes,const Query& query,const std::vector<Action>& a) {
    const int n=s.operators.size()*s.num_partitions;
    std::string before(n,'0'),after;std::vector<int64_t> sizes(n);std::vector<bool> probe(n);
    for(const auto& o:s.operators)for(const auto& p:o.partitions){const int i=o.op_id*s.num_partitions+p.partition_id;before[i]=p.in_memory?'1':'0';sizes[i]=p.data_size;probe[i]=o.phase==Phase::PROBE;}
    after=before;int64_t used=s.memory_used,writes=0,reads=0,freed=0;std::set<std::pair<int,int>> seen;
    if(tag=='M' && (a.empty() || a.back().type!=Action::LOAD || a.back().op_id!=op || a.back().partition_id!=pid))throw std::runtime_error("shadow Miss last LOAD");
    const int next=s.next_op.type=="PROBE"?s.next_op.op_id*s.num_partitions+s.next_op.key%s.num_partitions:-1;
    bool next_spilled=false;
    for(const auto& x:a) {
        if(x.op_id<0 || x.op_id>=static_cast<int>(s.operators.size()) || x.partition_id<0 || x.partition_id>=s.num_partitions)throw std::runtime_error("shadow id");
        const int i=x.op_id*s.num_partitions+x.partition_id,t=x.type==Action::SPILL?0:1;
        if(!seen.emplace(t,i).second)throw std::runtime_error("shadow duplicate action");
        if(t==0) {
            if(after[i]!='1' || sizes[i]<=0 || (tag=='O' && x.op_id==op && x.partition_id==pid))throw std::runtime_error("shadow illegal SPILL");
            after[i]='0';writes+=sizes[i];freed+=sizes[i];used-=sizes[i];next_spilled|=i==next;
        }else {
            if(tag=='O' || after[i]!='0' || !probe[i])throw std::runtime_error("shadow illegal LOAD");
            after[i]='1';reads+=sizes[i];used+=sizes[i];
        }
        if(used<0 || used>s.memory_limit)throw std::runtime_error("shadow OOM");
    }
    if(tag=='O' && used+bytes>s.memory_limit)throw std::runtime_error("shadow insufficient release");
    std::cout<<"SHADOW "<<query.prefix<<' '<<query.method<<' '<<callback_index<<' '<<s.hit_count+s.miss_count<<' '<<tag<<' '<<op<<' '<<pid<<' '<<next<<' '<<writes<<' '<<reads<<' '<<freed<<' '<<next_spilled<<' '<<before<<' '<<after<<' '<<a.size();
    for(const auto& x:a)std::cout<<' '<<(x.type==Action::SPILL?'S':'L')<<' '<<x.op_id<<' '<<x.partition_id;
    std::cout<<'\n';++shadow_count;
}
class MySpillScheduler {
    FrozenPolicy actual;
    std::vector<Action> call(const SystemState& s,char tag,int op=-1,int pid=-1,int64_t bytes=0) {
        const auto found=audit_queries.find(callback_index);
        if(found!=audit_queries.end())for(const auto& q:found->second) {
            FrozenPolicy shadow=actual;if(q.method!="legacy")shadow.overrideProbabilities(q.p);
            shadowRecord(s,tag,op,pid,bytes,q,invoke(shadow,s,tag,op,pid,bytes));
        }
        auto a=invoke(actual,s,tag,op,pid,bytes);
        if(callback_index>=static_cast<int>(expected_trace.size()) || traceLine(tag,op,pid,bytes,a)!=expected_trace[callback_index])throw std::runtime_error("baseline TRACE mismatch callback "+std::to_string(callback_index));
        ++callback_index;return a;
    }
public:
    void forceMode(int mode){actual.forceMode(mode);}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z){return call(s,'O',op,pid,z);}
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid){return call(s,'M',op,pid);}
    std::vector<Action> onPeriodicAdjust(const SystemState& s){return call(s,'P');}
};
// SIM_DEFINITION
int main(int argc,char** argv) {
    if(argc!=4)return 2;
    std::ifstream trace(argv[2]);std::string line;
    while(std::getline(trace,line))if(line.compare(0,6,"TRACE ")==0)expected_trace.push_back(line);
    std::ifstream queries(argv[3]);int nqueries,nobjects;queries>>nqueries>>nobjects;
    for(int j=0;j<nqueries;++j){int callback;Query q;queries>>callback>>q.prefix>>q.method;q.p.resize(nobjects);for(auto& x:q.p)queries>>x;audit_queries[callback].push_back(q);}
    if(!queries)throw std::runtime_error("bad queries");
    std::ifstream in(argv[1]);int k,p,n,b,pen;int64_t m;double w,r;in>>k>>p>>m>>w>>r>>pen>>n>>b;
    Sim sim;sim.s.memory_limit=m;sim.s.num_partitions=p;sim.s.write_bandwidth=w;sim.s.read_bandwidth=r;sim.B=b;sim.penalty=pen;
    if(nobjects!=k*p)throw std::runtime_error("object count mismatch");
    for(int i=0;i<k;++i){int id,bc,pc;in>>id>>bc>>pc;OperatorState o;o.op_id=id;o.phase=Phase::BUILD;o.partitions.resize(p);for(int j=0;j<p;++j)o.partitions[j].partition_id=j;sim.s.operators.push_back(o);}
    std::vector<InputOp> ops;
    for(int i=0;i<n;++i){InputOp o;int64_t key=0;o.bytes=0;in>>o.type>>o.op;if(o.type!="SWITCH")in>>key;if(o.type=="INSERT")in>>o.bytes;o.pid=key%p;ops.push_back(o);}
    if(!in)throw std::runtime_error("bad input");
    MySpillScheduler policy;policy.forceMode(0);
    for(int i=0;i<n;++i)sim.step(ops,i,policy);
    if(callback_index!=static_cast<int>(expected_trace.size()) || shadow_count!=nqueries)throw std::runtime_error("incomplete audit");
    std::cout<<std::setprecision(17)<<"AUDIT "<<callback_index<<' '<<shadow_count<<' '<<sim.s.hit_count<<' '<<sim.s.miss_count<<' '<<sim.reads<<' '<<sim.writes<<' '<<sim.physical()<<'\n';
}
