"""Conservative legal-observation gates; no case-name or input-stream access."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
base=(BASE/'MySpillSchedulerAI.cpp').read_text()
# Ensure fair comparison: prune-only is the immediate parent for every guard.
from make_variants import pruning
base=pruning(base)
records={}
for guard in ['all_seen','top_seen','warm8','warm32','credit']:
 s=base
 key='''            for (int j=0;j<cap;++j) {
                auto& v=victims_[j];float f[12];features(s,v.op,v.pid,need,op,f);'''
 checks={
  'all_seen':'''            bool use_nn=true;
            for(int j=0;j<cap;++j)if(history_[victims_[j].op*p_+victims_[j].pid].last<0)use_nn=false;
''',
  'top_seen':'''            bool use_nn=history_[victims_[0].op*p_+victims_[0].pid].last>=0;
''',
  'warm8':'''            bool use_nn=observed_count_>=8;
''',
  'warm32':'''            bool use_nn=observed_count_>=32;
''',
  'credit':'''            bool use_nn=nn_credit_>=0.;
'''}
 assert key in s
 s=s.replace(key,checks[guard]+'''            for (int j=0;j<cap && use_nn;++j) {
                auto& v=victims_[j];float f[12];features(s,v.op,v.pid,need,op,f);''')
 if guard=='credit':
  s=s.replace('bool active_ = false;','''bool active_ = false;
    double nn_credit_=0.;
    std::vector<int64_t> nn_spill_;
    void feedback(const SystemState& s,int op,int pid) {
        if(nn_spill_.size()!=history_.size())nn_spill_.assign(history_.size(),-1);
        const int id=op*p_+pid;
        const int64_t q=s.hit_count+s.miss_count;
        if(nn_spill_[id]>=0) {
            const int64_t gap=std::max<int64_t>(0,q-nn_spill_[id]);
            nn_credit_+=gap<64?-1.:.25;nn_spill_[id]=-1;
        }
        nn_credit_=std::min(4.,std::max(-4.,nn_credit_+.01));
    }
''')
  # Only assign blame to deviations from the original heuristic's first choice.
  s=s.replace('''            bool use_nn=nn_credit_>=0.;''','''            const int base_id=victims_[0].op*p_+victims_[0].pid;
            bool use_nn=nn_credit_>=0.;''')
  s=s.replace('''                const auto& v=victims_[j];actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;''','''                const auto& v=victims_[j];actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
                if(use_nn && v.op*p_+v.pid!=base_id) {
                    if(nn_spill_.size()!=history_.size())nn_spill_.assign(history_.size(),-1);
                    nn_spill_[v.op*p_+v.pid]=s.hit_count+s.miss_count;
                }''',1)
  s=s.replace('''active_ = true; update(s,op,pid); std::vector<Action> a;''','''active_ = true; update(s,op,pid); feedback(s,op,pid); std::vector<Action> a;''')
 if guard=='credit':
  s=s.replace('if (freed-size>=need) {freed-=size;continue;}', 'if (freed-size>=need) {freed-=size;if(nn_spill_.size()==history_.size() && nn_spill_[x.op_id*p_+x.partition_id]==s.hit_count+s.miss_count)nn_spill_[x.op_id*p_+x.partition_id]=-1;continue;}')
 name='ai_guard_'+guard;path=OUT/(name+'.cpp');path.write_text(s)
 records[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'base':'ai_prune','guard':guard,'note':'credit is local delayed feedback, not unbiased expert regret or a robustness guarantee'}
(OUT/'GUARD_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
