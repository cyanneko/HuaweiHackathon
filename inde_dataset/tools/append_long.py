"""Append 20 fresh eval workloads with exactly 2,000,000 operations each."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import random
from generate import recipe,generate_case,sha,dump,FAMILIES,MIB

HERE=Path(__file__).resolve().parent
TARGET=2_000_000


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=HERE.parent);args=parser.parse_args()
    root=args.root;assert not (root/'long_recipe.json').exists(),'Refuse to overwrite a frozen long recipe'
    assert len(list((root/'train').glob('*.txt')))==500 and len(list((root/'eval').glob('*.txt')))==50
    specs=[];build=root.parent/'build';build.mkdir(exist_ok=True)
    # Build planning uses the same deterministic RNG prefix, before probe count
    # influences generation; prototypes never run a scheduler or select by score.
    with tempfile.TemporaryDirectory(dir=build,prefix='inde_long_plan_') as tmp:
        folder=Path(tmp).resolve();assert folder.is_relative_to(build.resolve())
        for fi,family in enumerate(FAMILIES):
            for variant in range(2):
                index=fi*2+variant;s=recipe(family,100+index,'eval')
                s.update({'id':f'eval_long_{fi:02d}_{variant:03d}_{family}',
                          'seed':int.from_bytes(hashlib.sha256(f'inde:1.1:long:{family}:{variant}'.encode()).digest()[:8],'big'),
                          'k':4 if variant==0 else 8,'p':32 if variant==0 else 64,
                          'memory':(512 if variant==0 else 2048)*MIB,
                          'write':512 if variant==0 else 1024,'read':2048 if variant==0 else 4096,
                          'period':31 if variant==0 else 1000,'penalty':[100,500,250,1000][index%4],
                          'schedule':'bulk' if index%5==0 else 'asynchronous',
                          'size_heat_relation':['aligned','independent','anti_aligned','balanced'][index%4],
                          'total_probes':32768,'case_kind':'long_eval','operation_target':TARGET})
                rng=random.Random(s['seed']^0x17AB);s['target_build_bytes']=int(s['memory']*rng.uniform(2.5,7.5))
                prototype=folder/(s['id']+'.txt');meta=generate_case(s,prototype)
                builds=sum(pair[0] for pair in meta['per_operator_counts'])
                s['total_probes']=TARGET-builds-s['k'];assert s['total_probes']>1_900_000
                s['planned_insert_count']=builds;specs.append(s)
    frozen={'name':'inde_dataset','version':'1.1.0','base_version':'1.0.0','operation_target':TARGET,
            'new_cases':20,'new_split':'eval','cases':specs,'generator_sha256':sha(Path(__file__)),
            'base_generator_sha256':sha(HERE/'generate.py'),'no_algorithm_score_filtering':True,
            'length_definition':'N counts INSERT, PROBE and SWITCH; each input contains exactly N=2000000.'}
    dump(root/'long_recipe.json',frozen)
    for i,s in enumerate(specs):
        path=root/'eval'/(s['id']+'.txt');assert not path.exists()
        meta=generate_case(s,path);assert meta['operations']==TARGET
        assert sum(x[0] for x in meta['per_operator_counts'])==s['planned_insert_count']
        meta['version']='1.1.0';meta['case_kind']='long_eval';meta['operation_target']=TARGET
        dump(path.with_suffix('.meta.json'),meta)
        print(f'Generated long {i+1}/20: {path.name}, N={meta["operations"]}, bytes={path.stat().st_size}',flush=True)
    print('Long generation complete; run verify.py to audit and seal version1.1.0.',flush=True)


if __name__=='__main__':main()
