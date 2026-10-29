"""Audit feature parity and strict actions independently of the timed engine."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent;D=ROOT.parent
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ids',required=True);ap.add_argument('--scope',choices=['valid','eval','members'],default='valid');ap.add_argument('--tag',required=True);a=ap.parse_args()
    variants={v['id']:v for v in json.loads((ROOT/'variants.json').read_text())};ids=list(map(int,a.ids.split(',')))
    if a.scope=='valid':rows=json.loads((D/'neural_20261027/valid_manifest.json').read_text());paths=[r['linux_file'] for r in rows]
    else:
        data=D/('member_eval_20261030/worktree/datasets' if a.scope=='members' else 'dataset_integration_20261029/worktree/datasets')
        paths=[str(p) for p in sorted(data.glob('*/eval/*.txt'))]
    f=ROOT/(a.tag+'_audit_paths.txt');f.write_text(''.join(p+'\n' for p in paths));results={}
    for i in ids:
        v=variants[i];src=(D/'neural_selector/teacher.cpp').read_text().replace('#include "reference_types.hpp"','#include "../neural_selector/reference_types.hpp"').replace('#include "../MySpillScheduler_neural.cpp"',f'#define PORTFOLIO_AUDIT\n#include "{v["source"]}"\n#undef PORTFOLIO_AUDIT')
        (ROOT/'teacher_audit.cpp').write_text(src)
        audit=(D/'neural_selector/audit.cpp').read_text().replace('#include "teacher.cpp"','#include "teacher_audit.cpp"');(ROOT/'audit.cpp').write_text(audit)
        p=subprocess.run(['g++','-std=c++14','-O2','-pedantic-errors',str(ROOT/'audit.cpp'),'-o',str(ROOT/'audit')],capture_output=True,text=True)
        if p.returncode:raise RuntimeError(p.stderr)
        out=ROOT/(a.tag+'_audit_'+str(i)+'.jsonl');subprocess.run([str(ROOT/'audit'),str(f),str(out),'-1'],check=True,timeout=600)
        result=[json.loads(s) for s in out.read_text().splitlines()];assert len(result)==len(paths)
        results[str(i)]=dict(name=v['name'],cases=len(result),source_sha256=v['sha256'],feature_prediction_parity=True,strict_actions=True)
        print('Audited',v['name'],len(result),flush=True)
    (ROOT/(a.tag+'_audit_summary.json')).write_text(json.dumps(results,indent=2));print(json.dumps(results),flush=True)
if __name__=='__main__':main()
