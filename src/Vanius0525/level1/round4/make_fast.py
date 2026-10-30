"""Implementation variants preserving per-neuron FP accumulation and subset order."""
from pathlib import Path
import json,re,hashlib,ast,math
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent

def vectorize(s):
    match=re.search(r'        double y = ([^;]+);\n        for \(int j=0;j<16;\+\+j\) \{\n            double v=B0\[j\]; for \(int i=0;i<12;\+\+i\) v\+=f\[i\]\*W0\[i\]\[j\];\n            if \(v>0\) y\+=v\*W1\[j\];\n        \}',s)
    assert match
    replacement='''        double v[16];
        for(int j=0;j<16;++j)v[j]=B0[j];
        for(int i=0;i<12;++i) {
            const double x=f[i];
            for(int j=0;j<16;++j)v[j]+=x*W0[i][j];
        }
        double y = BIAS;
        for(int j=0;j<16;++j)if(v[j]>0)y+=v[j]*W1[j];'''.replace('BIAS',match[1])
    return s[:match.start()]+replacement+s[match.end():]

def subset_dp(s):
    # Replace fixed <=4 subset recomputation; highest-bit recurrence retains ascending addition.
    pattern=r'''            (?:    )?for \(int mask=1;mask<\(1<<cap\);\+\+mask\) \{
                int64_t bytes=0;double loss=0;
                for \(int j=0;j<cap;\+\+j\) if\(mask&\(1<<j\)\) \{
                    const auto& v=victims_\[j\];bytes\+=v.bytes;
                    loss\+=v.priority\*v.bytes\+([^;]+);
                \}
                if\(bytes>=need && loss<best_loss\) \{best_loss=loss;best_mask=mask;\}
            \}'''
    m=re.search(pattern,s)
    if m is None:
        # Pure generator uses compact syntax and opposite assignment order.
        pattern=r'''            for\(int mask=1;mask<\(1<<cap\);\+\+mask\) \{
                int64_t bytes=0;double loss=0;
                for\(int j=0;j<cap;\+\+j\) if\(mask&\(1<<j\)\) \{
                    const auto& v=victims_\[j\];bytes\+=v.bytes;
                    loss\+=v.priority\*v.bytes\+([^;]+);
                \}
                if\(bytes>=need && loss<best_loss\) \{best_mask=mask;best_loss=loss;\}
            \}'''
        m=re.search(pattern,s)
    assert m
    addition=m[1]
    replacement='''            static const int highest[16]={0,0,1,1,2,2,2,2,3,3,3,3,3,3,3,3};
            int64_t subset_bytes[16]={0};double subset_loss[16]={0};
            double item_loss[4]={0};
            for(int j=0;j<cap;++j) {
                const auto& v=victims_[j];item_loss[j]=v.priority*v.bytes+ADDITION;
            }
            for(int mask=1;mask<(1<<cap);++mask) {
                const int j=highest[mask],prev=mask^(1<<j);
                subset_bytes[mask]=subset_bytes[prev]+victims_[j].bytes;
                subset_loss[mask]=subset_loss[prev]+item_loss[j];
                if(subset_bytes[mask]>=need && subset_loss[mask]<best_loss) {
                    best_loss=subset_loss[mask];best_mask=mask;
                }
            }'''.replace('ADDITION',addition)
    return s[:m.start()]+replacement+s[m.end():]

def main():
    mapping={'ai_fast':('MySpillSchedulerAI.cpp',True,False),'ai_prune_fast':('round4/ai_prune.cpp',True,False),'ai_set0_fast':('round4/ai_set0.cpp',True,True),'ai_set025_fast':('round4/ai_set025.cpp',True,True),'pure_set1_fast':('round4/pure_set1.cpp',False,True)}
    records={}
    for name,(parent,nn,dp) in mapping.items():
        raw=(BASE/parent).read_text();s=vectorize(raw) if nn else raw
        if dp:s=subset_dp(s)
        s=s.replace('''        const int64_t need=required-(s.memory_limit-s.memory_used);
        int64_t freed=0;''','''        if(a.size()<=1)return;
        const int64_t need=required-(s.memory_limit-s.memory_used);
        int64_t freed=0;''')
        target=OUT/(name+'.cpp');target.write_text(s)
        records[name]={'parent':parent,'parent_sha256':hashlib.sha256(raw.encode()).hexdigest(),'sha256':hashlib.sha256(s.encode()).hexdigest(),'neural_loop_interchange':nn,'subset_highest_bit_recurrence':dp,'claim':'same per-node accumulation order and same subset traversal; numerical/action equivalence still to test'}
    (OUT/'FAST_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
