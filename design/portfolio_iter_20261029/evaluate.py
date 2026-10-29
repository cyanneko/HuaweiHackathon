"""Serial portfolio evaluation with actual SDK callback time and live mean Score."""
from pathlib import Path
import argparse,collections,hashlib,json,math,statistics,subprocess,sys,time
ROOT=Path(__file__).resolve().parent;DESIGN=ROOT.parent
PUBLIC=DESIGN/'dataset_integration_20261029/worktree'
sys.path.insert(0,str(PUBLIC/'evaluation'))
from evaluate import snapshot_dataset,parse_metrics,object_hash,normalize
from scripts.audit_datasets import audit_case
EXPECTED='5e49bfe12077a229b8099c86bb8f67d3ba78491058d54a98b71d03acde5dea86'
def read(p):return json.loads(p.read_text('utf8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def cases(scope,tag):
    out=[]
    if scope=='valid':
        rows=read(DESIGN/'neural_20261027/valid_manifest.json')
        for r in rows:
            p=Path(r['linux_file']);stats=audit_case(p);assert stats['sha256']==r['sha256']
            out.append(dict(case=r['sha256'],member='development',path=p,stats=stats))
        return out,None,[]
    snap=ROOT/'snapshots'/tag;snap.mkdir(parents=True,exist_ok=False);identities=[]
    root=PUBLIC/'datasets' if scope=='eval' else DESIGN/'member_eval_20261030/worktree/datasets'
    members=['cyanneko','liunianwww'] if scope=='eval' else [p.name for p in sorted(root.iterdir()) if p.is_dir() and any((p/'eval').glob('*.txt'))]
    for member in members:
        identity,pending=snapshot_dataset(root,member,snap,False);identities.append(identity)
        for m,name,path,stats in pending:out.append(dict(case=stats['sha256'],member=m,path=path,stats=stats))
    suite=object_hash([dict(member=d['member'],version=d['version'],sha256=d['sha256']) for d in sorted(identities,key=lambda d:d['member'])])
    if scope=='eval':assert suite==EXPECTED and len(out)==568
    return out,suite,identities
def summarize(rows):
    g=collections.defaultdict(list)
    for r in rows:g[r['case'],r['mode']].append(r)
    med={k:{n:statistics.mean(r[n] for r in rs) for n in ['Total_Score','Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count']} for k,rs in g.items()}
    modes=sorted({k[1] for k in med});out={}
    for mode in modes:
        vals=[v for (c,m),v in med.items() if m==mode];total=math.fsum(v['Total_Score'] for v in vals)
        v=dict(cases=len(vals),mean_score=total/len(vals),total_score=total,mean_decision_us=statistics.mean(x['Total_Decision_Time'] for x in vals),miss_count=math.fsum(x['Miss_Count'] for x in vals))
        for base,label in [(0,'nn'),(1,'previous'),(2,'naive')]:
            if base in modes:
                pairs=[(med[c,mode],med[c,base]) for c,m in med if m==mode and (c,base) in med];bt=math.fsum(b['Total_Score'] for a,b in pairs);ct=math.fsum(a['Total_Score'] for a,b in pairs)
                v['decrease_vs_'+label+'_percent']=100*(1-ct/bt) if bt else 0
                ratios=[a['Total_Score']/b['Total_Score'] if b['Total_Score'] else 1 if not a['Total_Score'] else math.inf for a,b in pairs]
                v['worst_vs_'+label]=max(ratios)
        out[str(mode)]=v
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scope',choices=['valid','eval','members'],required=True);ap.add_argument('--tag',required=True);ap.add_argument('--ids',default='0,1,2');ap.add_argument('--repeats',type=int,default=1)
    a=ap.parse_args();ids=[int(x) for x in a.ids.split(',')];data,suite,identities=cases(a.scope,a.tag);rows=[]
    registered=read(ROOT/'variants.json');variants={str(v['id']):v['name'] for v in registered};variants.update({'0':'neural_reference','1':'previous_reference','2':'official_naive'});variants.update({str(100+i):'fixed_expert_'+str(i) for i in range(8)})
    sources={str(v['id']):dict(name=v['name'],source=v['source'],sha256=v['sha256']) for v in registered if v['id'] in ids}
    for mode,path in [(0,DESIGN/'MySpillScheduler_neural.cpp'),(1,DESIGN/'MySpillScheduler_final.cpp')]:
        if mode in ids:sources[str(mode)]=dict(name=variants[str(mode)],source=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    binary_hash=hashlib.sha256((ROOT/'engine').read_bytes()).hexdigest()
    assert not (ROOT/(a.tag+'_runs.jsonl')).exists()
    start=time.monotonic()
    with (ROOT/(a.tag+'_runs.jsonl')).open('w') as f:
        for rep in range(a.repeats):
            for i,r in enumerate(data):
                for mode in (ids if (i+rep)%2==0 else ids[::-1]):
                    p=subprocess.run([str(ROOT/'engine'),str(r['path']),str(mode)],capture_output=True,text=True,timeout=120)
                    if p.returncode:raise RuntimeError((r['case'],mode,p.stderr))
                    metrics=parse_metrics(p.stdout,r['stats'],'official-2026-10-26')
                    row=dict(case=r['case'],member=r['member'],mode=mode,repeat=rep,**metrics);rows.append(row);f.write(json.dumps(row)+'\n')
                if (i+1)%32==0 or i+1==len(data):
                    live=dict(scope=a.scope,suite_id=suite,tag=a.tag,repeat=rep+1,completed_cases=i+1,total_cases=len(data),provisional=rep+1<a.repeats or i+1<len(data),summary=summarize(rows))
                    dump(ROOT/'live_metrics.json',live);print(json.dumps(dict(progress=f'{rep+1}/{a.repeats} {i+1}/{len(data)}',scope=a.scope)),flush=True)
    out=dict(scope=a.scope,suite_id=suite,datasets=identities,tag=a.tag,repeats=a.repeats,aggregation='sum of per-case arithmetic means; mean_score=total_score/case_count',variants=variants,summary=summarize(rows),by_member={m:summarize([r for r in rows if r['member']==m]) for m in sorted({r['member'] for r in rows})},wall_seconds=time.monotonic()-start,
        candidate_sources=sources,binary_sha256=binary_hash,protocol='official-2026-10-26',timer='unmodified public engine; callback time includes getSystemState')
    assert binary_hash==hashlib.sha256((ROOT/'engine').read_bytes()).hexdigest(),'Engine changed during serial timing'
    if identities and 2 in ids:
        def public_rows(mode):return [dict(member=r['member'],case=r['case'],repeat=r['repeat'],metrics={n:r[n] for n in ['Total_Score','Total_Decision_Time','Total_IO_Time','Hit_Count','Miss_Count']}) for r in rows if r['mode']==mode]
        baseline=public_rows(2);out['normalization']={str(mode):normalize(public_rows(mode),baseline,identities) for mode in ids if mode!=2}
    dump(ROOT/(a.tag+'_summary.json'),out);print(json.dumps(out['summary']),flush=True)
if __name__=='__main__':main()
