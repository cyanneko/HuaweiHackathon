"""Matched-body dense/sparse callback diagnostics; never uses full holdout."""
import json
import pathlib
import experiment as exp

out=exp.ROOT/'tmp/r74_period_views'
out.mkdir(exist_ok=True)
source=json.loads((exp.HERE/'cases.json').read_text())['cases']
selected=['synthetic_16','synthetic_17','synthetic_20','dev_slow_staggered_07']
cases=[]
for cid in selected:
    parent=next(c for c in source if c['id']==cid)
    lines=pathlib.Path(parent['path']).read_text().splitlines()
    for period in [1,10000]:
        clone=lines[:]
        count=clone[1].split()[0];clone[1]=f'{count} {period}'
        path=out/f'{cid}_B{period}.txt';path.write_text('\n'.join(clone)+'\n')
        assert clone[2:]==lines[2:]
        cases.append(dict(id=path.stem,path=str(path),sha256=exp.digest(path),group=f'B{period}',
            parent=cid,parent_sha256=parent['sha256'],operations_unchanged=True))
(out/'cases.json').write_text(json.dumps(dict(cases=cases),indent=2))
