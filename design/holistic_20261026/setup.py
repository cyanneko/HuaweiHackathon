import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;ROOT.mkdir(exist_ok=True)
OLD=ROOT.parent/'next_probe_20261026'
for n in ['reference_current.cpp','reference_types.hpp']:(ROOT/n).write_bytes((OLD/n).read_bytes())
base=(OLD/'MySpillScheduler_gated.cpp').read_text('utf8');(ROOT/'Previous.cpp').write_text(base,encoding='utf8')
s='#include <chrono>\n'+base
loc=s.index('    int flags_,rule_=4,options_;')
extras='''    static constexpr unsigned revision_features_=FEATURE_MASK;
    std::array<double,8> restore_pressure_{};
    std::array<uint64_t,8> restore_at_{};
    std::array<int64_t,1024> subset_bytes_;
    std::array<double,1024> subset_cost_;
    double search_spent_us_=0,search_ema_us_=1.0;
'''
s=s[:loc]+extras+s[loc:]
needle='''        if((flags_&1024)&&age<=width&&g.avoidable_cross) {'''
assert needle in s
s=s.replace(needle,'''        if((revision_features_&2)&&age<=width&&g.avoidable_cross) {
            uint64_t dt=tick(s)>restore_at_[o]?tick(s)-restore_at_[o]:0;
            double bytes=double(s.operators[o].partitions[p].data_size);
            restore_pressure_[o]=restore_pressure_[o]/(1.0+double(dt)/256.0)+bytes/s.write_bandwidth+bytes/s.read_bandwidth+32.0;
            restore_at_[o]=tick(s);++restore_updates;
        }
'''+needle)
needle='''            w[o]=(op.phase==Phase::PROBE?1.0:0.25)*(1.0+h);budget_[o]=0;'''
assert needle in s
s=s.replace(needle,needle+'''
            if(revision_features_&2) {
                uint64_t dt=now>restore_at_[o]?now-restore_at_[o]:0;
                double pressure=restore_pressure_[o]/(1.0+double(dt)/256.0);
                double unit=double(s.memory_limit)*(1.0/s.write_bandwidth+1.0/s.read_bandwidth)+32.0;
                w[o]*=1.0+std::min(2.0,pressure/unit);
            }''')
# Extra BUILD victims appear only after the single-demand greedy prefix.
needle='''                if((options_&64)&&sum>size+b.data_size+tolerance)accept=false;
                if(accept){'''
assert needle in s
s=s.replace(needle,'''                if((options_&64)&&sum>size+b.data_size+tolerance)accept=false;
                if(revision_features_&1) {
                    int64_t prefix=0,needed=size-(s.memory_limit-s.memory_used);
                    for(const auto& v:a){
                        if(prefix>=needed&&s.operators[v.op_id].phase==Phase::BUILD){accept=false;++stage_rejections;}
                        prefix+=s.operators[v.op_id].partitions[v.partition_id].data_size;
                    }
                }
                if(accept){''')
