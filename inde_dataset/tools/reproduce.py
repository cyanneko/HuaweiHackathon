"""Regenerate frozen cases and compare both input bytes and full metadata."""
import argparse
import json
from pathlib import Path
import tempfile
from generate import generate_case, sha, dump, FAMILIES

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    recipe=json.loads((ROOT/'recipe.json').read_text(encoding='utf-8'))
    assert sha(Path(__file__).with_name('generate.py'))==recipe['generator_sha256']
    selected=recipe['cases'] if args.all else [next(x for x in reversed(recipe['cases']) if x['split']==split and x['family']==family)
                                             for split in ['train','eval'] for family in FAMILIES]
    build=REPO/'build';build.mkdir(exist_ok=True);rows=[]
    with tempfile.TemporaryDirectory(dir=build,prefix='inde_repro_') as tmp:
        temp=Path(tmp).resolve();assert temp.is_relative_to(build.resolve())
        for spec in selected:
            output=temp/(spec['id']+'.txt');meta=generate_case(spec,output)
            frozen=ROOT/spec['split']/output.name
            expected=json.loads(frozen.with_suffix('.meta.json').read_text(encoding='utf-8'))
            assert sha(output)==sha(frozen)==expected['input_sha256'] and meta==expected
            rows.append({'path':frozen.relative_to(ROOT).as_posix(),'sha256':sha(frozen),'input_and_metadata_match':True})
    result={'status':'passed','cases':len(rows),'generator_sha256':recipe['generator_sha256'],
            'recipe_sha256':sha(ROOT/'recipe.json'),'scope':'All cases' if args.all else 'Last train and eval seed of each of 10 families, including long tiers',
            'rows':rows}
    dest=ROOT/('reproducibility_all.json' if args.all else 'reproducibility.json')
    if dest.exists():assert json.loads(dest.read_text(encoding='utf-8'))==result
    else:dump(dest,result)
    print(f'Reproduced {len(rows)} inputs and metadata byte-identically.')


if __name__=='__main__':main()
