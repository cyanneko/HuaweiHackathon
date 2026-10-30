"""Regenerate the frozen long inputs without modifying their originals."""
import argparse
import json
from pathlib import Path
import tempfile
from generate import sha,dump,generate_case

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    plan=json.loads((ROOT/'long_recipe.json').read_text(encoding='utf-8'))
    assert sha(Path(__file__).with_name('append_long.py'))==plan['generator_sha256']
    selected=plan['cases'] if args.all else [plan['cases'][2],plan['cases'][17]]
    build=ROOT.parent/'build';build.mkdir(exist_ok=True);rows=[]
    with tempfile.TemporaryDirectory(dir=build,prefix='inde_long_repro_') as tmp:
        folder=Path(tmp).resolve();assert folder.is_relative_to(build.resolve())
        for spec in selected:
            dest=folder/(spec['id']+'.txt');meta=generate_case(spec,dest)
            meta.update({'version':'1.1.0','case_kind':'long_eval','operation_target':2_000_000})
            frozen=ROOT/'eval'/dest.name;expected=json.loads(frozen.with_suffix('.meta.json').read_text(encoding='utf-8'))
            assert sha(dest)==sha(frozen)==expected['input_sha256'] and meta==expected
            rows.append({'path':frozen.relative_to(ROOT).as_posix(),'sha256':sha(frozen),'input_and_metadata_match':True})
    result={'status':'passed','cases':len(rows),'operation_target':2_000_000,'long_recipe_sha256':sha(ROOT/'long_recipe.json'),'rows':rows}
    dump(ROOT/('long_reproducibility_all.json' if args.all else 'long_reproducibility.json'),result)
    print(f'Reproduced {len(rows)} long inputs and metadata identically.')


if __name__=='__main__':main()
