"""Small case studies: mechanism ablations, exposed examples, audit every action."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
cases=json.loads((ROOT/'round4/CASE_STUDIES.json').read_text())
folder=ROOT/'build/round4/case_inputs';folder.mkdir(parents=True,exist_ok=True)
for rec in cases:
    found=[]
    for parent in [ROOT/'build/data/holdout',ROOT/'build/data/round3-fresh',ROOT/'build/team_snapshot_923d21e/liunianwww/eval']:
        path=parent/rec['file']
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==rec['input_sha256']:found.append(path)
    assert found;target=folder/rec['file']
    if not target.exists():target.symlink_to(found[0].resolve())
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
for name in ['pure_prune','pure_set1','ai_prune','ai_set0','ai_set025']:
    sources[name]=ROOT/'round4'/(name+'.cpp')
base=(ROOT/'MySpillScheduler.cpp').read_text()
for label,source in [
 ('pure_no_prefetch',base[:base.index('    std::vector<Action> onPeriodicAdjust')]+'''    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if(active_)update(s);return {};
    }
};
'''),
 ('pure_no_scan',base.replace('streak_ >= 6 && stride_ > 0 &&','false && streak_ >= 6 && stride_ > 0 &&')),
 ('pure_no_history',base.replace('if (evidence && h.last >= 0)', 'if (false && evidence && h.last >= 0)').replace('if (evidence && scan &&', 'if (false && evidence && scan &&'))]:
    path=ROOT/'round4'/(label+'.cpp');path.write_text(source);sources[label]=path
with experiment_lock():benchmark(folder,sources,5,True,ROOT/'results/round4-case-ablations.json')
