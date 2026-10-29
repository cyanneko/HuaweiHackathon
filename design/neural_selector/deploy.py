"""Export embedded C++ weights using only the Python standard library."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
def scalar(x):
    s=format(float(x),'.9g');return s+('' if '.' in s or 'e' in s else '.0')+'f'
def array(x):return '{'+','.join(array(z) if isinstance(z,list) else scalar(z) for z in x)+'}'
def transpose(x):return [list(z) for z in zip(*x)]
def export(name,margin=0):
    obj=json.loads((ROOT/name).read_text());w=obj['weights'];h=obj['hidden'];bias=w['b2'][:];bias[7]+=margin
    code=f'''    static int network(const std::array<float,32>& x) {{
        static const float w1[{h}][32]={array(transpose(w['w1']))};
        static const float b1[{h}]={array(w['b1'])};
        static const float w2[8][{h}]={array(transpose(w['w2']))};
        static const float b2[8]={array(bias)};
        float hidden[{h}];
        for(int j=0;j<{h};++j){{float z=b1[j];for(int i=0;i<32;++i)z+=w1[j][i]*x[i];hidden[j]=std::max(0.0f,z);}}
        int best=0;float top=-1e30f;
        for(int j=0;j<8;++j){{float z=b2[j];for(int i=0;i<{h};++i)z+=w2[j][i]*hidden[i];if(z>top){{top=z;best=j;}}}}
        return best;
    }}
'''
    template=(ROOT/'Scheduler.template').read_text('utf8');(ROOT/'generated.cpp').write_bytes(template.replace('@@NETWORK@@',code).encode('utf8'))
    (ROOT/'active_model.json').write_text(json.dumps(dict(model=name,baseline_logit_margin=margin,hidden=h,parameters=obj['parameters']),indent=2))
if __name__=='__main__':export(sys.argv[1],float(sys.argv[2]) if len(sys.argv)>2 else 0)
