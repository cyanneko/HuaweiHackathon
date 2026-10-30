"""Text-only scope adapter for the already audited R81 ablation runner."""
from pathlib import Path
import ast,hashlib,json
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'r81_ablation_20261031'
def prepare():
    original=(BASE/'runner.py').read_text(encoding='utf-8');text=original
    text=text.replace('Frozen nine-method ablation wrapper','Frozen isolated three-method BUILD wrapper')
    replacements=[("CAPS={'dyna':1000,'final':500,'stat':450};COUNTS={'dyna':12,'final':72,'stat':10}","CAPS={'dyna':500,'stat':200};COUNTS={'dyna':12,'stat':10}"),
      ("for mode in ['dyna','final']:","for mode in ['dyna']:"),
      ("['dyna','final','stat']","['dyna','stat']"),
      ('2200','900'),('846','66'),('188','44'),
      ('EFFECTIVENESS_PASS 9','TINY_BUILD_PASS cases=10'),
      ("'Frozen final R81 single-mechanism ablation; observed local synthetic '","'One frozen BUILD candidate; observed local synthetic '"),
      ("order='lexicographic cases; rotate fixed9 left case_index modulo9'","order='lexicographic cases; rotate fixed3 left case_index modulo3'"),
      ("tests='12 Python checks PASS; tiny native effectiveness checks deferred until GO'","tests='Small Python protocol checks PASS; candidate tiny tests deferred until GO'"),
      ("methods=9,cases=94,planned_cells=66","methods=3,cases=22,planned_cells=66")]
    for before,after in replacements:
        assert before in text,before;text=text.replace(before,after)
    # Tiny sources come from the candidate author, not the unrelated ablations.
    text=text.replace("HERE/'effectiveness.generated.hpp'","HERE/'candidate.binding.json'")
    text=text.replace("HERE/'effectiveness.cpp',HERE/'candidate.binding.json'","HERE/'effectiveness.cpp',HERE/'candidate.binding.json',HERE/'tiny.generated.hpp',HERE/'adapter_manifest.json'")
    text=text.replace("[sys.executable,'-m','unittest','test_sources','test_protocol']","[sys.executable,'-m','unittest','test_protocol']")
    text=text.replace("dict(status='PASS',tests=9,test_binary_sha256", "dict(status='PASS',tests=10,test_binary_sha256")
    text=text.replace('r81_ablation_','r81_build_')
    insert="""        # Fixed parent RED control and candidate GREEN, both inside900s.
        redbinary=HERE/'effectiveness_parent_red'
        red=helper.checked_run(['g++','-std=c++14','-O2','-DEXPECT_PARENT_RED',str(HERE/'effectiveness.cpp'),'-o',str(redbinary)],HERE/'effectiveness_red_compile',min(60.,left()),cwd=HERE)
        assert red['status']=='EXITED' and red['returncode']==0,'parent RED compile'
        red=helper.checked_run([str(redbinary)],HERE/'effectiveness_red_run',min(10.,left()),cwd=HERE)
        assert red['status']=='EXITED' and red['returncode']==3 and (HERE/'effectiveness_red_run/stderr.txt').read_text()=='TINY_FAIL: minimum_single_victim_beyond_parent_top4\\n','parent RED did not detect mechanism'
"""
    anchor="        binary=HERE/'effectiveness';p=helper.checked_run"
    assert text.count(anchor)==1;text=text.replace(anchor,insert+anchor,1)
    # Both frozen candidate artifacts and the adapter are part of closure.
    text=text.replace("for fp in HERE.glob('*.py'):deps[rel(fp)]=sha(fp)","for fp in HERE.glob('*.py'):deps[rel(fp)]=sha(fp)\n    binding=read(HERE/'candidate.binding.json')\n    for p,h in binding['dependencies'].items():assert sha(path(p))==h;deps[p]=h")
    tree=ast.parse(text);export=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export')
    replacement=(HERE/'export.inc.py').read_text(encoding='utf-8')
    text=text.replace(ast.get_source_segment(text,export),replacement)
    (HERE/'runner.py').write_text(text,encoding='utf-8')
    info=dict(base_runner_sha256=hashlib.sha256(original.encode()).hexdigest(),adapted_runner_sha256=hashlib.sha256(text.encode()).hexdigest(),exact_scope='3methods dyna12 stat10 66cells global900s',native_runs=0,compile_runs=0)
    (HERE/'adapter_manifest.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':prepare()
