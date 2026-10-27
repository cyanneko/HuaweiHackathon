from pathlib import Path
ROOT=Path(__file__).resolve().parent
src=ROOT/'PairScheduler.cpp';s=src.read_text('utf8');(ROOT/'PairScheduler_slow.cpp').write_text(s,encoding='utf8')
needle='''        ++sorted_plans;std::sort(c.begin(),c.begin()+n,less);'''
assert needle in s
fast='''        // Exact shortcut for a sorted greedy prefix of length two.
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
'''
s=s.replace(needle,fast+needle)
s=s.replace('uint64_t joint_loads=0,joint_rejections=0;','uint64_t joint_loads=0,joint_rejections=0,prefix2_plans=0;')
s=s.replace('explicit MySpillScheduler(int options=15)', 'explicit MySpillScheduler(int options=41)')
src.write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8')
e=e.replace("'guard_physical':133}","'guard_physical':133,'selected':141,'slow_selected':'SlowSelected.cpp'}")
(ROOT/'SlowSelected.cpp').write_text('#define MySpillScheduler SlowPolicy\n#include "PairScheduler_slow.cpp"\n#undef MySpillScheduler\nclass MySpillScheduler final : public SpillScheduler {\n    SlowPolicy inner_{41};\npublic:\n    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t b)override{return inner_.onMemoryOverflow(s,o,p,b);}\n    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return inner_.onPartitionMiss(s,o,p);}\n    std::vector<Action> onPeriodicAdjust(const SystemState& s)override{return inner_.onPeriodicAdjust(s);}\n};\n',encoding='utf8')
# SlowSelected wrapper adds a virtual forward; replace by direct default change
# so timing comparison isolates prefix2, not an extra call layer.
(ROOT/'SlowSelected.cpp').write_text((ROOT/'PairScheduler_slow.cpp').read_text().replace('int options=15','int options=41'),encoding='utf8')
(ROOT/'experiment.py').write_text(e,encoding='utf8')
print('Prepared exact two-victim prefix shortcut; selected options=41.')
