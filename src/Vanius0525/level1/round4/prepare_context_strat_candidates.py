"""Preserve trained raw variants; align runtime with the training feature-support filter."""
from pathlib import Path
import json,re,hashlib
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
report=json.loads((OUT/'CONTEXT_STRAT_TRAINING.json').read_text());records={}
for name,d in report['models'].items():
    parent=OUT/(name+'.cpp');raw=parent.read_text();assert hashlib.sha256(raw.encode()).hexdigest()==d['sha256']
    s=raw
    key='''        float gf[12];gateFeatures(s,op,pid,required,gf);
        const int mode=forced_mode_>=0?forced_mode_:gate(gf);last_mode_=mode;'''
    assert key in s
    s=s.replace(key,'''        int mode=forced_mode_;
        if(mode<0){float gf[12];gateFeatures(s,op,pid,required,gf);mode=gate(gf);}
        last_mode_=mode;''')
    key='''            float af[8],f[30];family_.actionFeatures(s,trial,af);
            for(int j=0;j<12;++j)f[j]=context[j];''';assert key in s
    s=s.replace(key,'''            float af[8],f[30];family_.actionFeatures(s,trial,af);
            bool feature_difference=false;
            for(int j=0;j<8;++j)if(af[j]!=bf[j])feature_difference=true;
            if(!feature_difference)continue;
            for(int j=0;j<12;++j)f[j]=context[j];''')
    target_name=name+'_support';target=OUT/(target_name+'.cpp');target.write_text(s)
    records[target_name]={'parent':name,'parent_sha256':d['sha256'],'sha256':hashlib.sha256(s.encode()).hexdigest(),'depth':d['depth'],'margin':d['margin'],'changes':['skip alternative when all action features equal baseline, matching the training filter','avoid unused global feature recomputation in forced internal modes'],'training_report':'CONTEXT_STRAT_TRAINING.json','training_scope':'train-only weights; architecture/features informed by exposed data; final external validation required'}
(OUT/'CONTEXT_STRAT_FINAL_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
