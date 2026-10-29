"""R61 Root recipe construction only: no solver/model/result input."""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from audit_datasets import audit_case

MODES = ['hot','scan','big','small','cycle','alternate']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def probe_pid(name, i, small, p):
    if name == 'hot': return 0 if i%4 < 3 else 1
    if name in ('scan','cycle'): return (small+[p-1])[i%p]
    if name == 'big': return p-1 if i%8 < 7 else small[(i//8)%(p-1)]
    if name == 'small': return small[i%(p-1)]
    if name == 'alternate': return p-1 if i%2 == 0 else small[(i//2)%(p-1)]
    raise ValueError(name)


def construct(recipe, split, j):
    cfg=recipe[split];k,p,m=cfg['K'],cfg['P'],cfg['M']
    seed=cfg['seed_base']+j;rng=random.Random(seed)
    small=cfg['small_bytes'];big=cfg['big_bytes']
    if j == 7: small,big=cfg['case7_override']['small_bytes'],cfg['case7_override']['big_bytes']
    layout=[[small]*(p-1)+[big] for _ in range(k)]
    permutations=[]
    for _ in range(k):
        order=list(range(p-1));rng.shuffle(order);permutations.append(order)
    probes=recipe['source_rules']['train_probe_count_per_operator' if split=='train' else 'probe_count_per_operator']
    local=[0]*k;ops=[];segments=[[] for _ in range(k)];counts=[[0,0] for _ in range(k)]
    case_mode=recipe['ordered_case_modes'][j]

    def probe(o):
        i=local[o]
        assert i < probes
        mode=MODES[(j+o+(3 if split=='holdout' and i>=probes//2 else 0))%6]
        pid=probe_pid(mode,i,permutations[o],p)
        ops.append(f'PROBE {o} {pid}');counts[o][1]+=1;local[o]+=1
        if not segments[o] or segments[o][-1]['mode'] != mode:
            segments[o].append(dict(mode=mode,local_probe_start=i,local_probe_end=i,pid_counts=[0]*p,global_operation_positions=[]))
        segment=segments[o][-1];segment['local_probe_end']=i+1;segment['pid_counts'][pid]+=1
        segment['global_operation_positions'].append(len(ops))

    for o in range(k):
        for pid,total in enumerate(layout[o]):
            remaining=total
            while remaining:
                chunk=min(1048576,remaining);remaining-=chunk
                ops.append(f'INSERT {o} {pid} {chunk}');counts[o][0]+=1
        ops.append(f'SWITCH {o}')
        if case_mode == 'phase_overlap':
            for _ in range(probes//4): probe(o)

    remaining=k*probes-sum(local);emitted=0;half=remaining//2
    if case_mode in ('burst_mix','interleave_reverse'):
        while emitted < half:
            for o in range(k):
                for _ in range(min(8,probes-local[o],half-emitted)):
                    probe(o);emitted+=1
        while emitted < remaining:
            for o in reversed(range(k)):
                if local[o]<probes: probe(o);emitted+=1
    else:
        while emitted < remaining:
            for o in range(k):
                if local[o]<probes: probe(o);emitted+=1
    assert local == [probes]*k
    header=[f"{k} {p} {m} {cfg['W_values'][j]} {cfg['R_values'][j]} {cfg['penalty_values'][j]}",f"{len(ops)} {cfg['B_values'][j]}"]
    header += [f'{o} {b} {q}' for o,(b,q) in enumerate(counts)]
    data=('\n'.join(header+ops)+'\n').encode('ascii')
    operation_sha=hashlib.sha256(('\n'.join(ops)+'\n').encode('ascii')).hexdigest()
    case_id=f'r61root_{j:02d}_{case_mode}_{split}'
    metadata=dict(case_id=case_id,split=split,case_index_zero_based=j,composition=case_mode,seed=seed,
        k=k,p=p,memory=m,write=cfg['W_values'][j],read=cfg['R_values'][j],penalty=cfg['penalty_values'][j],period=cfg['B_values'][j],
        operations=len(ops),per_operator_counts=counts,partition_sizes=[n for row in layout for n in row],partition_layout_per_operator=layout,
        build_bytes=sum(map(sum,layout)),realized_pressure=sum(map(sum,layout))/m,phase_overlap=case_mode=='phase_overlap',
        sha256=hashlib.sha256(data).hexdigest(),raw_sha256=hashlib.sha256(data).hexdigest(),
        operation_stream_sha256=operation_sha,semantic_modulo_P_stream_sha256=operation_sha,
        small_pid_permutations=permutations,probe_segments=segments,local_probe_index_rule='absolute local index; never reset at second half',
        recipe_sha256=sha(ROOT/'recipe.root.frozen.json'),generator_sha256=sha(__file__),auditor_sha256=sha(ROOT/'audit_datasets.py'),
        intended_use=cfg['use'],base_family_claim='Known base modes in unseen composition/parameter regimes; no claim of wholly new families',
        official_hidden_distribution_claim=False,solver_results_read=False)
    return case_id,data,metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    if args.out.exists(): raise FileExistsError(args.out)
    freeze=json.loads((ROOT/'generation_freeze.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items(): assert sha(ROOT/name)==expected,name
    recipe=json.loads((ROOT/'recipe.root.frozen.json').read_text(encoding='utf-8-sig'))
    assert sha(ROOT/'recipe.root.frozen.json')=='971ceca5ef9caef7da0ffd30b9cf1e9f49d9a6296fccd2547903579e8bf1a91c'
    prior=json.loads((ROOT/'prior_public_04_dedup.json').read_text(encoding='utf-8-sig'))
    previous={key:{row[key] for row in prior['cases']} for key in ('sha256','operation_stream_sha256','semantic_modulo_P_stream_sha256')}
    seen={key:set() for key in previous};rows=[]
    args.out.mkdir(parents=True)
    for split in ('train','holdout'):
        folder=args.out/split;folder.mkdir()
        for j in range(8):
            case_id,data,metadata=construct(recipe,split,j)
            path=folder/(case_id+'.txt');path.write_bytes(data)
            stats=audit_case(path,metadata,enforce_limits=True)
            assert stats['operations']==metadata['operations']
            for field in seen:
                value=metadata[field]
                assert value not in seen[field] and value not in previous[field],(field,case_id)
                seen[field].add(value)
            metadata['audit']=dict(passed=True,source_sha256=sha(ROOT/'audit_datasets.py'),statistics=stats)
            meta_path=path.with_suffix('.meta.json');dump(meta_path,metadata)
            rows.append(dict(case_id=case_id,split=split,path=path.relative_to(args.out).as_posix(),sha256=sha(path),
                 metadata_path=meta_path.relative_to(args.out).as_posix(),metadata_sha256=sha(meta_path),N=stats['operations'],K=stats['k'],P=stats['p'],M=stats['memory'],
                 operation_stream_sha256=stats['operation_stream_sha256'],semantic_modulo_P_stream_sha256=metadata['semantic_modulo_P_stream_sha256']))
    assert len(rows)==16
    for split in ('train','holdout'):
        dump(args.out/(split+'_manifest.json'),dict(recipe_sha256=freeze['files']['recipe.root.frozen.json'],cases=[row for row in rows if row['split']==split],
             use=recipe[split]['use'],solver_runs=0))
    report=dict(passed=True,cases=16,train=8,holdout=8,errors=0,skipped=0,case_rows=rows,
        raw_unique=16,operation_stream_unique=16,modulo_P_semantic_unique=16,duplicates_against_existing64=0,
        minimum_M=min(row['M'] for row in rows),max_N=max(row['N'] for row in rows),solver_runs=0,
        generator_sha256=sha(__file__),auditor_sha256=sha(ROOT/'audit_datasets.py'),recipe_sha256=freeze['files']['recipe.root.frozen.json'])
    dump(args.out/'generation_validation.json',report)
    print(json.dumps({key:report[key] for key in ('passed','cases','train','holdout','errors','skipped','max_N','solver_runs')}))


if __name__=='__main__': main()
