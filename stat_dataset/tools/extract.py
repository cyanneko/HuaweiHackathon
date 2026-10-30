"""Restore a split from deterministic archives, verifying SHA before promotion."""
import argparse,gzip,hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def contained(root,path):
    p=(root/path).resolve()
    if p!=root and root not in p.parents:raise ValueError('path escapes output root')
    return p
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--split',choices=['train','dev','eval','all'],default='eval');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    m=json.loads((ROOT/'manifest.json').read_text());root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    rows=[r for r in m['cases'] if a.split=='all' or r['split']==a.split]
    for split in sorted({r['split'] for r in rows}):
        v=contained(root,split+'/VERSION');data=(m['version']+'\n').encode()
        if v.exists() and v.read_text().strip()!=m['version']:raise ValueError('existing split VERSION differs; no inputs written')
    for r in rows:
        src=contained(ROOT.resolve(),r['archive']);dst=contained(root,r['input'])
        if dst.exists():
            if sha(dst)!=r['sha256']:raise ValueError('refuse overwrite of different existing input: '+r['input'])
            continue
        if sha(src)!=r['archive_sha256']:raise ValueError('archive SHA mismatch')
        dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name(dst.name+'.partial');h=hashlib.sha256()
        with gzip.open(src,'rb') as inp,tmp.open('xb') as out:
            for b in iter(lambda:inp.read(1048576),b''):h.update(b);out.write(b)
        if h.hexdigest()!=r['sha256']:raise ValueError('uncompressed SHA mismatch; preserve partial for diagnosis')
        if dst.exists():raise FileExistsError('destination appeared while extracting')
        tmp.rename(dst)
    for split in sorted({r['split'] for r in rows}):
        v=root/split/'VERSION';data=(m['version']+'\n').encode()
        if v.exists() and v.read_text().strip()!=m['version']:raise ValueError('existing split VERSION differs')
        v.parent.mkdir(parents=True,exist_ok=True)
        if not v.exists():v.write_bytes(data)
    print(json.dumps({'verified_cases':len(rows),'split':a.split,'version':m['version']}))
if __name__=='__main__':main()
