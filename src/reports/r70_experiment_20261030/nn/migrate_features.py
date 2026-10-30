"""Re-extract corrected causal features without rerunning or modifying suffix G."""
import json
from collections import Counter
import pipeline as p

source=p.ROOT/'labels_v2';destination=p.ROOT/'labels_v3'
if destination.exists():raise FileExistsError(destination)
destination.mkdir();cases=p.inventory();changed=Counter();rows_count=0;plans_count=0;files=[]
for path in sorted(source.glob('*.jsonl')):
    c=p.core.Case.read(cases[path.stem]['path']);rows=[]
    for line in path.read_text().splitlines():
        row=json.loads(line);s=p.core.State.from_snapshot(c,row['anchor_snapshot']);plans=p.core.pool(s);xs=p.features(s,plans)
        assert len(plans)==len(row['plans'])
        for a,x,old in zip(plans,xs,row['plans']):
            assert old['spill']==list(a)
            for i,(u,v) in enumerate(zip(old['x'],x)):
                if p.bits([u])!=p.bits([v]):changed[i]+=1
            old['x']=x;plans_count+=1
        row['feature_version']=p.FEATURE_VERSION
        row['feature_migration']=dict(from_version='r70-causal32-v1',old_labels_sha256=p.sha(path),
            reason='explicit sequential double accumulation to match C++14, including strict density rank',suffix_G_unchanged=True)
        groups={}
        for plan in row['plans']:
            if plan['valid_cost']:groups.setdefault(p.bits(plan['x']),set()).add(plan['cost']['G_delta'])
        row['conflicting_identical_feature_groups']=sum(len(v)>1 for v in groups.values())
        rows.append(row);rows_count+=1
    new=destination/path.name;new.write_text(''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows))
    report=json.loads(path.with_suffix('.report.json').read_text());report['labels_sha256']=p.sha(new)
    report['feature_migration_only_no_suffix_rerun']=True
    p.dump(new.with_suffix('.report.json'),report);files.append(dict(path=new.name,sha256=p.sha(new)))
batch=json.loads((source/'batch_report.json').read_text());batch['feature_version']=p.FEATURE_VERSION
p.dump(destination/'batch_report.json',batch)
result=dict(rows=rows_count,plans=plans_count,changed_fp32_dimensions=dict(changed),suffix_G_all_unchanged=True,
            from_directory=str(source),to_directory=str(destination),files=files)
p.dump(destination/'migration_report.json',result);print(json.dumps(result),flush=True)
