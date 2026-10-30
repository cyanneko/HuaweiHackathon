"""Broader maximum-N robustness campaign, immutable source snapshots and checkpoints.
This is synthetic stress coverage, never an estimate of the hidden test mixture.
"""
from pathlib import Path
import sys,json,hashlib,subprocess,time,random,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO,build
from replay import parse_output
from workflow import experiment_lock
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case
OUT=ROOT/'build/round4/stress_campaign';OUT.mkdir(parents=True,exist_ok=True)
FAMILIES=['cycle','uniform','hot_shift','scan_hot','hot_sparse']
N=5000000

def request(j,family):
    # Deterministic PRNG mixing, no Python random global state or generated future in scheduler.
    x=(j*1664525+1013904223)&0xffffffff;x^=x>>15;x=(x*2246822519)&0xffffffff;x^=x>>13
    if family=='cycle':ident=j%512
    elif family=='uniform':ident=x%512
    elif family=='hot_shift':ident=((j//250000)%4)*128+(x%32 if x%100<95 else (x>>12)%128)
    elif family=='scan_hot':ident=j%512 if x%100<80 else (x>>10)%16
    else:
        ident=(x%480)+x%480//15+1  # exactly nonmultiples of16 in 0..511
        if x%100>=95:ident=((x>>10)%32)*16
    return ident//64,ident%64

def generate(path,family,mib,b):
    meta=path.with_suffix('.meta.json')
    if path.exists():
        assert meta.exists(),'Partial input found; refuse overwrite'
        d=json.loads(meta.read_text());assert hashlib.sha256(path.read_bytes()).hexdigest()==d['sha256'];return d
    probes=N-512-8;counts=[0]*8
    for j in range(probes):counts[request(j,family)[0]]+=1
    digest=hashlib.sha256()
    with path.open('x') as out:
        def emit(line):raw=line+'\n';out.write(raw);digest.update(raw.encode())
        emit(f'8 64 {mib*(1<<20)} 10000 10000 1000');emit(f'{N} {b}')
        for o in range(8):emit(f'{o} 64 {counts[o]}')
        # All equal-size objects isolate the request-pattern and callback-density effects.
        for o in range(8):
            for p in range(64):
                emit(f'INSERT {o} {p} 1048576')
        for o in range(8):emit(f'SWITCH {o}')
        for j in range(probes):
            o,p=request(j,family);emit(f'PROBE {o} {p}')
    # Variable sizes are covered by the member and generated OOD suites.
    d={'family':family,'memory_mib':mib,'b':b,'n':N,'sha256':digest.hexdigest(),'scope':'deterministic synthetic maximum-N request pattern; not hidden distribution'}
    meta.write_text(json.dumps(d,indent=2)+'\n');return d

def main():
    names=['pure','ai','pure_prune','pure_set1','ai_prune','ai_set0','ai_set025','ai_gate_d3_m00']
    sources={n:ROOT/('MySpillScheduler.cpp' if n=='pure' else 'MySpillSchedulerAI.cpp') if n in ['pure','ai'] else ROOT/'round4'/(n+'.cpp') for n in names}
    snaps=OUT/'sources';snaps.mkdir(exist_ok=True);freeze={}
    for n,p in sources.items():
        data=p.read_bytes();freeze[n]=hashlib.sha256(data).hexdigest();target=snaps/(n+'.cpp')
        if target.exists():assert target.read_bytes()==data
        else:target.write_bytes(data)
        sources[n]=target
    manifest={'scheduler_sha256':freeze,'n':N,'families':FAMILIES,'memory_mib':[64,128,256],'periods':[1,10000],'repeats':3,'timeout_seconds':60,'cases':[],'runs':[],'state':'waiting_for_experiment_lock'}
    report=ROOT/'results/round4-stress-campaign.json'
    if report.exists():raise FileExistsError('Existing incremental experiment report; inspect the running worker and preserve/checkpoint results before any restart')
    def save():
        manifest['updated_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());report.write_text(json.dumps(manifest,indent=2)+'\n')
        (OUT/'status.json').write_text(json.dumps({k:v for k,v in manifest.items() if k not in ['cases','runs','scheduler_sha256']},indent=2)+'\n')
    save()
    with experiment_lock():
        exes={'naive':build()};exes.update({n:build(p,'r4_max_'+n) for n,p in sources.items()})
    # Case order interleaves capacities; each run alternates candidate order deterministically.
    for family in FAMILIES:
        for mib in [64,128,256]:
            for b in [1,10000]:
                with experiment_lock():
                    name=f'{family}_m{mib}_b{b}';path=OUT/(name+'.txt')
                    manifest.update(state='generating',current_case=name);save()
                    meta=generate(path,family,mib,b)
                    manifest.update(state='input_audit');save();audit=audit_case(path)
                    assert audit['sha256']==meta['sha256'];manifest['cases'].append({'file':path.name,'meta':meta,'input_audit':audit});save()
                    for repeat in range(3):
                        order=list(exes);random.Random(299000+len(manifest['runs'])).shuffle(order)
                        for candidate in order:
                            if (OUT/'STOP').exists():manifest.update(state='stopped');save();return
                            manifest.update(state='running',current_candidate=candidate,current_repeat=repeat);save();start=time.perf_counter()
                            row={'case':name,'candidate':candidate,'repeat':repeat}
                            try:
                                p=subprocess.run(['/usr/bin/time','-f','PEAK_RSS_KIB %M',str(exes[candidate]),str(path)],capture_output=True,text=True,timeout=60)
                                row.update(returncode=p.returncode,wall_seconds=time.perf_counter()-start)
                                (OUT/(name+'_'+candidate+f'_r{repeat}.out')).write_text(p.stdout)
                                (OUT/(name+'_'+candidate+f'_r{repeat}.err')).write_text(p.stderr)
                                if p.returncode==0:
                                    row['metrics']=parse_output(p.stdout);row['peak_rss_kib']=int(p.stderr.split('PEAK_RSS_KIB ')[-1].strip())
                                else:row['error']=p.stderr[-1000:]
                            except subprocess.TimeoutExpired:row.update(timeout=True,wall_seconds=time.perf_counter()-start)
                            manifest['runs'].append(row);save();print(json.dumps(row),flush=True)
    manifest.update(state='complete');save();(OUT/'DONE').write_text(manifest['updated_utc']+'\n')
if __name__=='__main__':main()
