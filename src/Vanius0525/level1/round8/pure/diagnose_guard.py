"""Four frozen train diagnostics; instrument counters only, require identical TRACE."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from build import build
from round6.prepare import DATA,manifest,put
from round7.cost_replay import replay
from workflow import experiment_lock

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def diagnostic_text(text):
    text=text.replace('#include <cmath>','#include <cmath>\n#include <iostream>\n#include <iomanip>')
    text=text.replace('    // Only these two already-established planners are compared.', '''    double diag_max_periodic_z_=-1e300,diag_min_pn_=1e300,diag_max_pn_=0;
    int64_t diag_periodic_positive_=0,diag_no_periodic_=0;
    // Only these two already-established planners are compared.''')
    needle='            if(immediate+64.0*pmean-2.0*psd>0){++paired_source_veto_;return;}'
    replacement='''            const double dmean=immediate+64.0*pmean;
            const double z=psd>0?dmean/psd:(dmean>0?1e100:(dmean<0?-1e100:0));
            diag_max_periodic_z_=std::max(diag_max_periodic_z_,z);
            diag_min_pn_=std::min(diag_min_pn_,pn);diag_max_pn_=std::max(diag_max_pn_,pn);
            if(dmean>0)++diag_periodic_positive_;
            if(pn<1)++diag_no_periodic_;
'''+needle
    assert text.count(needle)==1;text=text.replace(needle,replacement)
    marker='public:\n    std::vector<Action> onMemoryOverflow'
    new='''public:
    ~MySpillScheduler() override {
        std::cerr<<std::setprecision(17)<<"DIAG "<<paired_checks_<<" "<<paired_different_<<" "<<paired_confident_<<" "<<paired_source_veto_<<" "<<paired_chosen_
          <<" "<<diag_periodic_positive_<<" "<<diag_no_periodic_<<" "<<diag_max_periodic_z_<<" "<<diag_min_pn_<<" "<<diag_max_pn_<<" "<<periodic_total_<<"\\n";
    }
    std::vector<Action> onMemoryOverflow'''
    assert marker in text;return text.replace(marker,new)

def main():
    frozen=FOLDER/'paired_source_guard.cpp';assert sha(frozen)==json.loads((FOLDER/'CANDIDATES.json').read_text())['sources']['paired_source_guard']
    rows=json.loads((FOLDER/'PAIRED_SOURCE_GUARD_RESULTS.json').read_text())['rows'];index={r['file']:r for r in rows}
    names=['train_048_liunianwww_hot_large.txt','train_116_Vanius0525_markov.txt']
    for family in ['random_lognormal','random_zipf']:names.append(next(r['file'] for r in rows if r['family']==family))
    case_index={Path(x['path']).name:x for x in manifest()['cases']}
    folder=ROOT/'build/round8_pure_diagnostic';folder.mkdir(parents=True,exist_ok=True)
    source=folder/'source_guard_diagnostic.cpp';put(source,diagnostic_text(frozen.read_text()).encode())
    plan={'frozen_source_sha256':sha(frozen),'diagnostic_source_sha256':sha(source),'cases':[{'file':n,'sha256':index[n]['input_sha256']} for n in names],'selection':'Before diagnostics: worst old-train hot-large, existing Markov risk, first lognormal and first Zipf in frozen80 order; no dev/eval.','test_queries':0,'dev_queries':0}
    put(FOLDER/'DIAGNOSTIC_PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
    with experiment_lock():
        original=build(frozen,'round8_pure_guard_original',audit=True)
        diagnostic=build(source,'round8_pure_guard_diag',audit=True)
    result=[]
    for name in names:
        path=DATA/case_index[name]['path'];assert case_index[name]['split']=='train' and sha(path)==index[name]['input_sha256']
        cache=folder/(path.stem+'.json')
        if cache.exists():item=json.loads(cache.read_text())
        else:
            with experiment_lock():
                a=subprocess.run([str(original),str(path)],capture_output=True,text=True,check=True,timeout=120)
                b=subprocess.run([str(diagnostic),str(path)],capture_output=True,text=True,check=True,timeout=120)
            trace=lambda p:'\n'.join(x for x in p.stderr.splitlines() if x.startswith('TRACE '))
            assert trace(a)==trace(b)
            aa=replay(path,a.stderr,a.stdout);ab=replay(path,b.stderr,b.stdout);assert aa==ab==index[name]['audit']
            line=next(x for x in b.stderr.splitlines() if x.startswith('DIAG '));values=line.split()[1:]
            keys=['checks','different','confident','source_veto','chosen','periodic_mean_opposes','periodic_effective_n_lt1','max_periodic_z_on_confident','min_periodic_effective_n_on_confident','max_periodic_effective_n_on_confident','terminal_periodic_mass']
            item={'file':name,'input_sha256':sha(path),'same_trace':True,'trace_sha256':hashlib.sha256(trace(a).encode()).hexdigest(),'audit_equal_old_cache':True,'diagnostics':{k:(int(v) if j<7 else float(v)) for j,(k,v) in enumerate(zip(keys,values))}}
            put(cache,(json.dumps(item,indent=2)+'\n').encode())
        result.append(item);print(json.dumps(item),flush=True)
    put(FOLDER/'GUARD_DIAGNOSTICS.json',(json.dumps({'complete':True,'cases':result,'new_solver_runs':8,'source_unchanged':sha(frozen)==plan['frozen_source_sha256'],'test_queries':0,'dev_queries':0},indent=2)+'\n').encode())
if __name__=='__main__':main()
