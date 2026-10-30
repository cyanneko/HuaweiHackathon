"""Generate a readable strict extension of the frozen original audit."""
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent


def generate():
    base=HERE/'audit_return_risk_v1.py'
    assert hashlib.sha256(base.read_bytes()).hexdigest()=='478d13b221ebc71fa69ea89863d02646f90926b5d37cce4464f6fa169b8aeaf2'
    text=base.read_text()
    def change(old,new):
        nonlocal text
        assert text.count(old)==1,(old,text.count(old));text=text.replace(old,new,1)
    change('import numpy as np','import numpy as np\nfrom return_risk_scale_metrics_v1 import ScaleAttribution')
    change('def audit(path, stderr, final):','def audit_scale(path, stderr, final):\n    attribution=ScaleAttribution()')
    change('loss=np.zeros((3,k,7))','loss=np.zeros((4,k,7))')
    change('return np.stack((base,np.minimum(1,base*(rg+d)/(1+z)),np.minimum(1,base*(1+d)/(1+z))))',
           'g_all=(1+float(d.sum()))/(1+float(z.sum()))\n            return np.stack((base,np.minimum(1,base*(rg+d)/(1+z)),np.minimum(1,base*(1+d)/(1+z)),np.minimum(1,base*g_all)))')
    change('                        for model in range(3):','                        attribution.forecast((1+float(d.sum()))/(1+float(z.sum())),U,disk,hs)\n                        for model in range(4):')
    change("close(row['F'],fs,'F');assert row['choose']==choose","close(row['F'],fs[:3],'F');assert row['choose']==choose[:3]")
    change("                close(row['write_delta'],(freed[1]-freed[0])/w,'write_delta')", "                close(row['write_delta'],(freed[1]-freed[0])/w,'write_delta')\n                target=current if tag=='M' else pending_op[1]*p+pending_op[2]%p\n                need=max(0,int(sizes[target])-(m-used))\n                attribution.pair((1+float(d.sum()))/(1+float(z.sum())),choose,freed,[len(hist),len(dyn)],need,w)")
    change("    return {'all_observer_counters_match':True", "    return {'scale_attribution':attribution.export(loss,fields),'all_observer_counters_match':True")
    return '# Generated solely by make_return_risk_scale_v1.py; original three-model checks retained.\n'+text


if __name__=='__main__':
    path=HERE/'audit_return_risk_scale_v1.py';text=generate()
    if path.exists():assert path.read_text()==text
    else:path.write_text(text)
    print(hashlib.sha256(path.read_bytes()).hexdigest())
