"""Fixed mixed-extremes inputs only; no solver/model/score input (Python stdlib)."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parent
AUDITOR=ROOT.parents[1]/'evaluation/scripts/audit_datasets.py'
sys.path.insert(0,str(AUDITOR.parent))
from audit_datasets import audit_case

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

class ProbeSchedule:
    """Logical pid schedule; independent hot/cold event ordinals never reset."""
    def __init__(self,case):
        self.case=case;self.parameters=case['parameters'];self.global_index=0
        self.local_counts=[0]*case['K'];self.hot_counts=[0]*case['K'];self.cold_counts=[0]*case['K']
        self.filler_counts=[0]*case['K'];self.next_anchor=0;self.anchor_index=0
    def next(self,forced_op=None):
        c=self.case;p=self.parameters;g=self.global_index;family=c['family'];rates=c['main_operator_rate_cycle']
        op=rates[g%len(rates)] if forced_op is None else forced_op
        if family=='reuse_cross64':
            if g==self.next_anchor:
                op=p['anchor_operator'];pid=p['anchor_logical_pid']
                gaps=p['global_probe_interarrival_cycle'];self.next_anchor+=gaps[self.anchor_index%len(gaps)];self.anchor_index+=1
            else:
                pid=1+self.filler_counts[op]%(c['P']-1);self.filler_counts[op]+=1
        elif family=='memory_one_partition_boundary':
            phase=g//p['global_phase_length']%2
            extra=(phase==0)==p['first_phase_includes_extra']
            slots=p['active_interleaved_slots']+([p['extra_slot']] if extra else [])
            op,pid=slots[g%len(slots)]
        elif family=='next_bait_anticorrelation':
            ordinal=g%p['global_block_length'];order=p['bait_operator_order']
            if ordinal<len(order):op=order[ordinal];pid=p['bait_logical_pid']
            else:
                hot=p['hot_logical_ids'];pid=hot[self.hot_counts[op]%len(hot)];self.hot_counts[op]+=1
        else:
            if family in ('hotset_phase_reverse','size_reuse_correlation_reverse'):
                phase=(g+p['phase_offset_per_operator'][op])//p['global_phase_length']%2
                if p['reverse_A_B_start']:phase=1-phase
                hot=p['hot_A'] if phase==0 else p['hot_B']
            else:hot=p['hot_logical_ids']
            if self.local_counts[op]%p['period']<p['hot_hits_per_period']:
                pid=hot[self.hot_counts[op]%len(hot)];self.hot_counts[op]+=1
            else:
                cold=[i for i in range(c['P']) if i not in hot]
                pid=cold[self.cold_counts[op]%len(cold)];self.cold_counts[op]+=1
        self.local_counts[op]+=1;self.global_index+=1
        return op,pid

def construct(case,deadline):
    k,p=case['K'],case['P'];rng=random.Random(case['seed']);permutations=[]
    physical=[[0]*p for _ in range(k)]
    for op in range(k):
        order=list(range(p));rng.shuffle(order);permutations.append(order)
        for logical,pid in enumerate(order):physical[op][pid]=case['logical_partition_bytes'][op][logical]
    schedule=ProbeSchedule(case);operations=[];counts=[[0,0] for _ in range(k)];logical_counts=[[0]*p for _ in range(k)]
    op_hash=hashlib.sha256();semantic_hash=hashlib.sha256();maximum_q=(1_000_000_000-(p-1))//p
    def emit(kind,op,pid=None,size=None):
        if len(operations)%4096==0 and time.monotonic()>deadline:raise TimeoutError('generation deadline exceeded')
        if kind=='SWITCH':line=f'SWITCH {op}\n';semantic=line
        else:
            key=pid+p*((case['seed']+104729*len(operations))%(maximum_q+1))
            if kind=='INSERT':line=f'INSERT {op} {key} {size}\n';semantic=f'INSERT {op} {pid} {size}\n';counts[op][0]+=1
            else:line=f'PROBE {op} {key}\n';semantic=f'PROBE {op} {pid}\n';counts[op][1]+=1
        operations.append(line);op_hash.update(line.encode('ascii'));semantic_hash.update(semantic.encode('ascii'))
    def probe(forced=None):
        op,logical=schedule.next(forced);logical_counts[op][logical]+=1;emit('PROBE',op,permutations[op][logical])
    for op in range(k):
        for pid,total in enumerate(physical[op]):
            remaining=total
            while remaining:
                size=min(1048576,remaining);remaining-=size;emit('INSERT',op,pid,size)
        emit('SWITCH',op)
        for _ in range(case['probe_prelude_after_each_switch']):probe(op)
    while schedule.global_index<case['total_probe_count']:probe()
    assert schedule.global_index==case['total_probe_count'] and counts==[[counts[o][0],schedule.local_counts[o]] for o in range(k)]
    headers=[f"{k} {p} {case['M']} {case['W']} {case['R']} {case['miss_penalty']}\n",f"{len(operations)} {case['B']}\n"]
    headers += [f'{op} {build} {probes}\n' for op,(build,probes) in enumerate(counts)]
    data=(''.join(headers)+''.join(operations)).encode('ascii')
    metadata=dict(case_id=case['case_id'],split=case['split'],family=case['family'],seed=case['seed'],
        k=k,p=p,memory=case['M'],write=case['W'],read=case['R'],penalty=case['miss_penalty'],period=case['B'],
        operations=len(operations),per_operator_counts=counts,partition_sizes=[size for row in physical for size in row],
        logical_partition_bytes=case['logical_partition_bytes'],logical_to_physical_pid=permutations,logical_probe_counts=logical_counts,
        build_bytes=sum(map(sum,physical)),realized_pressure=sum(map(sum,physical))/case['M'],
        sha256=hashlib.sha256(data).hexdigest(),operation_stream_sha256=op_hash.hexdigest(),semantic_modulo_P_stream_sha256=semantic_hash.hexdigest(),
        recipe_sha256=sha(ROOT/'recipe.frozen.json'),generator_sha256=sha(__file__),auditor_sha256=sha(AUDITOR),
        parameters=case['parameters'],event_counter_rule='Per-op hot/cold/filler event counters continue across phases/preludes; global/local ordinals absolute.',
        key_ordinal_rule='Zero-based absolute operation ordinal including SWITCH positions.',
        intended_use='Synthetic development/regression; different split seeds/parameters/compositions, shared declared families; no blind or official distribution claim.',
        solver_or_result_input=False,independent_unseen_test=False,official_representative_claim=False)
    return data,metadata

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--max-seconds',type=float,default=60);args=parser.parse_args()
    if not 0<args.max_seconds<=60:parser.error('--max-seconds must be in (0,60]')
    if args.out.exists():raise FileExistsError(args.out)
    freeze=load(ROOT/'provenance/source_freeze.json')
    for path,key in [(Path(__file__),'generator_sha256'),(ROOT/'test_generate.py','test_sha256'),(ROOT/'recipe.frozen.json','recipe_sha256'),(AUDITOR,'auditor_sha256'),(ROOT/'provenance/prior_inputs_0.5.json','prior_inputs_sha256')]:
        assert sha(path)==freeze[key],key
    recipe=load(ROOT/'recipe.frozen.json');prior=load(ROOT/'provenance/prior_inputs_0.5.json')
    fields=('sha256','operation_stream_sha256','semantic_modulo_P_stream_sha256')
    previous={key:{row[key] for row in prior['cases']} for key in fields};seen={key:set() for key in fields}
    args.out.mkdir(parents=True);started=time.monotonic();deadline=started+args.max_seconds;rows=[];total_bytes=0;success=False;error=None
    try:
        for case in recipe['cases']:
            data,meta=construct(case,deadline);assert len(data)<=recipe['budgets']['max_single_input_bytes']
            folder=args.out/case['split'];folder.mkdir(exist_ok=True);path=folder/(case['case_id']+'.txt');path.write_bytes(data)
            stats=audit_case(path,meta,enforce_limits=True)
            assert stats['sha256']==meta['sha256'] and stats['operation_stream_sha256']==meta['operation_stream_sha256']
            for key in fields:
                value=meta[key];assert value not in seen[key] and value not in previous[key],(key,case['case_id']);seen[key].add(value)
            meta['audit']=dict(passed=True,statistics=stats);meta_path=path.with_suffix('.meta.json');dump(meta_path,meta)
            total_bytes+=len(data)+meta_path.stat().st_size;assert total_bytes<=recipe['budgets']['total_new_input_and_metadata_bytes']
            rows.append(dict(case_id=case['case_id'],split=case['split'],family=case['family'],path=path.relative_to(args.out).as_posix(),
                metadata_path=meta_path.relative_to(args.out).as_posix(),sha256=meta['sha256'],metadata_sha256=sha(meta_path),bytes=len(data),metadata_bytes=meta_path.stat().st_size,
                operation_stream_sha256=meta['operation_stream_sha256'],semantic_modulo_P_stream_sha256=meta['semantic_modulo_P_stream_sha256'],
                operations=stats['operations'],k=stats['k'],p=stats['p'],memory=stats['memory'],seed=case['seed'],observed_pressure=stats['pressure']))
            if time.monotonic()>deadline:raise TimeoutError('generation+audit deadline exceeded')
        assert len(rows)==16 and sum(row['split']=='train' for row in rows)==8 and sum(row['split']=='eval' for row in rows)==8
        for split in ('train','eval'):dump(args.out/(split+'_manifest.json'),dict(recipe_sha256=freeze['recipe_sha256'],cases=[r for r in rows if r['split']==split],solver_runs=0))
        success=True
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    elapsed=time.monotonic()-started
    report=dict(passed=success,error=error,cases=len(rows),train=sum(r['split']=='train' for r in rows),eval=sum(r['split']=='eval' for r in rows),case_rows=rows,
        generation_write_and_audit_seconds=elapsed,allowed_seconds=args.max_seconds,total_input_and_metadata_bytes=total_bytes,
        byte_limit=recipe['budgets']['total_new_input_and_metadata_bytes'],duplicates_against_prior80=0 if success else None,
        all_three_stream_hashes_unique=success,recipe_sha256=freeze['recipe_sha256'],generator_sha256=freeze['generator_sha256'],auditor_sha256=freeze['auditor_sha256'],
        solver_runs=0,compile_runs=0,score_generated=False)
    dump(args.out/'generation_validation.json',report)
    print(json.dumps({key:report[key] for key in ('passed','error','cases','train','eval','generation_write_and_audit_seconds','total_input_and_metadata_bytes','recipe_sha256','solver_runs')}))
    return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
