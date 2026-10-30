"""Freeze the one deferred offline contrast without opening large traces."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def put(path,text):
    if path.exists():assert path.read_text()==text,path
    else:path.write_text(text)


def main():
    raw=(HERE/'audit_return_risk_scale_v1.py').read_text()
    raw=raw.replace('from return_risk_scale_metrics_v1 import ScaleAttribution','from return_risk_scale_metrics_v1 import ScaleAttribution\nfrom risk_coscale_metrics_v1 import CoscaleAttribution')
    raw=raw.replace('def audit_scale(path, stderr, final):','def audit_coscale(path, stderr, final):')
    raw=raw.replace('    attribution=ScaleAttribution()','    attribution=ScaleAttribution()\n    coscale=CoscaleAttribution()')
    old='                attribution.pair((1+float(d.sum()))/(1+float(z.sum())),choose,freed,[len(hist),len(dyn)],need,w)'
    assert raw.count(old)==1
    new=old+'\n                g=(1+float(d.sum()))/(1+float(z.sum()))\n                coscale.pair(g,bool(np.all(g*base<=1.0)),effective,I,fs[3],risk,choose[3],freed,[len(hist),len(dyn)],need,w)'
    raw=raw.replace(old,new)
    old="return {'scale_attribution':attribution.export(loss,fields)"
    assert raw.count(old)==1;raw=raw.replace(old,"return {'risk_coscale':coscale.export(),'scale_attribution':attribution.export(loss,fields)")
    put(HERE/'audit_risk_coscale_v1.py','# Derived only by prepare_risk_coscale_v1.py; original four-model audit retained.\n'+raw)
    previous=json.loads((HERE/'RETURN_RISK_SCALE_BUILD_FREEZE_V1.json').read_text())
    plan={'contrast':'one global unclipped same-state U versus gU; no grid',
          'cases':previous['cases'],'previous_scale_freeze_sha256':sha(HERE/'RETURN_RISK_SCALE_BUILD_FREEZE_V1.json'),
          'contract_sha256':sha(HERE/'RETURN_RISK_COSCALE_CONTRACT_V1.md'),
          'required_dyna_execution_freeze':'7871de549e198358f014fad60bcb5aeabf0f2a0cf5403009df6a0e501972406d',
          'require_dyna_complete_before_replay':True,'new_solvers':0,'teacher_labels':0}
    put(HERE/'RETURN_RISK_COSCALE_PLAN_V1.json',json.dumps(plan,indent=2)+'\n')
    names=['RETURN_RISK_COSCALE_CONTRACT_V1.md','RETURN_RISK_COSCALE_PLAN_V1.json','risk_coscale_metrics_v1.py',
           'prepare_risk_coscale_v1.py','audit_risk_coscale_v1.py','run_risk_coscale_v1.py']
    freeze={'status':'prepared only; must wait for dyna completion','files':{n:sha(HERE/n) for n in names},
            'original_auditor_sha256':sha(HERE/'audit_return_risk_scale_v1.py'),
            'previous_scale_results_sha256':sha(HERE/'RETURN_RISK_SCALE_RESULTS_V1.json'),
            'uncertainty_review_sha256':sha(HERE/'RETURN_RISK_UNCERTAINTY_REVIEW_V1.md')}
    put(HERE/'RETURN_RISK_COSCALE_BUILD_FREEZE_V1.json',json.dumps(freeze,indent=2)+'\n')
    print('prepared, not executed:',sha(HERE/'RETURN_RISK_COSCALE_BUILD_FREEZE_V1.json'))


if __name__=='__main__':main()
