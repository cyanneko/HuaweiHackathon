"""Isolate probability saturation, then replace all-object median with cold mass quantiles."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from round6.prepare import put
ROOT=Path(__file__).resolve().parent
CORE=r'''    void refreshCore(const SystemState& s) {
        struct Item {int id; int64_t size; double density, probability;};
        std::vector<Item> items;
        double mass=0, discrepancy=0;
        for(const auto& o:s.operators) for(const auto& x:o.partitions) {
            if(o.phase!=Phase::PROBE || x.data_size<=0)continue;
            int id=o.op_id*p_+x.partition_id;
            double prob=probability(id);
            items.push_back({id,x.data_size,prob*(1.0/s.read_bandwidth+1.0/s.write_bandwidth+1.0/x.data_size),prob});
            mass+=prob;
        }
        if(items.empty() || sample_total_<64) {std::fill(core_.begin(),core_.end(),false);return;}
        for(const auto& x:items)discrepancy+=std::abs(x.probability/mass-1.0/items.size());
        // No statistical hotspot claim: a conservative fixed concentration gate.
        if(discrepancy<0.30) {std::fill(core_.begin(),core_.end(),false);return;}
        std::sort(items.begin(),items.end(),[&](const Item& a,const Item& b){
            double da=a.density*(core_[a.id]?1.1:1.0),db=b.density*(core_[b.id]?1.1:1.0);
            return da!=db?da>db:a.id<b.id;
        });
        // Provisional packing identifies the tail. Budget is its request-weighted
        // size quantile; it is not empty memory and never a legality constraint.
        int64_t available=s.memory_limit;
        std::vector<Item> cold;
        for(const auto& x:items) {
            if(x.size<=available)available-=x.size;
            else cold.push_back(x);
        }
        double cold_mass=0;
        for(const auto& x:cold)cold_mass+=x.probability;
        std::sort(cold.begin(),cold.end(),[](const Item& a,const Item& b){
            return a.size!=b.size?a.size<b.size:a.id<b.id;
        });
        int64_t reserve=0;double cumulative=0;
        if(QUANTILE>0 && cold_mass>0)for(const auto& x:cold) {
            cumulative+=x.probability;reserve=x.size;
            if(cumulative>=QUANTILE*cold_mass)break;
        }
        available=std::max<int64_t>(0,s.memory_limit-reserve);
        std::fill(core_.begin(),core_.end(),false);
        for(const auto& x:items)if(x.size<=available){core_[x.id]=true;available-=x.size;}
    }
'''
def main():
    for pool in ['', '_fixed_pool']:
        s=(ROOT/('mixed64'+pool+'.cpp')).read_text()
        assert s.count('std::min(1.0,64.0*probability(o.op_id*p_+part.partition_id))')==1
        s=s.replace('std::min(1.0,64.0*probability(o.op_id*p_+part.partition_id))','64.0*probability(o.op_id*p_+part.partition_id)')
        put(ROOT/('linear64'+pool+'.cpp'),s.encode())
    for name,q in [('core0',0.0),('core50',0.5),('core90',0.9)]:
        s=(ROOT/'linear64.cpp').read_text()
        a=s.index('    void refreshCore(');b=s.index('    void observe(',a)
        s=s[:a]+CORE.replace('QUANTILE',str(q))+s[b:]
        s=s.replace('        victims_.clear();','        refreshCore(s);\n        victims_.clear();')
        s=s.replace('            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;',
                    '            if(core_[o.op_id*p_+part.partition_id]) priority*=2.0;\n            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;')
        put(ROOT/(name+'.cpp'),s.encode())
if __name__=='__main__':main()
