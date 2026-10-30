"""Exposed alias/burst case study: compare actual and callback-observed request mass.
Full stream is offline diagnostic only; candidate debug copies log existing observations.
"""
from pathlib import Path
import sys,json,subprocess,collections,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import replay,parse_input
from workflow import experiment_lock
import case_study
case_study.setup()
OUT=ROOT/'build/round4/alias_study';OUT.mkdir(parents=True,exist_ok=True)
paths=[ROOT/'build/data/ood/055_periodic_alias_294055.txt',ROOT/'build/data/holdout/052_burst_293052.txt',ROOT/'build/data/ood/030_fixed_burst_294030.txt']
records=[]
with experiment_lock():
    exes={}
    for name,source in [('pure',ROOT/'MySpillScheduler.cpp'),('pure_set1',ROOT/'round4/pure_set1.cpp'),('ai_set025',ROOT/'round4/ai_set025.cpp')]:
        src=source.read_text();key='''        if (q <= observed_q_) return;''';assert key in src
        src='#include <iostream>\n'+src.replace(key,key+'''\n        std::cerr << "OBS " << q << " " << op << " " << pid << '\\n';''')
        target=OUT/(name+'.cpp');target.write_text(src);exes[name]=build(target,'r4_alias_'+name,audit=True)
    for path in paths:
        params,ops=parse_input(path);actual=collections.Counter((o[1],o[2]) for o in ops if o[0]=='PROBE')
        runs={};traces={}
        for name,exe in exes.items():
            p=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=60)
            (OUT/(path.stem+'_'+name+'.trace')).write_text(p.stderr)
            metric=replay(path,p.stderr,p.stdout);traces[name]=case_study.traces(p.stderr)
            obs=collections.Counter(tuple(map(int,s.split()[2:])) for s in p.stderr.splitlines() if s.startswith('OBS '))
            runs[name]={'audit':metric,'observed_top':[{'op':o,'pid':pa,'observed':v,'actual':actual[(o,pa)]} for (o,pa),v in obs.most_common(8)],'actual_top':[{'op':o,'pid':pa,'actual':v,'observed':obs[(o,pa)]} for (o,pa),v in actual.most_common(8)],'observed_total':sum(obs.values())}
        diffs={}
        def acts(line):return sorted(zip(*[iter(line.split()[6:])]*3))
        for name in ['pure_set1','ai_set025']:
            for index,(a,b) in enumerate(zip(traces['pure'],traces[name])):
                if a[0]!=b[0] or acts(a[1])!=acts(b[1]):
                    diffs[name]={'callback_index':index,'same_state':a[0]==b[0],'baseline_state':a[0],'candidate_state':b[0],'baseline_actions':a[1],'candidate_actions':b[1]};break
        records.append({'file':path.name,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'params':params,'runs':runs,'first_set_difference':diffs})
        print(path.name,{n:(round(v['audit']['io'],2),v['audit']['misses'],v['observed_total']) for n,v in runs.items()},flush=True)
(ROOT/'round4/ALIAS_CASE_STUDIES.json').write_text(json.dumps(records,indent=2)+'\n')
