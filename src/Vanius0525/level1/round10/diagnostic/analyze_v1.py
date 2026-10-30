"""One-pass descriptive statistics of every existing train60 Zipf input; no solver."""
import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
ROOT = ROUND.parent
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock

METHODS = ('paired100', 'risk_pool100', 'r80')
FEATURES = ('size_heat_spearman', 'log_size_heat_pearson', 'within_op_size_heat_spearman_weighted',
            'total_bytes_over_memory', 'max_object_over_memory', 'weighted_within_op_cv2',
            'weighted_within_op_top1', 'hot90_bytes_over_memory', 'largest_object_probe_share',
            'period', 'operations', 'partitions_total')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path): return json.loads(path.read_text())


def save(path, value, immutable=True):
    body = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
    if immutable:
        with path.open('x') as f: f.write(body)
    else: path.write_text(body)


def pearson(x, y):
    assert len(x) == len(y)
    if len(x) < 2 or min(x) == max(x) or min(y) == max(y): return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    xx, yy = [v-mx for v in x], [v-my for v in y]
    denom = math.sqrt(math.fsum(v*v for v in xx)*math.fsum(v*v for v in yy))
    return max(-1., min(1., math.fsum(a*b for a,b in zip(xx,yy))/denom))


def ranks(x):
    order = sorted(range(len(x)), key=lambda i:x[i]); out=[0.]*len(x); j=0
    while j < len(order):
        end=j+1
        while end<len(order) and x[order[end]]==x[order[j]]: end+=1
        for q in range(j,end): out[order[q]]=(j+end-1)/2+1
        j=end
    return out


def spearman(x, y): return pearson(ranks(x),ranks(y))


def associations(size, count):
    return {'objects':len(size), 'pearson':pearson(size,count), 'spearman':spearman(size,count),
            'log1p_pearson':pearson([math.log1p(x) for x in size],[math.log1p(x) for x in count]),
            'null_means_constant_size_or_count':min(size)==max(size) or min(count)==max(count)}


def distribution(count):
    total=sum(count)
    if not total: return None
    q=[x/total for x in count]; hhi=math.fsum(x*x for x in q); order=sorted(q,reverse=True)
    return {'hhi':hhi,'effective_objects':1/hhi,'cv2':len(count)*hhi-1,
            'top1':order[0],'top4':sum(order[:4]),'observed_nonzero_objects':sum(x>0 for x in count)}


def prepare():
    with experiment_lock():
        plan=load(ROUND/'PLAN_V1.json'); rootfreeze=load(ROUND/'EXECUTION_FREEZE_V1.json')
        assert rootfreeze['plan_sha256']==sha(ROUND/'PLAN_V1.json')
        for n,h in rootfreeze['files'].items(): assert sha(ROUND/n)==h,n
        result=load(ROUND/'RESULTS_V1.json'); assert result['complete'] and result['new_timed_runs']==360
        cases=[c for c in plan['cases'] if c['family']=='random_zipf'];assert len(cases)==24
        lock=load(ROOT/'round9/V21_DATASET_LOCK.json')
        assert all(c['case'] in lock['train'] and c['case'] not in lock['dev'] and c['case'] not in lock['eval'] for c in cases)
        files=[HERE/'CONTRACT_V1.md',HERE/'analyze_v1.py',ROUND/'PLAN_V1.json',ROUND/'RESULTS_V1.json',
               ROUND/'EXECUTION_FREEZE_V1.json',ROUND/'R80_next_hier_fast100_reference.cpp',
               ROOT/'round9/V21_DATASET_LOCK.json',ROOT/'round9/pure/R80_ROUND10_REVIEW_V1.json',ROOT/'workflow.py']
        frozen={'stage':'all24-zipf-training-descriptive-v1','cases':cases,'features':list(FEATURES),
                'files':{str(p.relative_to(ROOT)):sha(p) for p in files},'max_input_passes':24,
                'input_bytes_expected':sum((ROOT/c['input']).stat().st_size for c in cases),
                'operations_expected':sum(c['operations'] for c in cases),
                'new_solver_runs':0,'new_compiles':0,'new_teacher_runs':0,'eval_dyna_inputs_read':0}
        save(HERE/'EXECUTION_FREEZE_V1.json',frozen)
        print('frozen',sha(HERE/'EXECUTION_FREEZE_V1.json'),'24 existing Zipf inputs',flush=True)


