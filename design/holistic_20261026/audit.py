"""Read-only verification of frozen inputs, public-engine substitution and results."""
from pathlib import Path
import collections,hashlib,json,math,statistics
ROOT=Path(__file__).resolve().parent
def read(n):return json.loads((ROOT/n).read_text('utf8'))
def dump(n,x):(ROOT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def host(p):
    p=str(p)
    return Path(p[5].upper()+':'+p[6:]) if p.startswith('/mnt/') else Path(p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def direct(summary,a,b):
    m={(x['case'],x['profile']):x for x in summary['medians']}
    rows=[]
    for (c,p),x in m.items():
        if p!=a or x['Total_Score']<=0:continue
        y=m[c,b];rows.append(dict(case=c,ratio=y['Total_Score']/x['Total_Score'],cpu_ratio=y['Total_Decision_Time']/max(1e-9,x['Total_Decision_Time']),io_delta=y['Total_IO_Time']-x['Total_IO_Time'],miss_delta=y['Miss_Count']-x['Miss_Count']))
    return dict(cases=len(rows),geometric_ratio=math.exp(statistics.mean(math.log(x['ratio']) for x in rows)),wins=sum(x['ratio']<.999999 for x in rows),losses=sum(x['ratio']>1.000001 for x in rows),best=sorted(rows,key=lambda x:x['ratio'])[:6],worst=sorted(rows,key=lambda x:x['ratio'],reverse=True)[:6])
def main():
    frozen=read('freeze.json')['sources'];frozen.update(read('fused_freeze.json'))
    assert all(sha(ROOT/n)==h for n,h in frozen.items())
    manifests=['development_manifest.json','validation/manifest.json','cross_target_manifest.json','fused_validation/manifest.json','scale_manifest.json']
    counts={};input_shas={}
    for mf in manifests:
        rows=read(mf);counts[mf]=len(rows)
        for r in rows:
            p=host(r['file']);assert p.is_file(),p
            h=sha(p);assert h==r['sha256'],(mf,r['id'])
            with p.open() as f:header=list(map(float,(f.readline()+' '+f.readline()).split()[:8]))
            k,parts,m,w,rd,pen,n,b=header
            assert 1<=k<=8 and 2<=parts<=64 and 64*1024**2<=m<=4*1024**3
            assert 1<=w<=10000 and 1<=rd<=10000 and 1<=pen<=1000 and 1<=n<=5000000 and 1<=b<=10000
            assert header==[r[z] for z in ['K','P','M','W','R','penalty','N','B']]
            assert r.get('formal_range',True)
            if 'max_partition' in r:assert r['max_partition']<=r['M']
            # Older scale metadata lacks formal_range. Independent C++ replay
            # validates actual input ranges, per-partition sizes and feasibility.
            input_shas[str(p)]=h
    ref=(ROOT/'reference_current.cpp').read_text('utf8');cut=ref.index('/* ===== 执行引擎 ===== */')
    engines={'previous':'Previous.cpp','chosen':'MySpillScheduler.cpp','fused':'Fused.cpp','pressure':'pressure.cpp'}
    for name,src in engines.items():
        expected=(ref[:cut]+'\n#include "'+src+'"\n'+ref[cut:]).replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<MySpillScheduler>()')
        assert (ROOT/('engine_'+name+'.cpp')).read_text('utf8')==expected,name
    strict={};total=0
    for label in ['development','validation','cross','fused']:
        xs=[json.loads(l) for l in (ROOT/(label+'_strict.jsonl')).read_text().splitlines()]
        assert all(x['ok'] for x in xs);total+=len(xs);d=collections.defaultdict(collections.Counter)
        for x in xs:d[x['policy']].update({k:x.get(k,0) for k in ['stage_rejections','restore_updates','cover_searches','cover_completed','cover_accepts','forced_plans','search_us']})
        strict[label]=dict(runs=len(xs),counters=d)
    fused=[json.loads(l) for l in (ROOT/'fused_strict.jsonl').read_text().splitlines()]
    for a,b in zip(fused[::2],fused[1::2]):
        assert a['input']==b['input'] and a['policy']=='previous' and b['policy']=='fused'
        assert all(a[k]==b[k] for k in ['io','hit','miss','write_bytes','read_bytes','callbacks','spills','loads','action_hash'])
    scale=[json.loads(l) for l in (ROOT/'scale_fast_audit.jsonl').read_text().splitlines()]
    assert len(scale)==12 and all(x['ok'] for x in scale)
    for a,b in zip(scale[::2],scale[1::2]):
        assert a['input']==b['input']
        assert all(a[k]==b[k] for k in ['io','hit','miss','write_bytes','read_bytes','callbacks','spills','loads','action_hash'])
    for src,dst in [('Previous.cpp','MySpillScheduler_final.cpp'),('Fused.cpp','MySpillScheduler_scan_fused.cpp'),('MySpillScheduler.cpp','MySpillScheduler_holistic.cpp')]:
        assert sha(ROOT/src)==sha(ROOT.parent/dst)
    nondeterminism={}
    for label in ['validation','fused_validation','scale','fused_scale']:
        xs=[json.loads(l) for l in (ROOT/(label+'_runs.jsonl')).read_text().splitlines()]
        groups=collections.defaultdict(set)
        for x in xs:groups[x['case'],x['profile']].add((x['Total_IO_Time'],x['Miss_Count']))
        nondeterminism[label]=[dict(case=c,profile=p,variants=len(v)) for (c,p),v in groups.items() if len(v)>1]
    audit=dict(source_frozen=True,unchanged_sdk_except_scheduler=True,manifest_counts=counts,unique_inputs=len(input_shas),strict_runs=total,scale_action_audit_runs=12,strict=strict,action_equivalent_traces=len(fused)//2,non_timing_repeat_variation=nondeterminism,
        chosen_vs_previous=direct(read('validation_summary.json'),'previous','chosen'),pressure_vs_previous=direct(read('validation_summary.json'),'previous','pressure'),fused_vs_previous=direct(read('fused_validation_summary.json'),'previous','fused'),fused_scale_vs_previous=direct(read('fused_scale_summary.json'),'previous','fused'),sources=frozen)
    dump('final_audit.json',audit);dump('input_sha256.json',input_shas)
    print(json.dumps({k:v for k,v in audit.items() if k not in ['strict','sources']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
