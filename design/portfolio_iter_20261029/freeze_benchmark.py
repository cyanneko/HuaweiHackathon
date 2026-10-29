"""Archive the exact source-only timing program, without inputs or binaries."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent;D=ROOT.parent;PROJECT=D.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);ap.add_argument('--output-stem',default='benchmark_sources');a=ap.parse_args()
    variants=json.loads((ROOT/'variants.json').read_text('utf8'))
    paths=[ROOT/'engine.cpp',ROOT/'variants.json',D/'MySpillScheduler_neural.cpp',D/'MySpillScheduler_final.cpp',D/'holistic_20261026/reference_current.cpp']+[ROOT/v['source'] for v in variants]
    records={p.relative_to(PROJECT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths}
    meta=dict(tag=a.tag,source_only=True,binary_sha256=sha(ROOT/'engine'),files=records,compiler_flags=['-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors'],compile='g++ -std=c++14 -O2 -Wall -Wextra -pedantic-errors design/portfolio_iter_20261029/engine.cpp -o engine',run='./engine <official_input.txt> <mode>')
    target=ROOT/(a.output_stem+'.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in paths:
            name=p.relative_to(PROJECT).as_posix();info=zipfile.ZipInfo(name,date_time=(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==records[name]['sha256'];z.writestr(info,raw)
        z.writestr('benchmark_manifest.json',json.dumps(meta,ensure_ascii=False,indent=2))
    meta['archive_sha256']=sha(target)
    (ROOT/(a.output_stem+'_manifest.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(files=len(paths),bytes=target.stat().st_size,sha256=meta['archive_sha256'])))
if __name__=='__main__':main()
