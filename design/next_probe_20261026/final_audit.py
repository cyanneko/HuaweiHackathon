import collections,hashlib,json,re,statistics,subprocess
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
def main():
    freeze=json.loads((ROOT/'refined_freeze.json').read_text())['sources']
    for n,h in freeze.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h
    for n in ['MySpillScheduler_gated.cpp','SafeBase.cpp','MySpillScheduler.cpp']:
        code=re.sub(r'//[^\n]*|/\*.*?\*/','',(ROOT/n).read_text(),flags=re.S)
        assert not re.search(r'\b(main|ifstream|fstream|fopen|cin|scanf|system|popen|getenv|miss_penalty|op_lines)\b',code)
        assert set(re.findall(r'#include\s*<([^>]+)>',code))<=set(['algorithm','array','vector','cstdint'])
    ref=(ROOT/'reference_current.cpp').read_text('utf8')
    for name,include in [('refined','MySpillScheduler_gated.cpp'),('safe_base','SafeBase.cpp'),('base','BaseScheduler.cpp'),('candidate','MySpillScheduler.cpp')]:
        s=(ROOT/('engine_'+name+'.cpp')).read_text('utf8').replace('\n#include "'+include+'"\n','').replace('std::make_unique<MySpillScheduler>()','std::make_unique<NaiveSpillScheduler>()')
        assert s==ref
    for folder,count in [('validation',576),('refined_validation',300)]:
        rows=json.loads((ROOT/folder/'manifest.json').read_text());assert len(rows)==count
        for x in rows:
            assert hashlib.sha256(Path(e.linux(x['file'])).read_bytes()).hexdigest()==x['sha256']
            assert 64*(1<<20)<=x['M']<=4096*(1<<20) and x['max_partition']<=x['M']
    audits={}
    for label,count in [('development',336),('validation',576),('anchor',16),('refined',300),('previous576',576)]:
        rows=[json.loads(x) for x in (ROOT/(label+'_strict.jsonl')).read_text().splitlines()]
        assert all(x['ok'] for x in rows)
        audits[label]=dict(replays=len(rows),all_legal=True)
    mixed=json.loads((ROOT/'mixed_callback_counts.json').read_text());assert all(x['ok'] for x in mixed)
    # Equal-work ablation: three interleaved repetitions of slow and fast joint
    # planners plus the prior policy. It follows all other timed work serially.
    row=next(x for x in json.loads((ROOT/'scale_manifest.json').read_text()) if x['id']=='maxN_mixed_maxQ')
    runs=[]
    for rep in range(3):
        for name in (['base','slow_selected','candidate'] if rep%2==0 else ['candidate','slow_selected','base']):
            x=e.run_case(row,name);x['repeat']=rep;runs.append(x);print('Sort ablation',rep+1,name,flush=True)
    e.dump(ROOT/'sort_ablation_runs.json',runs)
    group=collections.defaultdict(list)
    for x in runs:group[x['profile']].append(x)
    assert len({(x['Total_IO_Time'],x['Hit_Count'],x['Miss_Count']) for x in group['slow_selected']+group['candidate']})==1
    e.dump(ROOT/'sort_ablation_summary.json',{n:{k:statistics.median(x[k] for x in xs) for k in ['Total_IO_Time','Total_Decision_Time','Miss_Count','Hit_Count','Total_Score','wall_s']} for n,xs in group.items()})
    scales=[json.loads(x) for x in (ROOT/'refined_scale_runs.jsonl').read_text().splitlines()]
    assert len(scales)==54 and all(x['wall_s']<60 for x in scales+runs)
    assert (ROOT.parent/'MySpillScheduler_adaptive.cpp').read_bytes()==(ROOT/'MySpillScheduler_gated.cpp').read_bytes()
    assert (ROOT.parent/'MySpillScheduler_prefix2.cpp').read_bytes()==(ROOT/'SafeBase.cpp').read_bytes()
    report=dict(standard='C++14',compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
      frozen_sources_verified=True,standard_library_only=True,framework_only_permitted_substitution=True,
      no_argument_constructors_compiled=True,no_input_or_hidden_penalty_access=True,
      stage1_fresh_cases=576,stage2_fresh_cases=300,independent_repetitions=3,
      stage1_engine_runs=576*5*3,stage2_engine_runs=300*5*3,strict_audits=audits,
      all_actions_legal=True,exact_prefix2_action_io_equivalence=True,
      final_scale_runs=54,sort_ablation_runs=9,all_wall_times_under_60s=True,
      mixed_callback_counts=mixed,source_sha256=freeze,
      validation_note='The first 576 inputs became development evidence for the restricted admission. Only the later 300 were drawn after the restricted policy was frozen.',
      limitation='Local generated workloads and timings, not official hidden tests or a universal Score improvement proof.')
    e.dump(ROOT/'final_audit.json',report);print('Final source/input/interface/audit checks passed.',flush=True)
if __name__=='__main__':main()
