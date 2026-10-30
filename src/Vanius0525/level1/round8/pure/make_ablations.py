"""Two post-pilot single-factor ablations; never alter frozen main candidates."""
import hashlib,json
from pathlib import Path
F=Path(__file__).resolve().parent

def main():
    base=F/'paired_confidence.cpp';text=base.read_text();assert hashlib.sha256(base.read_bytes()).hexdigest()=='8c040b8778ab9afa60df432d393466b174c3faf2a691fef2c8c84fab000b6287'
    substitutions={'paired_sigma0':('immediate+64.0*mean+2.0*sd>=0','immediate+64.0*mean+0.0*sd>=0'),'paired_next0':('immediate+=sign[id]*(size/s.read_bandwidth+1.0);','immediate+=0.0*sign[id]*(size/s.read_bandwidth+1.0);')}
    sources={}
    for name,(old,new) in substitutions.items():
        assert text.count(old)==1
        s=text.replace(old,new);p=F/(name+'.cpp')
        if p.exists():assert p.read_text()==s
        else:p.write_text(s)
        sources[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    cases=json.loads((F/'PILOT_PLAN.json').read_text())['cases']
    plan={'post_pilot':True,'reason':'Separate 2-sigma filtering and explicit-next addition from other paired-wrapper changes; immediate-write coefficient1 and all-PROBE restriction remain unchanged.','base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'sources':sources,'cases':cases,'test_queries':0,'dev_queries':0,'new48_queries':0,'no_sweep':True,'scope':'same previously frozen80 train; global lock released each case'}
    p=F/'ABLATION_PLAN.json';raw=json.dumps(plan,indent=2)+'\n'
    if p.exists():assert p.read_text()==raw
    else:p.write_text(raw)
if __name__=='__main__':main()
