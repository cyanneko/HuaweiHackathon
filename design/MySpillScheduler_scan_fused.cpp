// Single-file C++14 scheduler. Uses only SystemState, next_op and own history.
// Flags are for reproducible local ablations; the evaluator uses no arguments.
#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>

class MySpillScheduler final : public SpillScheduler {
    struct Victim { int o,p,id; int64_t bytes; double value,key; };
    struct Ghost { uint64_t at=0; int rule=-1; bool credited=false; int requester=-1; bool avoidable_cross=false; };
    int flags_,rule_=4,options_;
    uint64_t load_demands_=0,compensated_misses_=0;
    bool spilled_=false,first_miss_=false;
    std::array<uint64_t,512> last_{};
    std::array<float,512> heat_{};
    std::array<Ghost,512> ghost_{};
    std::array<double,8> op_heat_{},budget_{};
    std::array<uint64_t,8> op_last_{};
    std::array<double,7> loss_{};
    std::array<unsigned,7> trials_{};
    std::array<double,64> interference_{};
    std::array<uint64_t,64> interference_at_{};
    double interference(int source,int victim,uint64_t now) const {
        int i=source*8+victim;uint64_t age=now>interference_at_[i]?now-interference_at_[i]:0;
        return interference_[i]/(1.0+double(age)/256.0);
    }

