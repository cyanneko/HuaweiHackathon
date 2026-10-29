"""Archive portable single-program sources proven identical to measured binaries."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];D=ROOT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);ap.add_argument('--output-stem',default='standalone_sources');a=ap.parse_args()
    report=json.loads((ROOT/(a.tag+'_summary.json')).read_text('utf8'));assert report['status']=='complete' and report['deployment'].startswith('three independently')
    modes={'0':'neural','2':'baseline',str(report['published_checkpoint']['checkpoint_mode']):'recommended'}
    assert all(sha(D/'build'/name)==report['binary_sha256_by_mode'][mode] for mode,name in modes.items())
    paths=[D/'build'/('engine_'+name+'.cpp') for name in modes.values()]+[D/'MySpillScheduler_tree.cpp',D/'MySpillScheduler_neural.cpp']
    assert all(b'/mnt/' not in p.read_bytes() and b':/Users/' not in p.read_bytes() for p in paths)
    meta=dict(tag=a.tag,source_only=True,normalized_includes='Only generated include paths changed from absolute to relative; recompiled binaries are byte-identical to timed binaries.',
        measured_binary_sha256_by_mode=report['binary_sha256_by_mode'],binary_identity_verified=True,
        historical_build_sources=report['build_sources'],
        files={p.relative_to(PROJECT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths},
        compiler_flags=['-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors'],
        reproduction='Compile each design/build/engine_{recommended,neural,baseline}.cpp separately using these flags; run each program with the input path only. Original input files and binaries are excluded.')
    target=ROOT/(a.output_stem+'.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in paths:
            info=zipfile.ZipInfo(p.relative_to(PROJECT).as_posix(),date_time=(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,p.read_bytes())
        z.writestr('standalone_manifest.json',json.dumps(meta,ensure_ascii=False,indent=2))
    meta['archive_sha256']=sha(target)
    (ROOT/(a.output_stem+'_manifest.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(files=len(paths),bytes=target.stat().st_size,binary_identity_verified=True,archive_sha256=meta['archive_sha256'])))
if __name__=='__main__':main()
