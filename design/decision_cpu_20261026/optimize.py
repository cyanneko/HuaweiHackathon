"""Create action-preserving optimizations before any fresh validation."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    s=(ROOT/'PreviousScheduler.cpp').read_text('utf8')
    s=s.replace('int flags_,rule_=4;','static constexpr int flags_=351;\n    int rule_=4;')
    s=s.replace('explicit MySpillScheduler(int flags=351):flags_(flags){}','MySpillScheduler()=default;')
    # Compile-time specialization, active-range scan, and guaranteed monotone phase.
    s=s.replace('if(!first && mask==phase_mask_', 'if(!first && mask==phase_mask_')
    s=s.replace('uint64_t now=tick(s);int mask=0;\n        for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;',
       'uint64_t now=tick(s);int mask=phase_mask_;\n        if(mask!=((1<<int(s.operators.size()))-1)){mask=0;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;}')
    s=s.replace('for(auto& g:ghost_)if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}',
       'for(int i=0,q=int(s.operators.size())*s.num_partitions;i<q;++i){auto& g=ghost_[i];if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}}')
    s=s.replace('return s.next_op.type=="PROBE";',"return !s.next_op.type.empty()&&s.next_op.type[0]=='P';")
    s=s.replace('s.next_op.type=="INSERT"',"(!s.next_op.type.empty()&&s.next_op.type[0]=='I')")
    # Remove fields and writes used only by a disabled ablation.
    s=s.replace(' int requester=-1; bool avoidable_cross=false;','')
    a=s.index('    std::array<double,64> interference_{};');b=s.index('    uint64_t epoch_',a);s=s[:a]+s[b:]
    a=s.index('        if((flags_&1024)&&age<=width');b=s.index('        g=Ghost();',a);s=s[:a]+s[b:]
    a=s.index('ghost_[id].credited=false;ghost_[id].requester=');b=s.index('                if(x.op_id!=requester_)',a)
    s=s[:a]+'ghost_[id].credited=false;\n'+s[b:]
    a=s.index('            if((flags_&1024)&&requester_');b=s.index('            c[n]={',a);s=s[:a]+s[b:]
    # Fuse quota sizing and resident accounting at BUILD pressure points.
    s=s.replace('void allocate(const SystemState& s) {','void allocate(const SystemState& s,std::array<double,8>* used=nullptr) {')
    s=s.replace('for(const auto& x:op.partitions)cap[op.op_id]+=double(x.data_size);',
       'for(const auto& x:op.partitions){cap[op.op_id]+=double(x.data_size);if(used&&x.in_memory)(*used)[op.op_id]+=double(x.data_size);}')
    s=s.replace('if(build || !allocations)allocate(s);\n            for(const auto& op:s.operators)for(const auto& x:op.partitions)if(x.in_memory)used[op.op_id]+=double(x.data_size);',
       'if(build || !allocations)allocate(s,&used);\n            else for(const auto& op:s.operators)for(const auto& x:op.partitions)if(x.in_memory)used[op.op_id]+=double(x.data_size);')
    # Track minimum covering singleton while candidate costs are already hot.
    s=s.replace('int n=0,best=-1;uint64_t now=tick(s);','int n=0,best=-1,cover=-1;uint64_t now=tick(s);')
    s=s.replace('c[n]={o,p,id,x.data_size,v,key};if(best<0||less(c[n],c[best]))best=n;++n;',
       'c[n]={o,p,id,x.data_size,v,key};if(best<0||less(c[n],c[best]))best=n;\n            if(x.data_size>=deficit&&(cover<0||v<c[cover].value||(v==c[cover].value&&less(c[n],c[cover]))))cover=n;\n            ++n;')
    s=s.replace('if(rule==4)for(int i=0;i<n;++i)if(c[i].bytes>=deficit &&\n                (c[i].value<c[chosen].value || (c[i].value==c[chosen].value&&less(c[i],c[chosen]))))chosen=i;',
       'if(rule==4)chosen=cover;')
    # Fast entirely-resident periodic path, preserving pre-overflow INSERT handling.
    s=s.replace('std::vector<Action> onPeriodicAdjust(const SystemState& s) override {\n',
       "std::vector<Action> onPeriodicAdjust(const SystemState& s) override {\n        if(!spilled_&&(s.next_op.type.empty()||s.next_op.type[0]!='I'))return {};\n")
    (ROOT/'StaticScheduler.cpp').write_text(s,encoding='utf8')
    # Stack plans contain SPILL choices only; the API result allocates once.
    loc=s.index('    struct Ghost')
    s=s[:loc]+'''    struct Pick {int o,p;};
    struct Plan {
        std::array<Pick,512> picks;int n=0;int64_t freed=0;
        Plan()=default;
        Plan(const Plan& b):n(b.n),freed(b.freed){std::copy_n(b.picks.begin(),n,picks.begin());}
        Plan& operator=(const Plan& b){if(this!=&b){n=b.n;freed=b.freed;std::copy_n(b.picks.begin(),n,picks.begin());}return *this;}
        void add(int o,int p,int64_t bytes){picks[n++]={o,p};freed+=bytes;}
    };
    static std::vector<Action> actions(const Plan& a,int spare=0){
        std::vector<Action> result;result.reserve(a.n+spare);
        for(int i=0;i<a.n;++i)result.emplace_back(Action::SPILL,a.picks[i].o,a.picks[i].p);
        return result;
    }
'''+s[loc:]
    s=s.replace('std::vector<Action> plan(const SystemState&','Plan plan(const SystemState&')
    s=s.replace('int64_t deficit=need-(s.memory_limit-s.memory_used);if(deficit<=0)return {};',
       'Plan result;int64_t deficit=need-(s.memory_limit-s.memory_used);if(deficit<=0)return result;',1)
    s=s.replace('++linear_plans;return {Action(Action::SPILL,c[chosen].o,c[chosen].p)};',
       '++linear_plans;result.add(c[chosen].o,c[chosen].p,c[chosen].bytes);return result;')
    s=s.replace('if(single>=0)return {Action(Action::SPILL,c[single].o,c[single].p)};',
       'if(single>=0){result.add(c[single].o,c[single].p,c[single].bytes);return result;}')
    s=s.replace('std::vector<Action> a;a.reserve(take);','')
    s=s.replace('else a.emplace_back(Action::SPILL,c[i].o,c[i].p);\n        return a;',
       'else result.add(c[i].o,c[i].p,c[i].bytes);\n        return result;')
    a=s.index('    static int64_t written(');b=s.index('    // Local certificate',a)
    s=s[:a]+s[b:]
    # All actual callbacks materialize the chosen plan once; metadata accounting
    # is unchanged and only sees that final legal action vector.
    a=s.index('    std::vector<Action> onMemoryOverflow(')
    s=s[:a]+'''    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t bytes) override {
        requester_=o;demand_size_=s.operators[o].partitions[p].data_size+bytes;
        auto a=actions(plan(s,bytes,o,p,true));spilled_=true;remember(s,a,-1);return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        requester_=o;loaded(s,o,p);adapt(s,o,p);observe(o*s.num_partitions+p,o,tick(s));observeNext(s);
        int64_t size=s.operators[o].partitions[p].data_size;demand_size_=size;
        Plan a=plan(s,size,o,p,false);bool preload=false;int no=-1,np=-1;
        if(probeNext(s)) {
            no=s.next_op.op_id;np=int(s.next_op.key%s.num_partitions);const auto& b=s.operators[no].partitions[np];
            if(s.operators[no].phase==Phase::PROBE&&!(no==o&&np==p)&&size+b.data_size<=s.memory_limit) {
                bool evicts=false;for(int i=0;i<a.n;++i)if(a.picks[i].o==no&&a.picks[i].p==np)evicts=true;
                if(b.in_memory&&evicts) {
                    Plan other=plan(s,size,o,p,false,no,np);
                    if(double(other.freed-a.freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+1.0)a=other;
                }
                preload=!b.in_memory&&s.memory_used-a.freed+size+b.data_size<=s.memory_limit;
            }
        }
        auto result=actions(a,preload?2:1);
        if(preload)result.emplace_back(Action::LOAD,no,np);
        result.emplace_back(Action::LOAD,o,p);remember(s,result,rule_);return result;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if(!spilled_&&(s.next_op.type.empty()||s.next_op.type[0]!='I'))return {};
        if(!s.next_op.type.empty()&&s.next_op.type[0]=='I') {
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(s.operators[o].partitions[p].in_memory&&s.next_op.tuple_size>s.memory_limit-s.memory_used) {
                requester_=o;demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;
                auto a=actions(plan(s,s.next_op.tuple_size,o,p,true));spilled_=true;remember(s,a,-1);++advanced_builds;return a;
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
            a.emplace_back(Action::LOAD,o,p);remember(s,a,-1);return a;
        }
        return {};
    }
};
'''
    (ROOT/'StackScheduler.cpp').write_text(s,encoding='utf8')
    print('Generated static specialization and stack plans.')
if __name__=='__main__':main()