def analyze(case, result):
    h=hashlib.sha256(); byte_count=0
    with (ROOT/case['input']).open('rb') as f:
        def line():
            nonlocal byte_count
            raw=f.readline();h.update(raw);byte_count+=len(raw);return raw.decode().split()
        k,p,m,w,r,penalty=map(int,line());n,b=map(int,line())
        assert 1<=k<=8 and 2<=p<=64 and 64*(1<<20)<=m<=4*(1<<30)
        headers=[tuple(map(int,line())) for _ in range(k)];assert [x[0] for x in headers]==list(range(k))
        expected_probes=sum(x[2] for x in headers);assert expected_probes==case['probes']>0 and n==case['operations']
        size=[0]*(k*p);count=[0]*(k*p);quarters=[[0]*4 for _ in size];potential=[0]*(k*p)
        phase=[False]*k;build=[0]*k;probe=[0]*k;counter=q=0;previous_periodic=False
        first_probe=last_insert=None;mixed_requests=probes_while_build=0
        for index in range(n):
            a=line();assert a
            typ,o=a[0],int(a[1]);assert 0<=o<k
            if typ=='SWITCH':
                assert len(a)==2 and not phase[o];phase[o]=True;previous_periodic=False;continue
            key=int(a[2]);pid=key%p;i=o*p+pid
            if 0<sum(phase)<k:mixed_requests+=1
            if typ=='INSERT':
                assert not phase[o] and len(a)==4
                z=int(a[3]);assert 1<=z<=1<<20;size[i]+=z;assert size[i]<=m
                build[o]+=1;last_insert=index
            else:
                assert typ=='PROBE' and len(a)==3 and phase[o]
                if previous_periodic:potential[i]+=1
                if not all(phase):probes_while_build+=1
                if first_probe is None:first_probe=index
                count[i]+=1;quarters[i][min(3,q*4//expected_probes)]+=1;q+=1;probe[o]+=1
            counter+=1;previous_periodic=counter%b==0
        assert not line();assert all(phase)
        assert [(build[o],probe[o]) for o in range(k)]==[x[1:] for x in headers]
    assert h.hexdigest()==case['input_sha256'] and byte_count==(ROOT/case['input']).stat().st_size
    assert q==expected_probes and sum(count)==q and sum(map(sum,quarters))==q
    all_assoc=associations(size,count);operators=[]
    for o in range(k):
        s=size[o*p:(o+1)*p];c=count[o*p:(o+1)*p];dist=distribution(c)
        ids=sorted(range(p),key=lambda j:(-c[j],j));winner=ids[0] if sum(c) else None
        period_rows=[]
        for t in range(4):
            cc=[quarters[o*p+j][t] for j in range(p)];total=sum(cc)
            tw=min(range(p),key=lambda j:(-cc[j],j)) if total else None
            period_rows.append({'quarter':t,'operator_probes':total,'top1_partition':tw,
                                'full_stream_top1_share':cc[winner]/total if total and winner is not None else None,
                                'full_stream_top1_is_quarter_top1':tw==winner if total else None})
        avg=statistics.fmean(s);size_cv2=statistics.fmean([(x-avg)**2 for x in s])/(avg*avg) if avg else None
        operators.append({'op':o,'final_bytes':sum(s),'bytes_over_memory':sum(s)/m,'probe_count':sum(c),
                          'global_probe_share':sum(c)/q,'size_heat':associations(s,c),'heat':dist,'size_cv2':size_cv2,
                          'full_stream_top1_partition':winner,'quarters':period_rows})
    def weighted(key):
        return math.fsum(op['global_probe_share']*op['heat'][key] for op in operators if op['heat'] is not None)
    valid_rhos=[op for op in operators if op['size_heat']['spearman'] is not None and op['probe_count']]
    rho_weight=sum(op['global_probe_share'] for op in valid_rhos)
    within_rho=sum(op['global_probe_share']*op['size_heat']['spearman'] for op in valid_rhos)/rho_weight if rho_weight else None
    largest=min(range(k*p),key=lambda i:(-size[i],i));lo,lp=divmod(largest,p)
    hot={}
    order=sorted(range(k*p),key=lambda i:(-count[i],i))
    for portion in (.5,.9):
        selected=[];mass=0
        for i in order:
            selected.append(i);mass+=count[i]
            if mass>=portion*q:break
        hot[str(portion)]={'object_ids':selected,'object_count':len(selected),'probe_share':mass/q,
                           'final_bytes':sum(size[i] for i in selected),'bytes_over_memory':sum(size[i] for i in selected)/m}
    objects=[]
    for i in range(k*p):
        o,j=divmod(i,p)
        objects.append({'op':o,'partition':j,'final_size_bytes':size[i],'size_over_memory':size[i]/m,
                        'probe_count':count[i],'global_probe_share':count[i]/q,
                        'within_operator_probe_share':count[i]/probe[o] if probe[o] else None,
                        'probe_quarters':quarters[i],'potential_periodic_next_count':potential[i],
                        'not_actual_R80_next_samples':True})
    physical={method:result['runs'][method]['Total_IO_Time']+penalty*result['runs'][method]['Miss_Count'] for method in METHODS}
    assert penalty==result['penalty'] and all(result['runs'][method]['Hit_Count']+result['runs'][method]['Miss_Count']==q for method in METHODS)
    comparisons={}
    for method,ref in [('r80','paired100'),('r80','risk_pool100'),('risk_pool100','paired100')]:
        a,c=result['runs'][ref],result['runs'][method]
        comparisons[method+'_over_'+ref]={'physical_ratio':physical[method]/physical[ref],
          'physical_us_delta':physical[method]-physical[ref],'io_us_delta':c['Total_IO_Time']-a['Total_IO_Time'],
          'miss_count_delta':int(c['Miss_Count']-a['Miss_Count']),'miss_us_delta':penalty*(c['Miss_Count']-a['Miss_Count'])}
    features={'size_heat_spearman':all_assoc['spearman'],'log_size_heat_pearson':all_assoc['log1p_pearson'],
              'within_op_size_heat_spearman_weighted':within_rho,
              'total_bytes_over_memory':sum(size)/m,'max_object_over_memory':size[largest]/m,
              'weighted_within_op_cv2':weighted('cv2'),'weighted_within_op_top1':weighted('top1'),
              'hot90_bytes_over_memory':hot['0.9']['bytes_over_memory'],
              'largest_object_probe_share':count[largest]/q,'period':b,'operations':n,'partitions_total':k*p}
    return {'case':case['case'],'seed':case['seed'],'input_sha256':h.hexdigest(),'input_bytes':byte_count,
            'parameters':{'K':k,'P':p,'M':m,'W':w,'R':r,'penalty':penalty,'N':n,'B':b},
            'probe_count':q,'phase':{'metadata_overlap':case['phase_overlap'],'mixed_requests':mixed_requests,
                     'probes_while_any_build':probes_while_build,'first_probe_operation':first_probe,
                     'last_insert_operation':last_insert,'all_build_before_probe':last_insert<first_probe},
            'size_heat_global':all_assoc,'operators':operators,'objects':objects,
            'capacity':{'total_bytes':sum(size),'max_operator_bytes_over_memory':max(op['final_bytes'] for op in operators)/m,
                        'largest_object':objects[largest],'largest_object_within_op_frequency_rank':1+sum(count[lo*p+j]>count[largest] for j in range(p)),
                        'largest_object_tied_frequency_objects':sum(count[lo*p+j]==count[largest] for j in range(p)),
                        'zero_request_objects':sum(x==0 for x in count),'potential_periodic_next_total':sum(potential),'hot_prefixes':hot},
            'features':features,'physical_us':physical,'comparisons':comparisons,
            'reported_runs':{method:result['runs'][method] for method in METHODS},
            'internal_R80_share_or_p_observed':False}


def summarize(rows):
    def group(row):
        x=row['comparisons']['r80_over_paired100']['physical_ratio']
        return 'better' if x<1-1e-12 else 'worse' if x>1+1e-12 else 'equal'
    groups={g:[r for r in rows if group(r)==g] for g in ('better','equal','worse')}
    descriptions={}
    for feature in FEATURES:
        valid=[r for r in rows if r['features'][feature] is not None]
        x=[r['features'][feature] for r in valid]
        y=[math.log(r['comparisons']['r80_over_paired100']['physical_ratio']) for r in valid]
        descriptions[feature]={'valid_cases':len(valid),'spearman_vs_log_r80_paired_ratio':spearman(x,y),
              'range':[min(x),max(x)] if x else None,
              'group_medians':{g:statistics.median([r['features'][feature] for r in group_rows if r['features'][feature] is not None]) if any(r['features'][feature] is not None for r in group_rows) else None for g,group_rows in groups.items()}}
    comparisons={}
    for key in rows[0]['comparisons']:
        ratios=[r['comparisons'][key]['physical_ratio'] for r in rows];method,ref=key.split('_over_')
        comparisons[key]={'mean_of_case_ratios':statistics.fmean(ratios),'ratio_of_total_costs':sum(r['physical_us'][method] for r in rows)/sum(r['physical_us'][ref] for r in rows),
                          'min':min(ratios),'max':max(ratios),'better_equal_worse':[sum(x<1-1e-12 for x in ratios),sum(abs(x-1)<=1e-12 for x in ratios),sum(x>1+1e-12 for x in ratios)]}
    return {'cases':len(rows),'group_counts':{g:len(v) for g,v in groups.items()},'features':descriptions,
            'comparisons':comparisons,'internal_model_values_available':False,
            'group_case_names':{g:[r['case'] for r in v] for g,v in groups.items()},
            'all_objects':sum(len(r['objects']) for r in rows),'all_operators':sum(len(r['operators']) for r in rows),
            'all_build_before_probe':all(r['phase']['all_build_before_probe'] for r in rows),
            'zero_probe_operator_count':sum(op['probe_count']==0 for r in rows for op in r['operators'])}


def run():
    fp=HERE/'EXECUTION_FREEZE_V1.json';frozen=load(fp);fh=sha(fp);rows=[];started=time.time()
    results=load(ROUND/'RESULTS_V1.json');bycase={r['case']:r for r in results['records']}
    def status(state,**kw):save(HERE/'STATUS_V1.json',{'state':state,'completed':len(rows),'planned':24,'freeze_sha256':fh,'new_solver_runs':0,**kw},False)
    try:
        for case in frozen['cases']:
            status('waiting_shared_lock',case=case['case'])
            with experiment_lock():
                assert sha(fp)==fh
                for name,h in frozen['files'].items():assert sha(ROOT/name)==h,name
                status('reading_original_input_once',case=case['case'])
                row=analyze(case,bycase[case['case']]);save(HERE/(Path(case['case']).stem+'_V1.json'),row);rows.append(row)
            print('complete',len(rows),'/24',case['case'],flush=True)
        with experiment_lock():
            summary=summarize(rows);save(HERE/'RESULTS_V1.json',{'complete':True,'freeze_sha256':fh,'records':rows,'input_passes':24,
              'input_bytes':sum(r['input_bytes'] for r in rows),'operations':sum(r['parameters']['N'] for r in rows),
              'new_solver_runs':0,'new_compiles':0,'new_teacher_runs':0,'eval_dyna_input_reads':0,
              'diagnostic_wall_seconds':time.time()-started})
            save(HERE/'SUMMARY_V1.json',summary);status('complete')
    except BaseException as exc:
        status('failed',error_type=type(exc).__name__,error=str(exc));raise


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('prepare','run'));args=ap.parse_args()
    prepare() if args.stage=='prepare' else run()
