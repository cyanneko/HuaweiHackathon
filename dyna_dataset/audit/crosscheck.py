"""Small independent cross-check against the preexisting Python audit."""
import importlib.util,json,subprocess,tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('legacy_audit',ROOT/'hashjoin_lab/tools/audit_datasets.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

from test_audit import VALID

def main():
    cases=[VALID,VALID.replace('PROBE 1 1','PROBE 1 0')]
    body='INSERT 0 0 1\n'*9999+'SWITCH 0\nPROBE 0 1\nPROBE 0 1\n'
    cases.append('1 2 67108864 100 80 100\n10002 31\n0 9999 2\n'+body)
    results=[]
    for index,text in enumerate(cases):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            path=Path(d)/'case.txt';path.write_text(text)
            ref=old.audit_case(path,enforce_limits=True)
            p=subprocess.run([str(HERE/'audit'),str(path)],text=True,capture_output=True,check=True)
            actual=json.loads(p.stdout)
            for a,b in [('operations','operations'),('total_build_bytes','build_bytes'),('partition_bytes','partition_sizes'),('partition_probes','probe_counts')]:
                assert actual[a]==ref[b],(index,a,actual[a],ref[b])
            assert list(map(list,zip(actual['build_counts'],actual['probe_counts'])))==ref['per_operator_counts']
            results.append({'case':index,'agreement':True,'operations':ref['operations']})
    out={'status':'passed','cases':results,'scope':'independent small-case counts/bytes/phases/partition agreement; no generator imports'}
    (HERE/'crosscheck.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))

if __name__=='__main__':main()
