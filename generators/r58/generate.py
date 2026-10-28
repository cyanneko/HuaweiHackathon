"""R58 frozen construction only; no scheduler, result selection, or outcome reads."""
import argparse,collections,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MiB=1048576
AUDITOR=ROOT.parents[1]/'evaluation/scripts/audit_datasets.py'
sys.path.insert(0,str(AUDITOR.parent))
from audit_datasets import audit_case

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def specs():return json.loads((ROOT/'case_specs_proposal.json').read_text(encoding='utf-8-sig'))['cases']
def digest(text):return hashlib.sha256(text.encode('ascii')).hexdigest()

def generate_case(spec):
    rng=random.Random(spec['seed']);family=spec['family'];k=spec['K'];p=spec['P'];ops=[];tags=[]
    quotas=[[8*MiB]*7+[60*MiB]]
    if family=='low_opportunity_mix':quotas.append([2*MiB]*8)
    if family=='no_op_controls' and spec['variant']==1:quotas=[[8*MiB]*7+[0]]
    def put(typ,o,pid=0,size=0,tag='build'):
        ops.append((typ,o,pid,size));tags.append(tag)
    split_remaining=4 if spec.get('split_1MiB_INSERTs_into_half') else 0
    def insert(o,pid):
        nonlocal split_remaining
        if split_remaining:
            put('INSERT',o,pid,MiB//2);put('INSERT',o,pid,MiB//2);split_remaining-=1
        else:put('INSERT',o,pid,MiB)
    if family=='low_opportunity_mix':
        remaining=[q[:] for q in quotas]
        while any(any(v for v in row) for row in remaining):
            for o in range(k):
                for pid in range(p):
                    if remaining[o][pid]:insert(o,pid);remaining[o][pid]-=MiB
    else:
        for o in range(k):
            for pid in range(p):
                for _ in range(quotas[o][pid]//MiB):insert(o,pid)
    for o in range(k):put('SWITCH',o,tag='switch')
    planned=[]
    def cycle_sequence(n,tag):
        order=list(range(7));rng.shuffle(order)
        planned.append(dict(operator=0,mode=tag,planned_count=n*8,small_pid_order=order+[7]))
        return [(0,pid,tag) for _ in range(n) for pid in order+[7]]
    if family=='positive_cycles':sequence=cycle_sequence(spec['cycles'],'small_then_large_cycles')
    elif family=='temporal_alignment_mix':
        sequence=cycle_sequence(spec['aligned_cycles'],'aligned_cycles')
        planned.append(dict(operator=0,mode='phase_shift_large_hits',planned_count=2))
        sequence += [(0,7,'phase_shift_large_hits')]*2
        sequence += cycle_sequence(spec['shifted_cycles'],'shifted_cycles')
    elif family=='no_op_controls':
        if spec['variant']==0:sequence=cycle_sequence(spec['cycles'],'aligned_control_cycles')
        else:
            order=list(range(8));rng.shuffle(order);sequence=[(0,order[i%8],'resident_control') for i in range(spec['probes'])]
            planned.append(dict(operator=0,mode='resident_control',planned_count=spec['probes'],pid_order=order))
    else:
        total=spec['probes'];n0=3*total//4;n1=total//4
        assert total%4==0 and n0%8==0
        seq0=cycle_sequence(n0//8,'operator0_cycles')
        order=list(range(8));rng.shuffle(order);scan=[(1,order[i%8],'operator1_scan') for i in range(n1//2)]
        h=n1-len(scan);nhot=round(.94*h);hot=[7]*nhot+[rng.randrange(7) for _ in range(h-nhot)];rng.shuffle(hot)
        seq1=scan+[(1,pid,'operator1_hot') for pid in hot]
        planned.extend([dict(operator=1,mode='operator1_scan',planned_count=len(scan),pid_order=order),
                        dict(operator=1,mode='operator1_hot',planned_count=h,planned_hot_pid=7,planned_hot_share=.94,rounded_hot_count=nhot)])
        sequence=[];pos=[0,0];seqs=[seq0,seq1]
        for j in range(total):
            preferred=0 if rng.randrange(4)<(3 if j<total//2 else 1) else 1
            if pos[preferred]==len(seqs[preferred]):preferred=1-preferred
            sequence.append(seqs[preferred][pos[preferred]]);pos[preferred]+=1
    for o,pid,tag in sequence:put('PROBE',o,pid,tag=tag)
    assert len(ops)==spec['N'],'frozen exact N mismatch'
    counts=[[sum(x[0]=='INSERT' and x[1]==o for x in ops),sum(x[0]=='PROBE' and x[1]==o for x in ops)] for o in range(k)]
    assert sum(z[0] for z in counts)==spec['build_INSERTs']
    assert sum(z[1] for z in counts)==spec['probe_count']
    lines=[f"{k} {p} {spec['M']} {spec['W']} {spec['R']} {spec['penalty']}",f"{len(ops)} {spec['B']}"]
    lines += [f'{o} {b} {q}' for o,(b,q) in enumerate(counts)]
    canonical=[];semantic=[];segments=[]
    for typ,o,pid,size in ops:
        if typ=='SWITCH':line=f'SWITCH {o}';mod=line
        else:
            key=pid+p*rng.randrange((999999999-pid)//p+1)
            line=f'{typ} {o} {key}'+(f' {size}' if typ=='INSERT' else '')
            mod=f'{typ} {o} {pid}'+(f' {size}' if typ=='INSERT' else '')
        lines.append(line);canonical.append(line);semantic.append(mod)
    for plan in planned:
        positions=[j+1 for j,(x,tag) in enumerate(zip(ops,tags)) if x[0]=='PROBE' and x[1]==plan['operator'] and tag==plan['mode']]
        histogram=[sum(ops[j-1][2]==pid for j in positions) for pid in range(p)]
        segments.append(dict(**plan,actual_count=len(positions),actual_share_of_all_probes=len(positions)/spec['probe_count'],
                             actual_pid_counts=histogram,actual_pid_shares=[n/len(positions) if positions else 0 for n in histogram],global_input_positions=positions,
                             first_global_input_position=positions[0] if positions else None,last_global_input_position=positions[-1] if positions else None))
    interleave=[]
    if family=='low_opportunity_mix':
        probe_positions=[j+1 for j,x in enumerate(ops) if x[0]=='PROBE']
        for half in range(2):
            positions=probe_positions[half*len(probe_positions)//2:(half+1)*len(probe_positions)//2]
            actual=[sum(ops[j-1][1]==o for j in positions) for o in range(2)]
            interleave.append(dict(global_probe_half=half,planned_weights=[3,1] if half==0 else [1,3],quota_exhaustion='force remaining operator',
                                   actual_operator_counts=actual,actual_operator_shares=[n/len(positions) for n in actual],global_input_positions=positions))
    text='\n'.join(lines)+'\n'
    meta=dict(case_id=spec['case_id'],parameters=spec,seed=spec['seed'],source='generate.py frozen source, no outcome selection',
              use='train' if spec['split']=='train' else 'eval_development',partition_bytes=quotas,pressure=sum(map(sum,quotas))/spec['M'],
              realized_pressure=sum(map(sum,quotas))/spec['M'],per_operator_counts=counts,operator_modes=segments,interleave_segments=interleave,
              q_prediction=spec['q_prediction'],prediction_kind=spec['prediction_kind'],q_observed=None,
              raw_sha256=digest(text),operation_stream_sha256=digest('\n'.join(canonical)+'\n'),semantic_modulo_P_stream_sha256=digest('\n'.join(semantic)+'\n'),
              construction_similarity='Shared family construction across train/eval; distinct seeds/counts/modulo-P semantics; not blind generalization')
    return text,meta,ops

def generate_all(destination):
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    original=json.loads((ROOT/'provenance/source_freeze.original.json').read_text(encoding='utf-8-sig'))
    freeze=dict(generator_sha256=sha(__file__),tests_sha256=sha(ROOT/'tests/test_generate.py'),
                specs_sha256=sha(ROOT/'case_specs_proposal.json'),auditor_sha256=sha(AUDITOR),
                original_source_freeze=original,role='public reproduction; original pre-outcome identity retained separately')
    destination.mkdir(parents=True);(destination/'source_freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8',newline='\n')
    cases=[];semantic=[]
    for spec in specs():
        text,meta,ops=generate_case(spec);out=destination/spec['split']/(spec['case_id']+'.txt');out.parent.mkdir(exist_ok=True)
        out.write_text(text,encoding='ascii',newline='\n')
        audit=audit_case(out,meta,enforce_limits=True)
        assert audit['sha256']==meta['raw_sha256']
        assert audit['operation_stream_sha256']==meta['operation_stream_sha256']
        meta['independent_audit']=dict(passed=True,statistics=audit,source_sha256=sha(AUDITOR))
        out.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2),encoding='utf-8',newline='\n')
        semantic.append(meta['semantic_modulo_P_stream_sha256']);cases.append(dict(case_id=spec['case_id'],relative_path=out.relative_to(destination).as_posix(),N=len(ops),
                raw_sha256=meta['raw_sha256'],operation_stream_sha256=meta['operation_stream_sha256'],semantic_modulo_P_stream_sha256=semantic[-1],independent_audit_passed=True))
    assert len(cases)==16 and len(set(semantic))==16,'semantic duplicate: stop without regeneration'
    return dict(passed=True,cases=cases,source_freeze=freeze,no_algorithm_runs=True,q_observed=None)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path,help='new output directory; must not exist')
    args=parser.parse_args()
    started=time.perf_counter();report=generate_all(args.out);report['generation_and_audit_seconds']=time.perf_counter()-started
    (args.out/'generation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=report['passed'],cases=len(report['cases']),output=str(args.out))))
if __name__=='__main__':main()
