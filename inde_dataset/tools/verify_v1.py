"""Independent format, byte/stream isolation, scale and hotspot-window audit."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
from generate import sha, dump, FAMILIES

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
KEYS=['sha256','operation_stream_sha256','partition_stream_sha256']


def extra_audit(path,meta):
    s=meta['recipe'];k,p=s['k'],s['p'];counts=meta['per_operator_counts']
    windows=[[[0]*p for _ in range(s['windows'])] for _ in range(k)]
    indices=[0]*k;wi=[0]*k;phase=[False]*k;overlap=0;switch_positions=[None]*k
    semantic=hashlib.sha256(f'{k} {p}\n'.encode())
    with path.open('rb') as stream:
        stream.readline();n,_=map(int,stream.readline().split())
        assert [int(stream.readline().split()[0]) for _ in range(k)]==list(range(k))
        for step in range(n):
            fields=stream.readline().split();kind=fields[0];o=int(fields[1])
            if kind==b'SWITCH':
                phase[o]=True;switch_positions[o]=step
                semantic.update(f'SWITCH {o}\n'.encode())
            else:
                pid=int(fields[2])%p
                if kind==b'INSERT':semantic.update(f'INSERT {o} {pid} {int(fields[3])}\n'.encode())
                else:
                    semantic.update(f'PROBE {o} {pid}\n'.encode())
                    while indices[o]>=meta['probe_windows'][o][wi[o]]['end']:wi[o]+=1
                    windows[o][wi[o]][pid]+=1;indices[o]+=1
                    if not all(phase):overlap+=1
    expected=observed=variance=0.0;peak_changes=[];peak_matches=[];quartiles=[]
    for o in range(k):
        peaks=[x['expected_peak'] for x in meta['probe_windows'][o]]
        peak_changes.append(sum(a!=b for a,b in zip(peaks,peaks[1:])))
        probe_counts=[sum(win[j] for win in windows[o]) for j in range(p)]
        quartiles.append(sum(sorted(probe_counts,reverse=True)[:(p+3)//4])/sum(probe_counts))
        assert len(meta['probe_windows'][o])==64 and indices[o]==counts[o][1]
        for w,(actual,plan) in enumerate(zip(windows[o],meta['probe_windows'][o])):
            assert plan['begin']==w*counts[o][1]//64 and plan['end']==(w+1)*counts[o][1]//64
            length=plan['end']-plan['begin'];assert sum(actual)==length
            prob=plan['expected_max_share'];expected+=length*prob
            variance+=length*prob*(1-prob);observed+=actual[plan['expected_peak']]
            peak_matches.append(int(max(range(p),key=actual.__getitem__)==plan['expected_peak']))
        profiles={x['profile_sha256'] for x in meta['probe_windows'][o]}
        assert (len(profiles)==1) if s['family'].startswith('static_') else len(profiles)>=3
    z=(observed-expected)/math.sqrt(max(1.0,variance))
    assert abs(z)<8,(path.name,'unexpected generated peak mass',z)
    return {'partition_stream_sha256':semantic.hexdigest(),'probe_overlap_fraction':overlap/s['total_probes'],
            'switch_operation_indices_zero_based':switch_positions,'expected_peak_changes_per_operator':peak_changes,
            'observed_expected_peak_match_fraction':statistics.mean(peak_matches),
            'peak_mass_zscore':z,'top_quartile_probe_share_per_operator':quartiles,
            'probe_window_counts':windows}


def historic_hashes():
    hashes={key:set() for key in KEYS};sources=[]
    def collect(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key in hashes and isinstance(value,str):hashes[key].add(value)
                elif isinstance(value,(list,dict)):collect(value)
        elif isinstance(obj,list):
            for value in obj:collect(value)
    for path in list(REPO.glob('*/manifest.json'))+list(REPO.glob('datasets/*/manifest.json')):
        if path.parent.name=='inde_dataset':continue
        collect(json.loads(path.read_text(encoding='utf-8-sig')));sources.append(path.relative_to(REPO).as_posix())
    return hashes,sources


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=HERE.parent)
    parser.add_argument('--expected-train',type=int,default=500);parser.add_argument('--expected-eval',type=int,default=50)
    args=parser.parse_args();root=args.root;recipe=json.loads((root/'recipe.json').read_text(encoding='utf-8'))
    assert recipe['train_cases']==args.expected_train and recipe['eval_cases']==args.expected_eval
    assert recipe['generator_sha256']==sha(HERE/'generate.py')
    assert (root/'VERSION').read_text().strip()==(root/'eval/VERSION').read_text().strip()=='1.0.0'
    auditor_path=REPO/'evaluation/scripts/audit_datasets.py'
    spec=importlib.util.spec_from_file_location('independent_public_auditor',auditor_path)
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    old,sources=historic_hashes();seen={key:set() for key in KEYS};rows=[];full_windows=[]
    for split,count in [('train',args.expected_train),('eval',args.expected_eval)]:
        files=sorted((root/split).glob('*.txt'));assert len(files)==count
        assert len(list((root/split).glob('*.meta.json')))==count
        for path in files:
            meta_path=path.with_suffix('.meta.json');meta=json.loads(meta_path.read_text(encoding='utf-8'))
            s=meta['recipe'];assert s['split']==split and s in recipe['cases']
            actual=auditor.audit_case(path,metadata=meta,enforce_limits=True)
            assert actual['sha256']==meta['input_sha256']
            assert actual['operations']>=32768 and 2<=actual['pressure']<=8
            assert 0<actual['max_partition_bytes']<=.70*actual['memory']
            assert actual['min_positive_partition_bytes']>0
            extra=extra_audit(path,meta)
            for key,value in {**actual,**extra}.items():
                if key in seen:
                    assert value not in seen[key],(key,'duplicate within/across splits',path.name)
                    assert value not in old[key],(key,'duplicate prior published stream',path.name)
                    seen[key].add(value)
            rows.append({'path':path.relative_to(root).as_posix(),'split':split,'family':s['family'],'seed':s['seed'],
                         'schedule':s['schedule'],'size_heat_relation':s['size_heat_relation'],
                         'metadata_sha256':sha(meta_path),**actual,
                         **{key:value for key,value in extra.items() if key!='probe_window_counts'}})
            full_windows.append({'path':path.relative_to(root).as_posix(),'counts':extra['probe_window_counts']})
            if len(rows)%10==0:print(f'Audited {len(rows)}/{args.expected_train+args.expected_eval}',flush=True)
    summaries={}
    for split in ['train','eval']:
        group=[x for x in rows if x['split']==split]
        summary={'cases':len(group),'families':dict(Counter(x['family'] for x in group)),
                 'operations_total':sum(x['operations'] for x in group),
                 'operations_min':min(x['operations'] for x in group),'operations_median':statistics.median(x['operations'] for x in group),
                 'operations_max':max(x['operations'] for x in group),'input_bytes':sum(x['file_bytes'] for x in group),
                 'build_bytes_min':min(x['build_bytes'] for x in group),'build_bytes_max':max(x['build_bytes'] for x in group),
                 'build_bytes_total':sum(x['build_bytes'] for x in group),
                 'memory_bytes_min':min(x['memory'] for x in group),'memory_bytes_max':max(x['memory'] for x in group),
                 'pressure_min':min(x['pressure'] for x in group),'pressure_max':max(x['pressure'] for x in group),
                 'mixed_phase_cases':sum(x['phase_overlap'] for x in group),
                 'schedule_counts':dict(Counter(x['schedule'] for x in group)),
                 'relation_counts':dict(Counter(x['size_heat_relation'] for x in group))}
        assert set(summary['families'])==set(FAMILIES) and len(set(summary['families'].values()))==1
        summaries[split]=summary
    suite=hashlib.sha256(''.join(x['path']+' '+x['sha256']+'\n' for x in rows).encode()).hexdigest()
    manifest={'schema_version':1,'name':'inde_dataset','version':'1.0.0','suite_id':suite,
              'recipe_sha256':sha(root/'recipe.json'),'generator_sha256':sha(HERE/'generate.py'),
              'summary':summaries,'cases':rows,'all_new_synthetic':True,
              'exposure':'New generated independent seeds, known synthetic families; no solver/model performance filtering or evaluation in this release.'}
    report={'status':'passed','cases':len(rows),'errors':[],'suite_id':suite,
            'independent_auditor_sha256':sha(auditor_path),'verifier_sha256':sha(Path(__file__)),
            'checks':['exact split and family counts','official fields, phases, counts and whole-partition capacity',
                      'ascending operator headers','recipe and metadata identity','raw, operation and partition-semantic uniqueness',
                      'train/eval isolation','large memory pressure','constant static profiles and varying dynamic profiles',
                      'realized peak mass statistical check'],
            'historical_manifest_sources':sources,'historical_hash_counts':{k:len(v) for k,v in old.items()},
            'summary':summaries,'limitations':'Synthetic workload recipe, not official hidden workloads; distribution audit is not algorithm performance validation.'}
    for name,obj in [('manifest.json',manifest),('validation.json',report),('probe_windows.json',full_windows)]:
        target=root/name
        if target.exists():assert json.loads(target.read_text(encoding='utf-8'))==obj,'Frozen audit differs; inspect rather than overwrite'
        else:dump(target,obj)
    print(json.dumps({'status':'passed','summary':summaries,'suite_id':suite},indent=2))


if __name__=='__main__':main()
