"""Test internal source bookkeeping with public visibility only in a test artifact."""
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put
CHECK=r'''
int main() {
    SystemState s{};s.num_partitions=16;s.memory_limit=67108864;
    s.read_bandwidth=s.write_bandwidth=1000;
    OperatorState o;o.op_id=0;o.phase=Phase::PROBE;o.partitions.resize(16);
    for(int i=0;i<16;++i){o.partitions[i].partition_id=i;o.partitions[i].data_size=1048576;}
    s.operators.push_back(o);s.memory_used=16*1048576;
    MySpillScheduler a;
    a.update(s);
    // Same pending request exposed by two sources; one mass, two provenance tags.
    s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=3;
    a.sampleNext(s,2);a.sampleNext(s,1);a.sampleNext(s,1);
    assert(a.sample_total_==1 && a.sample_count_[3]==1);
    assert(a.periodic_count_[3]==1 && a.after_miss_count_[3]==1 && a.sample_sources_==3);
    ++s.hit_count;a.sampleNext(s,1);
    assert(a.sample_total_==2 && a.sample_count_[3]==2);
    // Updating the current miss history must not add it to sampling mass.
    ++s.miss_count;a.update(s,0,5);
    assert(a.sample_count_[5]==0 && a.sample_total_==2);
    s.next_op.type="INSERT";a.sampleNext(s,1);assert(a.sample_total_==2);
    s.next_op.type="PROBE";s.hit_count=4096;s.next_op.key=6;a.sampleNext(s,2);
    assert(a.sample_count_[3]<0.501 && a.sample_count_[6]==1);
    double sum=0;for(int i=0;i<16;++i)sum+=a.probability(i);
    assert(std::abs(sum-1)<1e-12);
    assert(a.periodic_count_[3]==2 && a.after_miss_count_[3]==1);
    std::cout<<"source-dedup real-repeat miss-exclusion decay probability-sum passed\n";
}
'''
def main():
    reference=(ROOT/'build/round7_best_audit.cpp').read_text()
    declarations=reference[:reference.index('/* ===== 朴素调度器')]
    out=ROOT/'build/round7/sampling_checks';out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name in ['decay64','decay64_fixed_pool']:
        source=(ROOT/'round7'/(name+'.cpp')).read_text().replace('class MySpillScheduler : public SpillScheduler {','class MySpillScheduler : public SpillScheduler {\npublic:')
        path=out/(name+'.cpp');path.write_text(declarations+source+CHECK);exe=path.with_suffix('')
        subprocess.run(['g++','-std=c++14','-O2',str(path),'-o',str(exe)],check=True)
        p=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
        rows.append({'name':name,'stdout':p.stdout.strip()})
    put(ROOT/'round7/SAMPLING_CHECKS.json',(json.dumps(rows,indent=2)+'\n').encode());print(rows)
if __name__=='__main__':main()
