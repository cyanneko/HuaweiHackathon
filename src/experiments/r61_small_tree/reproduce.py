"""R61 frozen-artifact verification and explicit offline reproduction entry points."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['verify','fit-from-recorded-labels','regenerate-labels'],default='verify');p.add_argument('--out',type=Path);p.add_argument('--datasets-root',type=Path);p.add_argument('--max-seconds',type=float,default=60);a=p.parse_args()
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    for rel,expected in manifest['frozen_files_sha256'].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected,rel
    if a.mode=='verify':print(json.dumps(dict(passed=True,scope='hash verification only; no training/simulation/compiler')));return
    if not a.out or not 0<a.max_seconds<=60:p.error('explicit new --out and max-seconds in (0,60] required')
    a.out.mkdir(parents=True,exist_ok=False);deadline=time.perf_counter()+a.max_seconds
    if a.mode=='fit-from-recorded-labels':
        trainer=module('r61_archived_tree_fit',ROOT/'tree_fit.py');labels=json.loads((ROOT/'labels.json').read_text(encoding='utf-8'));trainer.fit_and_export(labels['rows'],a.out/'model.json',a.out/'tree.hpp',deadline=deadline)
    else:
        if not a.datasets_root:p.error('--datasets-root must point to the data branch datasets directory')
        config=json.loads((ROOT/'training_config.json').read_text(encoding='utf-8'));paths=[]
        for row in config['frozen_training_inputs']:
            path=a.datasets_root/Path(row['path']).relative_to('datasets');assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'];paths.append(path)
        labels=module('r61_archived_labels',ROOT/'label_source/round61_small_tree/labels.py');labels.O=a.out;labels.generate(sorted(paths),deadline)
if __name__=='__main__':main()