    uint64_t epoch_=0,epoch_miss_=0,switched_at_=0,returns_=0,return_base_=0;
    int phase_mask_=-1;
    static uint64_t tick(const SystemState& s) {return uint64_t(s.hit_count+s.miss_count);}
    static bool probeNext(const SystemState& s) {return s.next_op.type=="PROBE";}
    static bool less(const Victim& a,const Victim& b) {
        if(a.key!=b.key)return a.key<b.key;
        if(a.bytes!=b.bytes)return a.bytes>b.bytes;
        return a.id>b.id;
    }
    static double clip(double x,double a,double b) {return std::max(a,std::min(b,x));}
    void observe(int id,int o,uint64_t now) {
        if(last_[id]==now)return;
        uint64_t age=now>last_[id]?now-last_[id]:0;
        heat_[id]=float(double(heat_[id])/(1.0+double(age)/64.0)+1.0);last_[id]=now;
        age=now>op_last_[o]?now-op_last_[o]:0;
        op_heat_[o]=op_heat_[o]/(1.0+double(age)/128.0)+1.0;op_last_[o]=now;
    }
    void observeNext(const SystemState& s) {
        if(!probeNext(s))return;
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
        if(s.operators[o].phase==Phase::PROBE)observe(o*s.num_partitions+p,o,tick(s)+1);
    }
    void credit(int rule,double loss) {
        if(rule<0)return;
        loss_[rule]=trials_[rule]?0.875*loss_[rule]+0.125*loss:loss;
        ++trials_[rule];
    }
    void loaded(const SystemState& s,int o,int p) {
        Ghost& g=ghost_[o*s.num_partitions+p];
        if(!g.at)return;
        uint64_t age=tick(s)+1-g.at,width=uint64_t(std::max(64,int(s.operators.size())*s.num_partitions*2));
        if(age<=width){if(g.rule>=0 || !(flags_&64))++returns_;if(!g.credited)credit(g.rule,1.0);}
        else if(!g.credited)credit(g.rule,0.0);
        if((flags_&1024)&&age<=width&&g.avoidable_cross) {
            int edge=g.requester*8+o;
            double bytes=double(s.operators[o].partitions[p].data_size);
            interference_[edge]=interference(g.requester,o,tick(s))+bytes/s.write_bandwidth+bytes/s.read_bandwidth+1.0;
            interference_at_[edge]=tick(s);++interference_returns;
        }
        g=Ghost();
    }
    void remember(const SystemState& s,const std::vector<Action>& a,int cause) {
        for(const auto& x:a) {
            if(x.type==Action::SPILL) {
                int id=x.op_id*s.num_partitions+x.partition_id;
                ghost_[id].at=tick(s)+1;
                // If victim and demand target cannot coexist, eviction is forced;
                // do not treat its return as evidence against a discretionary rule.
                ghost_[id].rule=((flags_&64)&&cause>=0&&s.operators[x.op_id].partitions[x.partition_id].data_size+demand_size_>s.memory_limit)?-1:cause;
                ghost_[id].credited=false;ghost_[id].requester=requester_;
                ghost_[id].avoidable_cross=requester_>=0&&requester_!=x.op_id&&s.operators[x.op_id].phase==Phase::PROBE&&
                    s.operators[x.op_id].partitions[x.partition_id].data_size+demand_size_<=s.memory_limit;
                if(x.op_id!=requester_)++cross_spills;
            } else loaded(s,x.op_id,x.partition_id);
        }
    }
    int requester_=-1;int64_t demand_size_=0;
    void allocate(const SystemState& s) {
        int k=int(s.operators.size());uint64_t now=tick(s);
        std::array<double,8> cap{},w{};std::array<bool,8> done{};
        for(const auto& op:s.operators) {
            for(const auto& x:op.partitions)cap[op.op_id]+=double(x.data_size);
            int o=op.op_id;uint64_t age=now>op_last_[o]?now-op_last_[o]:0;
            double h=op_heat_[o]/(1.0+double(age)/128.0);
            w[o]=(op.phase==Phase::PROBE?1.0:0.25)*(1.0+h);budget_[o]=0;
        }
        double remaining=double(s.memory_limit);
        for(int pass=0;pass<=k;++pass) {
            double sw=0;for(int o=0;o<k;++o)if(!done[o])sw+=w[o];
            if(sw<=0)break;
            bool capped=false;
            for(int o=0;o<k;++o)if(!done[o] && cap[o]<=remaining*w[o]/sw) {
                budget_[o]=cap[o];done[o]=true;capped=true;
            }
            if(!capped){for(int o=0;o<k;++o)if(!done[o])budget_[o]=remaining*w[o]/sw;break;}
            remaining=double(s.memory_limit);for(int o=0;o<k;++o)if(done[o])remaining-=budget_[o];
        }
        ++allocations;
    }
    void adapt(const SystemState& s,int o,int p) {
        uint64_t now=tick(s);int mask=phase_mask_;
        if(mask!=((1<<int(s.operators.size()))-1)){mask=0;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;}
        uint64_t observed_misses=(options_&8)?((options_&64)?uint64_t(s.miss_count)+compensated_misses_:load_demands_):uint64_t(s.miss_count);
        bool first=!first_miss_,urgent=returns_-return_base_>=3;
        if(!first && mask==phase_mask_ && now-epoch_<128 && observed_misses-epoch_miss_<32 && !urgent)return;
        uint64_t width=uint64_t(std::max(64,int(s.operators.size())*s.num_partitions*2));
        for(int i=0,q=int(s.operators.size())*s.num_partitions;i<q;++i){auto& g=ghost_[i];if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}}
        if(first) {
            first_miss_=true;
            if(flags_&32) {
                double a=double(s.operators[o].partitions[p].data_size)/s.memory_limit,b=-1;
                if(probeNext(s))b=double(s.operators[s.next_op.op_id].partitions[int(s.next_op.key%s.num_partitions)].data_size)/s.memory_limit;
                rule_=a<=.125?(b<=.0013453512706539845?3:4):(s.operators.size()<=1?4:3);
            }
        } else if(flags_&4) {
            double rate=std::min(1.0,double(observed_misses-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_)));
            int desired=(flags_&256)?rule_:4;
            // Positive evidence for a repeat working set favours heat/byte;
            // sustained misses without quick returns favour observed recency.
            if(urgent && rate>.12)desired=6;
            else if(rate>.65 && !urgent && !(flags_&128))desired=3;
            if((flags_&256)&&desired==rule_&&rule_!=4&&rate>.30&&loss_[rule_]>.50)desired=4;
            double best=loss_[desired]+(trials_[desired]?0.0:.12);
            for(int r:{4,3,6})if(trials_[r]>=4 && loss_[r]+.12<best){desired=r;best=loss_[r];}
            uint64_t dwell=urgent?8:64;
            if(desired!=rule_ && now-switched_at_>=dwell) {
                // Hysteresis prevents a tiny sampled advantage triggering a switch.
                if(urgent || desired==4 || !trials_[rule_] || loss_[rule_]>best+.08 || rate>.65) {
                    rule_=desired;switched_at_=now;++switches;
                }
            }
        }
        epoch_=now;epoch_miss_=observed_misses;return_base_=returns_;phase_mask_=mask;++epochs;
        if(flags_&8)allocate(s);
    }
    std::vector<Action> plan(const SystemState& s,int64_t need,int to,int tp,bool build,int po=-1,int pp=-1) {
        int64_t deficit=need-(s.memory_limit-s.memory_used);if(deficit<=0)return {};
        int rule=build?0:rule_;
        std::array<double,8> used{},factor{};factor.fill(1.0);
        bool quota=(flags_&8)!=0;
        if(build&&(options_&4)){bool has_probe=false;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)has_probe=true;if(!has_probe)quota=false;}
        if(quota && (build || !allocations))allocate(s);
        std::array<Victim,512> c;int n=0,best=-1;uint64_t now=tick(s);
        // Read the public partition table once. Preserve accumulation order,
        // candidate order, floating-point expressions and every tie-break.
        for(const auto& op:s.operators)for(const auto& x:op.partitions) {
            if(!x.in_memory)continue;
            int o=op.op_id,p=x.partition_id;
            if(quota)used[o]+=double(x.data_size);
            if(x.data_size<=0||(o==to&&p==tp)||(o==po&&p==pp))continue;
            c[n++]={o,p,o*s.num_partitions+p,x.data_size,0,0};
        }
        if(quota) {
            double pad=double(s.memory_limit)/(32.0*s.operators.size());
            for(unsigned o=0;o<s.operators.size();++o)factor[o]=clip((budget_[o]+pad)/(used[o]+pad),.5,2.0);
        }
        for(int i=0;i<n;++i) {
            int o=c[i].o,p=c[i].p,id=c[i].id;
            const auto& op=s.operators[o];const auto& x=op.partitions[p];
            double v=0,key=-double(x.data_size)/factor[o];
            if(rule==4) {
                uint64_t age=now>last_[id]?now-last_[id]:0;
                double h=double(heat_[id])/(1.0+double(age)/64.0),q=.15+.70*h/(1.0+h);
                if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)q=1.0;
                if(op.phase==Phase::BUILD)q*=.35;
                v=(double(x.data_size)/s.write_bandwidth+q*(double(x.data_size)/s.read_bandwidth+32.0))*factor[o];
                key=v/double(x.data_size);
            } else if(rule==3)key=(double(last_[id])+1.0)*factor[o];
            else if(rule==6) {
                uint64_t age=now>last_[id]?now-last_[id]:0;
                double h=double(heat_[id])/(1.0+double(age)/64.0);
                key=(1.0+h)*factor[o]/double(x.data_size);
                if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)key*=16.0;
            }
            if((flags_&1024)&&requester_>=0&&requester_!=o) {
                double unit=double(s.memory_limit)*(1.0/s.write_bandwidth+1.0/s.read_bandwidth)+1.0;
                double charge=1.0+std::min(3.0,interference(requester_,o,now)/unit);
                if(rule==0)key/=charge;else {key*=charge;v*=charge;}
            }
            c[i].value=v;c[i].key=key;if(best<0||less(c[i],c[best]))best=i;
        }
        // The sorted greedy prefix has length one in this case. Select the
        // same minimum-cost covering singleton in O(Q), preserving tie order.
        if((flags_&16) && best>=0 && c[best].bytes>=deficit) {
            int chosen=best;
            if(rule==4)for(int i=0;i<n;++i)if(c[i].bytes>=deficit &&
                (c[i].value<c[chosen].value || (c[i].value==c[chosen].value&&less(c[i],c[chosen]))))chosen=i;
            ++linear_plans;std::vector<Action> a;a.reserve(build?1:3);a.emplace_back(Action::SPILL,c[chosen].o,c[chosen].p);return a;
        }
        // Exact shortcut for a sorted greedy prefix of length two.
        // No heuristic truncation: all covering singletons are still compared.
        if(best>=0&&c[best].bytes<deficit) {
            int second=-1;
            for(int i=0;i<n;++i)if(i!=best&&(second<0||less(c[i],c[second])))second=i;
            if(second>=0&&c[best].bytes+c[second].bytes>=deficit) {
                int64_t freed=c[best].bytes+c[second].bytes;
                double value=c[best].value+c[second].value;int single=-1;
                if(rule==4)for(int i=0;i<n;++i)if(c[i].bytes>=deficit) {
                    if(c[i].value<value){single=i;value=c[i].value;}
                    else if(single>=0&&c[i].value==value&&less(c[i],c[single]))single=i;
                }
                std::vector<Action> a;a.reserve(2+(build?0:2));
                if(single>=0)a.emplace_back(Action::SPILL,c[single].o,c[single].p);
                else {
                    for(int i:{best,second}) {
                        if(rule==4&&freed-c[i].bytes>=deficit)freed-=c[i].bytes;
                        else a.emplace_back(Action::SPILL,c[i].o,c[i].p);
                    }
                }
                ++prefix2_plans;return a;
            }
        }
        ++sorted_plans;std::sort(c.begin(),c.begin()+n,less);
        int take=0;int64_t freed=0;double value=0;
        while(take<n&&freed<deficit){freed+=c[take].bytes;value+=c[take].value;++take;}
        if(rule==4) {
            int single=-1;for(int i=0;i<n;++i)if(c[i].bytes>=deficit&&c[i].value<value){single=i;value=c[i].value;}
            if(single>=0){std::vector<Action> a;a.reserve(build?1:3);a.emplace_back(Action::SPILL,c[single].o,c[single].p);return a;}
        }
        std::vector<Action> a;a.reserve(take+(build?0:2));
        for(int i=0;i<take;++i)if(rule==4&&freed-c[i].bytes>=deficit)freed-=c[i].bytes;
        else a.emplace_back(Action::SPILL,c[i].o,c[i].p);
        return a;
    }
    static int64_t written(const SystemState& s,const std::vector<Action>& a) {
        int64_t n=0;for(const auto& x:a)if(x.type==Action::SPILL)n+=s.operators[x.op_id].partitions[x.partition_id].data_size;return n;
    }
    // Local certificate: any resident x with size(x)>M-size(B) MUST leave
    // before B can be loaded. Only prefetch when these forced victims suffice.
    bool forced(const SystemState& s,int o,int p,int64_t need,std::vector<Action>& a,int64_t freed) {
        if(!(flags_&2)||need<s.memory_limit/2)return false;
        int64_t deficit=need-(s.memory_limit-s.memory_used+freed);if(deficit<=0)return true;
        std::array<bool,512> removed{};
        for(const auto& x:a)if(x.type==Action::SPILL)removed[x.op_id*s.num_partitions+x.partition_id]=true;
        std::vector<Action> extra;int64_t sum=0;
        for(const auto& op:s.operators)for(const auto& x:op.partitions) {
            if(x.in_memory&&x.data_size>s.memory_limit-need&&!removed[op.op_id*s.num_partitions+x.partition_id]&&!(op.op_id==o&&x.partition_id==p)) {
                extra.emplace_back(Action::SPILL,op.op_id,x.partition_id);sum+=x.data_size;
            }
        }
        if(sum<deficit)return false;
        a.insert(a.end(),extra.begin(),extra.end());++certified_prefetches;return true;
    }
