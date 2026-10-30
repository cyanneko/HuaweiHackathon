"""Factorial ablation: subset selection before vs after the first visible Probe."""
from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
records={}
for base in ['pure_set1','pure_set025']:
    src=(OUT/(base+'.cpp')).read_text();key='''        if (!victims_.empty()) {''';assert src.count(key)==1
    for label,condition in [('after_probe','evidence'),('before_probe','!evidence'),('io_asymmetry','(evidence || s.read_bandwidth>=s.write_bandwidth)'),('all_probe','std::all_of(s.operators.begin(),s.operators.end(),[](const OperatorState& o){return o.phase==Phase::PROBE;})')]:
        s=src.replace(key,'        if ('+condition+' && !victims_.empty()) {')
        name=base+'_'+label;p=OUT/(name+'.cpp');p.write_text(s)
        records[name]={'parent':base,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'subset_active':label,'prune_active':'all memory/miss callbacks'}
(OUT/'COLD_ABLATIONS.json').write_text(json.dumps(records,indent=2)+'\n')
