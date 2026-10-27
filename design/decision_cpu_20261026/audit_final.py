import collections,hashlib,json,re,statistics,subprocess
from pathlib import Path
from experiment import dump,linux
ROOT=Path(__file__).resolve().parent
freeze=json.loads((ROOT/'freeze.json').read_text())
source=ROOT/'MySpillScheduler.cpp'
assert hashlib.sha256(source.read_bytes()).hexdigest()==freeze['source_sha256']
assert (ROOT.parent/'MySpillScheduler_cpu.cpp').read_bytes()==source.read_bytes()
code=re.sub(r'//[^\n]*|/\*.*?\*/','',source.read_text('utf8'),flags=re.S)
assert not re.search(r'\b(main|ifstream|fstream|fopen|scanf|cin|getenv|popen|system|miss_penalty|op_lines)\b',code)
assert set(re.findall(r'#include\s*<([^>]+)>',code))<=set(['algorithm','array','cstdint','vector'])
plain=(ROOT/'reference_current.cpp').read_text('utf8')
for name,include in [('previous','PreviousScheduler.cpp'),('optimized','MySpillScheduler.cpp')]:
    e=(ROOT/('engine_'+name+'.cpp')).read_text('utf8')
    assert e.replace('\n#include "'+include+'"\n','').replace('std::make_unique<MySpillScheduler>()','std::make_unique<NaiveSpillScheduler>()')==plain
rows=json.loads((ROOT/'validation'/'manifest.json').read_text())
for r in rows:
    p=Path(linux(r['file']));assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
    assert 64*(1<<20)<=r['M']<=4096*(1<<20) and r['max_partition']<=r['M']
strict=[]
for label,n in [('development',610),('validation',336)]:
    xs=[json.loads(x) for x in (ROOT/(label+'_final_strict.jsonl')).read_text().splitlines()]
    assert len(xs)==2*n and all(x['ok'] for x in xs);strict.extend(xs)
large=[json.loads(x) for x in (ROOT/'scale_cpu_runs.jsonl').read_text().splitlines()]
assert len(large)==60 and all(x['wall_s']<60 for x in large)
g=collections.defaultdict(list)
for x in large:g[x['case'],x['profile']].append(x)
for ident in {x['case'] for x in large}:
    a,b=g[ident,'previous'],g[ident,'optimized']
    assert len(a)==len(b)==5
    assert len({(x['Total_IO_Time'],x['Miss_Count'],x['Hit_Count']) for x in a+b})==1
grouped={}
for ident in {x['case'] for x in large}:
    a,b=g[ident,'previous'],g[ident,'optimized']
    grouped[ident]=dict(previous_decision_us=statistics.median(x['Total_Decision_Time'] for x in a),
      optimized_decision_us=statistics.median(x['Total_Decision_Time'] for x in b),
      previous_score=statistics.median(x['Total_Score'] for x in a),optimized_score=statistics.median(x['Total_Score'] for x in b),
      optimized_decision_minmax=[min(x['Total_Decision_Time'] for x in b),max(x['Total_Decision_Time'] for x in b)])
v=json.loads((ROOT/'validation_summary.json').read_text())['summary']
report=dict(standard='C++14',compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
 frozen_sources_verified=True,framework_only_permitted_substitution=True,standard_library_only=True,
 no_runtime_input_or_hidden_parameters=True,no_argument_constructor_compiled=True,validation_cases=336,
 validation_repetitions=3,validation_engine_runs=336*3*3,strict_replays=len(strict),all_actions_legal=True,
 same_actions_reads_writes_hit_miss=True,cpu_scale_runs=60,scale_repetitions=5,all_scale_under_60s=True,
 source_sha256=freeze['source_sha256'],previous_sha256=freeze['previous_sha256'],
 validation_decision_reduction=1-v['optimized']['sum_decision_us']/v['previous']['sum_decision_us'],
 validation_geometric_score_ratios={k:v[k]['geometric_ratio'] for k in ['previous','optimized']},cpu_scale=grouped,
 default_replacement=False,conclusion='Small cumulative CPU improvement; no stable universal Score improvement. Keep as an optional action-preserving candidate, not a new default.',
 limitation='Local generated data and CPU timings. No official hidden-test score or universal speedup guarantee.')
dump(ROOT/'final_audit.json',report);print(json.dumps(report,indent=2))
