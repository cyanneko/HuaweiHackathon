"""Exact small-state evidence for an unobserved reward-parameter boundary.
This is a constructed diagnostic, never included in member means or online features.
"""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO
from workflow import experiment_lock
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case
out=ROOT/'build/round4/penalty_information';out.mkdir(parents=True,exist_ok=True)
# Keep the original frozen oracle bytes. Only restrict the first mandatory overflow's destination.
original=(ROOT/'oracle.py').read_text();text=original.replace('def optimal(path):','def optimal(path, first_mask=None):')
needle='''                        if sub&bit and sub&zero==zero and sums[sub]+z<=m:'''
assert needle in text
text=text.replace(needle,'''                        if first_mask is not None and counter==64 and sub!=first_mask:
                            pass
                        elif sub&bit and sub&zero==zero and sums[sub]+z<=m:''')
source=out/'conditioned_oracle.py';source.write_text(text);namespace={'__name__':'conditioned_oracle'};exec(compile(text,str(source),'exec'),namespace)
optimal=namespace['optimal'];rows=[]
with experiment_lock():
    ops=['INSERT 0 0 1048576']*63+['INSERT 0 1 1048576','INSERT 0 2 1048576','SWITCH 0']+[f'PROBE 0 {1+j%2}' for j in range(16)]+['PROBE 0 0']
    for penalty in [1,1000]:
        data=('\n'.join([f'1 3 67108864 10000 10000 {penalty}',f'{len(ops)} 10000','0 65 17']+ops)+'\n').encode();p=out/f'paired_penalty_{penalty}.txt'
        if p.exists():assert p.read_bytes()==data
        else:p.write_bytes(data)
        audit=audit_case(p);conditional={name:optimal(p,mask)['optimal_io_plus_miss'] for name,mask in [('spill_large',6),('spill_small',5),('spill_both',4)]}
        full=optimal(p)['optimal_io_plus_miss'];assert abs(full-min(conditional.values()))<1e-6
        rows.append({'penalty':penalty,'input_sha256':audit['sha256'],'operation_sha256':audit['operation_stream_sha256'],'optimal_io_plus_miss':full,'conditional_first_action_cost':conditional,'regret':{n:v-full for n,v in conditional.items()}})
    assert rows[0]['operation_sha256']==rows[1]['operation_sha256']
    assert min(rows[0]['conditional_first_action_cost'],key=rows[0]['conditional_first_action_cost'].get)!=min(rows[1]['conditional_first_action_cost'],key=rows[1]['conditional_first_action_cost'].get)
    # Both-spill is dominated by spilling the large object alone on these two traces.
    assert all(r['conditional_first_action_cost']['spill_both']>=r['conditional_first_action_cost']['spill_large'] for r in rows)
    low=rows[0]['regret']['spill_large'];high=rows[1]['regret']['spill_small'];prob=high/(low+high)
    result={'instances':rows,'first_callback_visible_state':{'memory_limit':67108864,'memory_used':67108864,'k':1,'p':3,'write_bandwidth':10000,'read_bandwidth':10000,'hit_count':0,'miss_count':0,'total_io_bytes':0,'operator_phase':'BUILD','partition_bytes':[63*(1<<20),1<<20,0],'resident':[True,True,True],'callback':'overflow(op0,pid2,tuple1MiB)','next_op':'SWITCH op0','prior_callbacks':0},'first_actions':'Only spill large A, small B, or both can free the required 1MiB; LOAD during BUILD is illegal.','deterministic_minimax_regret_lower_bound_us':min(low,high),'randomized_two_action_minimax_lower_bound_us':low*high/(low+high),'randomized_probability_spill_large':prob,'scope':'Conditional exact offline minima give a lower bound for any legal callback-only policy. The penalty is absent from SystemState and all other input bytes/visible past and future are identical; cannot be inferred from later state either. Does not imply any tested policy attains this lower bound or that the phenomenon is a novel research result.','oracle_original_sha256':hashlib.sha256(original.encode()).hexdigest(),'conditioned_oracle_sha256':hashlib.sha256(text.encode()).hexdigest()}
    (ROOT/'round4/PENALTY_INFORMATION_BOUNDARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
