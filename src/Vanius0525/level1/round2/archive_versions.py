"""Recover exact measured scheduler versions from preserved build translation units.
Only the inserted scheduler is extracted; no framework or peer algorithm is archived.
"""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import AUDIT

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'version_archive'

def digest(b):return hashlib.sha256(b).hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    wanted={};reports={}
    for report in sorted((BASE/'results').glob('*.json')):
        try:r=json.loads(report.read_text())
        except (ValueError,OSError):continue
        if not isinstance(r,dict) or 'scheduler_sha256' not in r:continue
        sources=r['scheduler_sha256'];reports[report.name]={'sha256':digest(report.read_bytes()),'schema':r.get('benchmark_schema',1),'summary':r.get('summary'),
            'sources':sources,'cases':len(r.get('cases',[])),'repeats':r.get('repeats')}
        for name,sha in sources.items():wanted.setdefault(sha,[]).append({'report':'results/'+report.name,'name':name})
    available={}
    for path in list(BASE.glob('*.cpp'))+list((BASE/'round2').glob('*.cpp')):
        b=path.read_bytes()
        if b'class MySpillScheduler' in b and b'class HashJoinEngine' not in b:available.setdefault(digest(b),(b,str(path.relative_to(BASE))))
    for path in OUT.glob('*.cpp'):
        b=path.read_bytes();available.setdefault(digest(b),(b,str(path.relative_to(BASE))))
    recovered=[]
    for meta in sorted((BASE/'build').glob('*.build.json')):
        d=json.loads(meta.read_text());sha=d.get('scheduler_sha256')
        if not sha or sha in available:continue
        translation=meta.with_name(meta.name[:-len('.build.json')]+'.cpp')
        if not translation.exists():continue
        b=translation.read_bytes()
        marker='/* ===== 执行引擎 ===== */\n'.encode()
        if marker not in b:continue
        insert=b.split(marker,1)[1].split(b'\nclass HashJoinEngine',1)[0]
        if d.get('audit') and insert.endswith(AUDIT.encode()):insert=insert[:-len(AUDIT.encode())]
        if digest(insert)!=sha:continue
        name='measured_'+sha[:16]+'.cpp';target=OUT/name
        if target.exists():assert target.read_bytes()==insert
        else:target.write_bytes(insert)
        available[sha]=(insert,str(target.relative_to(BASE)));recovered.append(name)
    entries=[]
    for sha,evidence in sorted(wanted.items()):
        if sha in available:
            b,original=available[sha]
            target=OUT/('measured_'+sha[:16]+'.cpp')
            if target.exists():assert target.read_bytes()==b
            else:target.write_bytes(b)
            entries.append({'sha256':sha,'source':str(target.relative_to(BASE)),'original_or_recovery_source':original,'bytes':len(b),'evidence':evidence,'exact_source_preserved':True})
        else:entries.append({'sha256':sha,'evidence':evidence,'exact_source_preserved':False,'note':'Do not relabel a later revision as this measured source; record missing snapshot explicitly'})
    # Keep historical report summary and identity; large raw repetitions stay local.
    ledger={'scope':'exact versions referenced by completed local benchmark reports','measured_sources':entries,'reports':reports,'raw_repetitions':'preserved locally under results/; not uploaded as large logs','source_inventory':[{'file':str(p.relative_to(BASE)),'sha256':digest(p.read_bytes()),'measured':digest(p.read_bytes()) in wanted} for p in sorted(list(BASE.glob('*.cpp'))+list((BASE/'round2').glob('*.cpp')))],'framework_archived':False,'peer_algorithm_read':False}
    (BASE/'VERSION_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({'measured_versions':len(entries),'exact_preserved':sum(e['exact_source_preserved'] for e in entries),'newly_recovered_from_build':recovered,'missing':[e['sha256'] for e in entries if not e['exact_source_preserved']]}),flush=True)

if __name__=='__main__':main()
