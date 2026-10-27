from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=ROOT/'PairScheduler.cpp';s=source.read_text('utf8');(ROOT/'PairScheduler_v1.cpp').write_text(s,encoding='utf8')
needle='''                if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                a.emplace_back(Action::LOAD,no,np);a.emplace_back(Action::LOAD,o,p);
                ++load_demands_;++joint_loads;demand_size_=size+b.data_size;remember(s,a,rule_);return a;'''
assert needle in s
s=s.replace(needle,'''                bool accept=true;
                if(options_&32)for(const auto& v:a)if(s.operators[v.op_id].partitions[v.partition_id].data_size>size+b.data_size)accept=false;
                if(accept){
                    if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                    a.emplace_back(Action::LOAD,no,np);a.emplace_back(Action::LOAD,o,p);
                    ++load_demands_;++joint_loads;demand_size_=size+b.data_size;remember(s,a,rule_);return a;
                }
                ++joint_rejections;''')
s=s.replace('uint64_t joint_loads=0;','uint64_t joint_loads=0,joint_rejections=0;')
source.write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'pair_threequarter':125}","'pair_threequarter':125,'guard_feedback':141,'guard_build_feedback':145,'guard_half_build_feedback':147,'guard_physical':133}")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
print('Added a guard against evicting a partition larger than both known targets combined.')
