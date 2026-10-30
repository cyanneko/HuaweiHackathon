"""Mechanism-driven variants; frozen submissions never overwritten."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
HELPER='''
    void pruneSpills(const SystemState& s, int64_t required, std::vector<Action>& a) {
        const int64_t need=required-(s.memory_limit-s.memory_used);
        int64_t freed=0;
        for (const auto& x:a) freed+=s.operators[x.op_id].partitions[x.partition_id].data_size;
        size_t keep=0;
        for (const auto& x:a) {
            const int64_t size=s.operators[x.op_id].partitions[x.partition_id].data_size;
            if (freed-size>=need) {freed-=size;continue;}
            a[keep++]=x;
        }
        a.erase(a.begin()+keep,a.end());
    }
'''
def pruning(src):
    src=src.replace('public:\n',HELPER+'public:\n')
    src=src.replace('release(s,op,pid,z,a); return a;', 'release(s,op,pid,z,a); pruneSpills(s,z,a); return a;')
    src=src.replace('a.emplace_back(Action::LOAD,op,pid); return a;', 'pruneSpills(s,s.operators[op].partitions[pid].data_size,a);\n        a.emplace_back(Action::LOAD,op,pid); return a;')
    # Periodic currently only loads using free space; no release call there.
    return src

def costset(src,weight,blend=None):
    if blend is not None:
        src=src.replace('v.priority=neural(f)*(1/s.read_bandwidth+1/s.write_bandwidth+1.0/v.bytes);', f'v.priority={blend}*v.priority+{1-blend}*neural(f)*(1/s.read_bandwidth+1/s.write_bandwidth+1.0/v.bytes);')
    mark='''            std::sort(victims_.begin(),victims_.begin()+cap,less);
            int64_t freed=0;'''
    inject='''            // Fixed four-candidate subset search, not a global knapsack oracle.
            // Score sums predicted downstream loss plus immediate write cost.
            int best_mask=0; double best_loss=1e300;
            for (int mask=1;mask<(1<<cap);++mask) {
                int64_t bytes=0;double loss=0;
                for (int j=0;j<cap;++j) if(mask&(1<<j)) {
                    const auto& v=victims_[j];bytes+=v.bytes;
                    loss+=v.priority*v.bytes+WEIGHT*static_cast<double>(v.bytes)/s.write_bandwidth;
                }
                if(bytes>=need && loss<best_loss) {best_loss=loss;best_mask=mask;}
            }
            if(best_mask) {
                for(int j=0;j<cap;++j) if(best_mask&(1<<j))
                    actions.emplace_back(Action::SPILL,victims_[j].op,victims_[j].pid);
                return;
            }
'''.replace('WEIGHT',str(weight))
    assert mark in src
    return src.replace(mark,inject+mark)

def pure_set(src,weight):
    mark='''        if (!evidence) {'''
    inject='''        if (!victims_.empty()) {
            auto less=better;
            const int cap=std::min<int>(4,victims_.size());
            std::partial_sort(victims_.begin(),victims_.begin()+cap,victims_.end(),less);
            int best_mask=0;double best_loss=1e300;
            for(int mask=1;mask<(1<<cap);++mask) {
                int64_t bytes=0;double loss=0;
                for(int j=0;j<cap;++j) if(mask&(1<<j)) {
                    const auto& v=victims_[j];bytes+=v.bytes;
                    loss+=v.priority*v.bytes+WEIGHT*static_cast<double>(v.bytes)/s.write_bandwidth;
                }
                if(bytes>=need && loss<best_loss) {best_mask=mask;best_loss=loss;}
            }
            if(best_mask) {
                for(int j=0;j<cap;++j) if(best_mask&(1<<j))
                    actions.emplace_back(Action::SPILL,victims_[j].op,victims_[j].pid);
                return;
            }
        }
'''.replace('WEIGHT',str(weight))
    assert mark in src
    return src.replace(mark,inject+mark)

def main():
    pure=(BASE/'MySpillScheduler.cpp').read_text();ai=(BASE/'MySpillSchedulerAI.cpp').read_text()
    variants={'pure_prune':pruning(pure),'ai_prune':pruning(ai),
      'pure_set025':pruning(pure_set(pure,.25)),'pure_set1':pruning(pure_set(pure,1.)),
      'ai_set0':pruning(costset(ai,0.)),'ai_set025':pruning(costset(ai,.25)),
      'ai_set1':pruning(costset(ai,1.)),'ai_blend_set':pruning(costset(ai,.25,.5))}
    records={}
    for name,src in variants.items():
        target=OUT/(name+'.cpp')
        target.write_text(src)
        records[name]={'sha256':hashlib.sha256(src.encode()).hexdigest(),'base':'ai' if name.startswith('ai') else 'pure','trained_weights':'frozen original' if name.startswith('ai') else None}
    (OUT/'VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