# Small-n model refinement. Its CPU is charged to a visible-cost budget.
loc=s.index('    std::vector<Action> plan(')
helper='''    std::vector<Action> refineCover(const SystemState& s,const std::array<Victim,512>& c,int n,
            std::vector<Action> incumbent,int64_t deficit,int rule,bool build) {
        if(!(revision_features_&4)||build||rule!=4||n<2||n>10)return incumbent;
        double current=0,min_density=1e300;
        for(int i=0;i<n;++i){min_density=std::min(min_density,c[i].value/double(c[i].bytes));
            for(const auto& a:incumbent)if(a.op_id==c[i].o&&a.partition_id==c[i].p)current+=c[i].value;
        }
        if(current-min_density*double(deficit)<=std::max(.25,2.0*search_ema_us_))return incumbent;
        double allowance=.001*(double(s.total_io_bytes)/std::max(s.write_bandwidth,s.read_bandwidth)+double(s.miss_count));
        if(search_spent_us_+4.0*search_ema_us_>allowance)return incumbent;
        auto start=std::chrono::steady_clock::now();double before=search_spent_us_;
        subset_bytes_[0]=0;subset_cost_[0]=0;unsigned best_mask=0;double best=current;
        unsigned stop=1u<<n;bool complete=true;
        for(unsigned mask=1;mask<stop;++mask){
            unsigned bit=mask&(~mask+1),idx=0;while((1u<<idx)!=bit)++idx;
            unsigned prev=mask^bit;
            subset_bytes_[mask]=subset_bytes_[prev]+c[idx].bytes;
            subset_cost_[mask]=subset_cost_[prev]+c[idx].value;
            if(subset_bytes_[mask]>=deficit&&subset_cost_[mask]<best){best=subset_cost_[mask];best_mask=mask;}
            if((mask&63u)==0){double elapsed=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
                if(before+elapsed>=allowance){complete=false;break;}
            }
        }
        double elapsed=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        search_spent_us_+=elapsed;search_ema_us_=.875*search_ema_us_+.125*elapsed;++cover_searches;
        if(complete)++cover_completed;
        if(!best_mask||current-best<=std::max(.25,2.0*elapsed))return incumbent;
        std::vector<Action> result;result.reserve(n+2);
        for(int i=0;i<n;++i)if(best_mask&(1u<<i))result.emplace_back(Action::SPILL,c[i].o,c[i].p);
        ++cover_accepts;return result;
    }
'''
s=s[:loc]+helper+s[loc:]
# Necessary-victim shortcut for large requests. Avoid cases with a co-fitting
# next disk target, where additional free space could change known prefetch.
needle='''        int rule=build?0:rule_;'''
assert needle in s
s=s.replace(needle,'''        if(revision_features_&8) {
            int64_t full=build?s.operators[to].partitions[tp].data_size+need:need;
            bool next_disk_pair=false;
            if(probeNext(s)) {
                int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);
                const auto& nx=s.operators[no].partitions[np];
                next_disk_pair=!(no==to&&np==tp)&&!nx.in_memory&&s.operators[no].phase==Phase::PROBE&&full+nx.data_size<=s.memory_limit;
            }
            if(full>s.memory_limit/2&&!next_disk_pair) {
                int count=0;int64_t sum=0;
                for(const auto& op:s.operators)for(const auto& x:op.partitions)
                    if(x.in_memory&&x.data_size>s.memory_limit-full&&!(op.op_id==to&&x.partition_id==tp)&&!(op.op_id==po&&x.partition_id==pp)){sum+=x.data_size;++count;}
                if(sum>=deficit){
                    std::vector<Action> a;a.reserve(count+(build?0:2));
                    for(const auto& op:s.operators)for(const auto& x:op.partitions)
                        if(x.in_memory&&x.data_size>s.memory_limit-full&&!(op.op_id==to&&x.partition_id==tp)&&!(op.op_id==po&&x.partition_id==pp))a.emplace_back(Action::SPILL,op.op_id,x.partition_id);
                    ++forced_plans;return a;
                }
            }
        }
'''+needle,1)
a=s.index('    std::vector<Action> plan(');b=s.index('    static int64_t written',a)
part=s[a:b]
part=part.replace('return a;', 'return refineCover(s,c,n,std::move(a),deficit,rule,build);')
# The mandatory return precedes declarations of c/n/rule, so it stays direct.
part=part.replace('++forced_plans;return refineCover(s,c,n,std::move(a),deficit,rule,build);','++forced_plans;return a;')
s=s[:a]+part+s[b:]
s=s.replace('    uint64_t joint_loads=0,','    uint64_t stage_rejections=0,restore_updates=0,cover_searches=0,cover_completed=0,cover_accepts=0,forced_plans=0;\n    double searchSpentUs()const{return search_spent_us_;}\n    uint64_t joint_loads=0,')
profiles={'staged':1,'pressure':3,'cover':5,'mandatory':9,'pressure_cover':7,'stage_cover_mandatory':13,'integrated':15}
for name,mask in profiles.items():(ROOT/(name+'.cpp')).write_text(s.replace('FEATURE_MASK',str(mask)),encoding='utf8')
(ROOT/'Policy.template').write_text(s,encoding='utf8')
e=(OLD/'experiment.py').read_text('utf8');a=e.index('PROFILES=');b=e.index('\ndef compile_all',a)
e=e[:a]+"PROFILES={'baseline':None,'previous':'Previous.cpp',"+','.join(repr(k)+':'+repr(k+'.cpp') for k in profiles)+"}\n"+e[b:]
(ROOT/'experiment.py').write_text(e,encoding='utf8')
rows=[]
for prefix,folder in [('older','validation'),('recent','refined_validation')]:
    for row in json.loads((OLD/folder/'manifest.json').read_text()):row['id']=prefix+'_'+row['id'];rows.append(row)
(ROOT/'development_manifest.json').write_text(json.dumps(rows,indent=2));(ROOT/'scale_manifest.json').write_bytes((OLD/'scale_manifest.json').read_bytes())
print('Prepared',len(rows),'development cases and',len(profiles),'revision ablations.')
