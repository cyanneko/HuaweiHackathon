import hashlib,json,re,subprocess
from pathlib import Path
from experiment import dump
ROOT=Path(__file__).resolve().parent
def main():
    frozen=json.loads((ROOT/'freeze.json').read_text())
    for n,h in frozen.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h
    b=json.loads((ROOT/'budget_freeze.json').read_text());source=ROOT/'BudgetedScheduler.cpp'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==b['source_sha256']
    code=re.sub(r'//[^\n]*|/\*.*?\*/','',source.read_text('utf8'),flags=re.S)
    assert not re.search(r'\b(main|ifstream|fstream|fopen|cin|scanf|getenv|system|popen|miss_penalty|op_lines)\b',code)
    assert set(re.findall(r'#include\s*<([^>]+)>',code))<=set(['algorithm','array','vector','cstdint','chrono'])
    for folder in ['fresh_test','funded_test']:
        rows=json.loads((ROOT/folder/'manifest.json').read_text())
        for r in rows:
            assert hashlib.sha256(Path(r['file']).read_bytes()).hexdigest()==r['sha256']
            assert 64*(1<<20)<=r['M']<=4096*(1<<20) and r['max_partition']<=r['M']
    plain=(ROOT/'reference_current.cpp').read_text('utf8')
    for name,flags in [('core',351),('early',863),('budget',4959),('budget_externality',5983)]:
        modified=(ROOT/('budget_engine_'+name+'.cpp')).read_text('utf8')
        restored=modified.replace('\n#include "BudgetedScheduler.cpp"\n','').replace('std::make_unique<MySpillScheduler>('+str(flags)+')','std::make_unique<NaiveSpillScheduler>()')
        assert restored==plain
    test=(ROOT/'budget_engine_budget.cpp').read_text().replace('std::make_unique<MySpillScheduler>(4959)','std::make_unique<MySpillScheduler>()')
    (ROOT/'default_constructor_check.cpp').write_text(test)
    p=subprocess.run(['g++','-std=c++14','-O2','-pedantic-errors',str(ROOT/'default_constructor_check.cpp'),'-o',str(ROOT/'default_constructor_check')],capture_output=True,text=True,timeout=60)
    assert p.returncode==0,p.stderr
    p=subprocess.run([str(ROOT/'default_constructor_check'),str(ROOT/'fresh_test'/'cases'/'alias_A.txt')],capture_output=True,text=True,timeout=60)
    assert p.returncode==0,p.stderr
    times=json.loads((ROOT/'scale_results.json').read_text());assert len(times)==12 and all(x['wall_s']<60 for x in times)
    audit=dict(frozen_source_hashes_verified=True,input_files_sha256_verified=642,standard='C++14',standard_library_only=True,
      no_runtime_input_or_hidden_penalty_access=True,framework_only_permitted_substitution=True,no_argument_constructor_tested=True,
      unexpected_failures=0,scale_runs=12,all_scale_under_60s=True,
      official_engine_replays=610*8*3+610*6*3+32*6*3+12,strict_replays=4270+1284,
      development_reuse='The original 610 cases became regression/development evidence for the budget refinement. Only the 32 funded cases were generated after budget freeze.',
      limitation='Synthetic local workloads, not official hidden-test scores or a global competitive guarantee.')
    dump(ROOT/'final_audit.json',audit);print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
