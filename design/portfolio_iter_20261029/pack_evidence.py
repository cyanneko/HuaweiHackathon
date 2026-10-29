"""Pack completed raw measurements at original bytes, excluding case inputs."""
from pathlib import Path
import collections,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    files=[]
    for tag in ['members_r1','members_r2','members_r3','train_g0_840','train_g1_840','train_g2_840']:
        report=json.loads((ROOT/(tag+'_summary.json')).read_text('utf8'))
        scope='members' if tag.startswith('members_') else 'train';n=785 if scope=='members' else 840
        assert report['scope']==scope and report['repeats']==(3 if scope=='members' else 1)
        if scope=='train':assert report['status']=='complete'
        assert all(v['cases']==n for v in report['summary'].values())
        rows=[json.loads(line) for line in (ROOT/(tag+'_runs.jsonl')).read_text('utf8').splitlines()]
        modes=set(map(int,report['summary']));counts=collections.Counter((r['case'],r['mode'],r['repeat']) for r in rows)
        assert len(rows)==n*len(modes)*report['repeats'] and len(counts)==len(rows) and set(counts.values())=={1}
        assert set(r['repeat'] for r in rows)==set(range(report['repeats']))
        assert all(len({r['case'] for r in rows if r['mode']==mode and r['repeat']==rep})==n for mode in modes for rep in range(report['repeats']))
        for suffix in ['_summary.json','_runs.jsonl']:
            path=ROOT/(tag+suffix);assert path.is_file();files.append(path)
    meta=dict(original_bytes_preserved=True,inputs_included=False,binaries_included=False,
        source_bundle_scope='benchmark_sources.zip binds members_r3 only; r1/r2 retain their own historical binary/source hashes',
        unpack='python -m zipfile -e design/portfolio_iter_20261029/benchmark_measurements.zip design/portfolio_iter_20261029',files={})
    target=ROOT/'benchmark_measurements.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in files:
            raw=path.read_bytes();meta['files'][path.name]=dict(bytes=len(raw),sha256=sha(raw))
            info=zipfile.ZipInfo(path.name,date_time=(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,raw)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,entry in meta['files'].items():assert sha(z.read(name))==entry['sha256']
    meta['archive_sha256']=sha(target.read_bytes());meta['archive_bytes']=target.stat().st_size
    (ROOT/'benchmark_measurements_manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(files=len(files),bytes=meta['archive_bytes'],sha256=meta['archive_sha256'])))
if __name__=='__main__':main()
