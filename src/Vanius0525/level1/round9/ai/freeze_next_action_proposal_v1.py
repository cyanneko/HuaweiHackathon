"""Select pre-existing bottom-k states without future rewards or new inputs."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    with experiment_lock():
        result=json.loads((HERE/'PHASE_A_RESULTS_V1.json').read_text())
        summary=json.loads((HERE/'PHASE_A_SUMMARY_V1.json').read_text())
        proposal=json.loads((HERE/'PRESSURE_PILOT_PROPOSAL_V1.json').read_text())
        seeds={x['case']:x for x in summary['seed_rows']};metadata={x['path']:x for x in proposal['cases']}
        states=[]
        for row in result['rows']:
            detail=row['observation_audit'];c=seeds[row['case']]
            total=c['last_callback_probe']+c['unobserved_tail_probes']
            for j in range(4):
                candidates=[s for s in detail['samples'] if s['kind']=='different' and s['stratum']==j]
                if not candidates:continue
                s=min(candidates,key=lambda x:(x['key'],x['q']))
                same=set(map(tuple,s['history']))==set(map(tuple,s['dynamic']))
                states.append({'id':len(states),'case':row['case'],'seed':row['seed'],'family':row['family'],
                    'fold':metadata[row['case']]['metadata_only_fold_proposal'],'stratum':j,'q':s['q'],
                    'raw_operation_index_zero_based':detail['sample_raw_operation_indices'][str(s['q'])],
                    'sampling_key':s['key'],'phase_a_callback_index':s['callback_index'],
                    'member_sets_different':not same,'order_only_difference':same and s['history']!=s['dynamic'],
                    'remaining_probes_including_current':total-s['q']+1,
                    'complete_8192':total-s['q']+1>=8192,
                    'stratum_pressure_population':detail['summary']['bins'][j]['pressure'],
                    'stratum_different_population':detail['summary']['bins'][j]['different'],
                    'phase_a_original_dynamic_choice':s['chosen_dynamic'],
                    'history':s['history'],'dynamic':s['dynamic']})
        assert len(states)==70 and sum(x['complete_8192'] for x in states)==65
        full=[x['id'] for x in states if x['complete_8192']]
        report={'scope':'authorized two-teacher finite opportunity only; no EM/training/dev/eval',
                'plan_sha256':sha(HERE/'NEXT_ACTION_OPPORTUNITY_PLAN_V1.md'),
                'phase_a_final_freeze_sha256':sha(HERE/'PHASE_A_FINAL_FREEZE_V1.json'),
                'phase_a_results_sha256':sha(HERE/'PHASE_A_RESULTS_V1.json'),
                'seed_proposal_sha256':sha(HERE/'PRESSURE_PILOT_PROPOSAL_V1.json'),
                'selection_program_sha256':sha(Path(__file__)),
                'seeds':24,'nonzero_state_seeds':len({s['seed'] for s in states}),
                'states':states,'audit_first_two_state_ids':full[:2],
                'maximum_collector_prefixes':23,'maximum_branches':260,
                'endpoints_probes_including_current':[4096,8192],
                'continuations':['paired100','fixed_dynamic100'],
                'terminal_censored_state_ids':[x['id'] for x in states if not x['complete_8192']],
                'all_states_member_sets_different':all(x['member_sets_different'] for x in states)}
        text=json.dumps(report,indent=2)+'\n';path=HERE/'NEXT_ACTION_OPPORTUNITY_PROPOSAL_V1.json'
        if path.exists():assert path.read_text()==text
        else:path.write_text(text)
        print('Frozen proposal',sha(path),'states',len(states),'full',len(full),'audit first',full[:2])
if __name__=='__main__':main()