public:
    uint64_t joint_loads=0,joint_rejections=0,prefix2_plans=0;
    uint64_t interference_returns=0;
    void externalSpill(){spilled_=true;}
    uint64_t switches=0,epochs=0,allocations=0,cross_spills=0,linear_plans=0,sorted_plans=0,advanced_builds=0,certified_prefetches=0;
    explicit MySpillScheduler(int options=105):flags_(351),options_(options){}
    int selectedMode() const {return rule_;}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t bytes) override {
        requester_=o;demand_size_=s.operators[o].partitions[p].data_size+bytes;auto a=plan(s,bytes,o,p,true);spilled_=true;remember(s,a,-1);return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        requester_=o;++load_demands_;loaded(s,o,p);adapt(s,o,p);observe(o*s.num_partitions+p,o,tick(s));observeNext(s);
        int64_t size=s.operators[o].partitions[p].data_size;demand_size_=size;
        if((options_&1)&&probeNext(s)) {
            int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);const auto& b=s.operators[no].partitions[np];
            int64_t limit=(options_&2)?s.memory_limit/2:((options_&16)?s.memory_limit*3/4:s.memory_limit);
            if(s.operators[no].phase==Phase::PROBE&&!b.in_memory&&!(no==o&&np==p)&&size+b.data_size<=limit&&
                (!(options_&64)||(rule_==6&&size+b.data_size<=s.memory_limit/2&&std::max(size,b.data_size)<=2*std::min(size,b.data_size)))) {
                auto a=plan(s,size+b.data_size,o,p,false);
                bool accept=true;
                int64_t tolerance=std::max(int64_t(16),(size+b.data_size)/256),sum=0;
                if(options_&(32|64))for(const auto& v:a){
                    int64_t bytes=s.operators[v.op_id].partitions[v.partition_id].data_size;sum+=bytes;
                    if(bytes>((options_&64)?std::max(size,b.data_size)+tolerance:size+b.data_size))accept=false;
                }
                if((options_&64)&&sum>size+b.data_size+tolerance)accept=false;
                if(accept){
                    if(options_&64){
                        int64_t prefix=0,needed=size-(s.memory_limit-s.memory_used);
                        for(const auto& v:a){if(prefix>=needed)break;prefix+=s.operators[v.op_id].partitions[v.partition_id].data_size;}
                        if(s.memory_limit-s.memory_used+prefix<size+b.data_size)++compensated_misses_;
                    }
                    if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                    a.emplace_back(Action::LOAD,no,np);a.emplace_back(Action::LOAD,o,p);
                    ++load_demands_;++joint_loads;demand_size_=size+b.data_size;remember(s,a,rule_);return a;
                }
                ++joint_rejections;
            }
        }
        auto a=plan(s,size,o,p,false);if(a.capacity()<a.size()+2)a.reserve(a.size()+2);int64_t freed=written(s,a);
        if(probeNext(s)) {
            int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);const auto& b=s.operators[no].partitions[np];
            if(s.operators[no].phase==Phase::PROBE&&!(no==o&&np==p)&&size+b.data_size<=s.memory_limit) {
                bool evicts=false;for(const auto& x:a)if(x.op_id==no&&x.partition_id==np)evicts=true;
                if(b.in_memory&&evicts) {
                    auto other=plan(s,size,o,p,false,no,np);int64_t f=written(s,other);
                    if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+1.0){a.swap(other);freed=f;}
                }
                // Forced-victim prefetch is used at periodic callbacks only.
                // Here the existing no-extra-spill joint load remains cheaper.
                if(!b.in_memory&&s.memory_used-freed+size+b.data_size<=s.memory_limit){a.emplace_back(Action::LOAD,no,np);++load_demands_;}
            }
        }
        a.emplace_back(Action::LOAD,o,p);remember(s,a,rule_);return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if((flags_&1)&&s.next_op.type=="INSERT") {
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(s.operators[o].partitions[p].in_memory&&s.next_op.tuple_size>s.memory_limit-s.memory_used) {
                requester_=o;demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;auto a=plan(s,s.next_op.tuple_size,o,p,true);spilled_=true;remember(s,a,-1);++advanced_builds;return a;
            }
            return {};
        }
        if(!spilled_||!probeNext(s))return {};
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);const auto& x=s.operators[o].partitions[p];
        if(s.operators[o].phase!=Phase::PROBE)return {};
        observe(o*s.num_partitions+p,o,tick(s)+1);
        if(x.in_memory)return {};
        requester_=o;demand_size_=x.data_size;std::vector<Action> a;
        if(x.data_size<=s.memory_limit-s.memory_used||forced(s,o,p,x.data_size,a,0)) {
            ++load_demands_;a.emplace_back(Action::LOAD,o,p);remember(s,a,-1);return a;
        }
        return {};
    }
};
