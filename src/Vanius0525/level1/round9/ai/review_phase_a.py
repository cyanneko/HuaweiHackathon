"""Final byte-for-byte trace review and seed-aware PhaseA descriptive summary."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,statistics
from itertools import zip_longest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
def mean(v):return statistics.mean(v) if v else None
def pct(a,b):return a/b if b else None
def trace(path):
    with path.open('rb') as f:
        for line in f:
            if line.startswith(b'TRACE '):yield line
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,value):
    s=json.dumps(value,indent=2)+'\n'
    if p.exists():assert p.read_text()==s
    else:p.write_text(s)
def main():
    result=json.loads((HERE/'PHASE_A_RESULTS_V1.json').read_text());assert result['complete'] and len(result['rows'])==24
    freeze=json.loads((HERE/'PHASE_A_BUILD_FREEZE_V1.json').read_text())
    for f,h in freeze['files'].items():assert sha(HERE/f)==h
    flows=[];callbacks=0;strata=[{'pressure':0,'eligible':0,'different':0,'chosen_dynamic':0} for _ in range(4)]
    for row in result['rows']:
        with experiment_lock():
            ref=ROOT/'build/round9/proxy100_baseline_v2'/row['reference_success_attempt']/'paired100_audit.stderr'
            obs=HERE/'build/phase_a_v1'/(Path(row['case']).stem+'.stderr');assert sha(ref)==row['reference_stderr_sha256'] and sha(obs)==row['observer_stderr_sha256']
            count=0
            for a,b in zip_longest(trace(ref),trace(obs)):
                assert a==b,(row['case'],count);count+=1
            assert count==row['trace']['callbacks'];callbacks+=count
            detail=row['observation_audit'];summary=detail['summary'];coverage=summary['coverage'];bins=summary['bins'];bits=coverage['source_bits']
            totals={k:sum(x[k] for x in bins) for k in ['pressure','eligible','different','chosen_dynamic']}
            for j,bin in enumerate(bins):
                for k in strata[j]:strata[j][k]+=bin[k]
            periodic=sum(bits[i] for i in range(8) if i&1);missnext=sum(bits[i] for i in range(8) if i&2);both=sum(bits[i] for i in range(8) if i&3==3)
            next_unique=periodic+missnext-both;assert next_unique+bits[4]==coverage['exact']
            samples=detail['samples'];distinct={s['q']:s for s in samples}
            order_only=sum(s['eligible'] and not s['different'] and s['history']!=s['dynamic'] for s in distinct.values())
            flow={'case':row['case'],'seed':row['seed'],'family':row['family'],**totals,
                  'different_per_pressure':pct(totals['different'],totals['pressure']),
                  'dynamic_per_pressure':pct(totals['chosen_dynamic'],totals['pressure']),
                  'dynamic_per_different':pct(totals['chosen_dynamic'],totals['different']),
                  'covered_probe_span':coverage['span'],'identified_executed':coverage['exact'],'anonymous_hit':coverage['anonymous'],
                  'identity_coverage':pct(coverage['exact'],coverage['span']),
                  'next_identity_coverage':pct(next_unique,coverage['span']),
                  'periodic_next_identity_coverage':pct(periodic,coverage['span']),
                  'miss_only_identifications':bits[4],'next_unique_identifications':next_unique,
                  'periodic_next_identifications':periodic,'miss_next_identifications':missnext,'next_source_overlap':both,
                  'known_hits_removed_from_anonymous':coverage['known_hit'],
                  'known_hits_after_periodic_prefetch':coverage['periodic_prefetch_hit'],
                  'first_callback_probe':coverage['start_q'],'last_callback_probe':coverage['last_q'],
                  'unobserved_tail_probes':detail['unobserved_tail_probes'],
                  'samples_with_pool_membership_different':sum(s['different'] for s in distinct.values()),
                  'sample_records':len(samples),'unique_sample_states':len(distinct),'sample_order_only_differences':order_only,
                  'full_different_margin_min':min((b['margin_min'] for b in bins if b['different']),default=None),
                  'full_different_margin_max':max((b['margin_max'] for b in bins if b['different']),default=None)}
            flows.append(flow)
    sums={k:sum(f[k] for f in flows) for k in ['pressure','eligible','different','chosen_dynamic','covered_probe_span','identified_executed','anonymous_hit','miss_only_identifications','next_unique_identifications','periodic_next_identifications','miss_next_identifications','next_source_overlap','known_hits_removed_from_anonymous','known_hits_after_periodic_prefetch','sample_records','unique_sample_states','unobserved_tail_probes']}
    rates=['different_per_pressure','dynamic_per_pressure','dynamic_per_different','identity_coverage','next_identity_coverage','periodic_next_identity_coverage']
    family={fam:{'seeds':sum(f['family']==fam for f in flows),**{metric:mean([f[metric] for f in flows if f['family']==fam and f[metric] is not None]) for metric in rates}} for fam in sorted({f['family'] for f in flows})}
    report={'scope':'24 independent100-only train seeds; current action/observation space, not future rewards or learning opportunity proof',
        'byte_for_byte_trace_callbacks':callbacks,'all24_byte_for_byte_trace_match':True,'all24_independent_byte_and_identity_audits_pass':True,
        'totals':sums,'equal_seed_rates':{metric:mean([f[metric] for f in flows if f[metric] is not None]) for metric in rates},
        'event_weighted_rates':{'different_per_pressure':pct(sums['different'],sums['pressure']),'dynamic_per_pressure':pct(sums['chosen_dynamic'],sums['pressure']),
              'dynamic_per_different':pct(sums['chosen_dynamic'],sums['different']),'identity_coverage':pct(sums['identified_executed'],sums['covered_probe_span']),
              'next_identity_coverage':pct(sums['next_unique_identifications'],sums['covered_probe_span'])},
        'families':family,'q_strata':strata,'seed_rows':flows,'seeds_with_different_pools':sum(f['different']>0 for f in flows),
        'seeds_with_dynamic_selection':sum(f['chosen_dynamic']>0 for f in flows),'new_observer_runs':24,'new_reference_runs':0,'em_runs':0,'teacher_runs':0,'training_runs':0,'dev_eval_accesses':0,
        'interpretation_limits':['pool endpoints differ does not prove different estimator decisions or learnable benefit','identity coverage includes policy-selected Miss-only and is not IID sampling probability','per-operator exact IDs are not per-operator true traffic or hit rate','observation timing includes instrumentation and is not deployed inference timing']}
    save(HERE/'PHASE_A_SUMMARY_V1.json',report)
    print(json.dumps({k:report[k] for k in ['totals','equal_seed_rates','families','q_strata','seeds_with_different_pools','seeds_with_dynamic_selection','byte_for_byte_trace_callbacks']},indent=2))
if __name__=='__main__':main()
