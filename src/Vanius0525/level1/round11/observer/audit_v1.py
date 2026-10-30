"""Independent numerical/state/set checks of the at-most-three copy snapshots."""
from decimal import Decimal
import json
import math
from pathlib import Path

FIELDS=('Total_IO_Time','Total_Decision_Time','Total_Score','Hit_Count','Miss_Count')


def parse_output(path):
    lines=path.read_text().strip().splitlines();assert len(lines)==5
    raw=dict(line.split(': ',1) for line in lines);assert set(raw)==set(FIELDS)
    d={k:Decimal(v) for k,v in raw.items()};assert all(v.is_finite() and v>=0 for v in d.values())
    for k in ('Hit_Count','Miss_Count'):assert d[k]==d[k].to_integral_value()
    return d


def pending(line):
    a=line.split()
    if not a:return {'type':'','op_id':-1,'key':0,'tuple_size':0}
    return {'type':a[0],'op_id':int(a[1]),'key':int(a[2]) if len(a)>2 else 0,
            'tuple_size':int(a[3]) if len(a)>3 else 0}


def audit(input_path,stdout,stderr,reference_stdout):
    states=[];end=None
    for line in stderr.read_text().splitlines():
        if line.startswith('OBS_STATE '):
            assert end is None;states.append(json.loads(line[10:]))
        elif line.startswith('OBS_END '):assert end is None;end=json.loads(line[8:])
        else:raise AssertionError(('Unexpected observer stderr',line[:150]))
    assert end is not None and end['snapshots']==len(states)<=3
    # Read only the original prefix needed to locate captured q; no hidden input enters C++.
    byq={r['q']:r for r in states};assert len(byq)==len(states)
    with input_path.open() as f:
        k,p,m,w,r,penalty=map(int,f.readline().split());n,b=map(int,f.readline().split())
        heads=[tuple(map(int,f.readline().split())) for _ in range(k)]
        assert [x[0] for x in heads]==list(range(k));sizes=[[0]*p for _ in range(k)];phase=[False]*k
        q=0;current=f.readline();maximum=max(byq,default=0);locations={}
        for index in range(n):
            assert current;following=f.readline() if index+1<n else ''
            op=pending(current);nxt=pending(following);o=op['op_id']
            if op['type']=='SWITCH':phase[o]=True
            elif op['type']=='INSERT':sizes[o][op['key']%p]+=op['tuple_size']
            else:
                assert op['type']=='PROBE';q+=1
                if q in byq:
                    row=byq[q];assert row['tag']=='M' and row['target_op']==o and row['target_partition']==op['key']%p
                    assert row['state']['next_op']==nxt and all(phase)
                    for oo in range(k):
                        assert [pa['data_size'] for pa in row['state']['operators'][oo]['partitions']]==sizes[oo]
                    locations[q]={'raw_operation_index_0based':index,'current_operation':op,'next_operation':nxt}
                if q>=maximum:break
            current=following
    actual=parse_output(stdout);reference=parse_output(reference_stdout)
    for key in ('Total_IO_Time','Hit_Count','Miss_Count'):assert actual[key]==reference[key],(key,actual[key],reference[key])
    assert actual['Hit_Count']+actual['Miss_Count']==sum(x[2] for x in heads)
    residual=abs(actual['Total_Score']-actual['Total_IO_Time']-penalty*actual['Miss_Count']-actual['Total_Decision_Time'])
    assert residual<=Decimal('.02')
    numeric={'comparisons':0,'max_absolute_error':0.,'max_scaled_error':0.}
    def close(a,c):
        assert math.isfinite(a) and math.isfinite(c)
        diff=abs(a-c);numeric['comparisons']+=1;numeric['max_absolute_error']=max(numeric['max_absolute_error'],diff)
        numeric['max_scaled_error']=max(numeric['max_scaled_error'],diff/max(1.,abs(a),abs(c)))
        assert math.isclose(a,c,rel_tol=2e-9,abs_tol=2e-8),(a,c,diff)
    consumed=[];checks=[];previous_callback=0
    for row in states:
        s=row['state'];q=row['q'];assert q==s['hit_count']+s['miss_count']
        assert row['callback']>previous_callback;previous_callback=row['callback']
        thresholds=[x for x in (256,1024,4096) if x not in consumed and x<=q]
        assert row['thresholds']==thresholds and thresholds;consumed+=thresholds
        assert row['hier_copy_equals_actual_spills'] is True
        assert s['num_partitions']==p and len(s['operators'])==k and s['memory_limit']==m
        assert s['write_bandwidth']==w and s['read_bandwidth']==r
        assert row['probability_clock']==max(q,row['next_sample_q']) and row['next_sample_q']<=q+1
        objects=row['objects'];groups=row['groups'];assert len(objects)==k*p and len(groups)==k
        assert s['memory_used']==sum(obj['size'] for obj in objects if obj['resident'])
        target=(row['target_op'],row['target_partition']);required=row['required_bytes'];need=required-(m-s['memory_used']);assert need>0
        assert all(o['phase']=='PROBE' for o in s['operators'])
        assert not s['operators'][target[0]]['partitions'][target[1]]['in_memory']
        assert required==s['operators'][target[0]]['partitions'][target[1]]['data_size']
        total=row['total_mass'];denom=row['probability_denom'];prior=row['probability_prior_per_object'];close(prior,64/(k*p));close(denom,total+64)
        close(total,sum(g['mass'] for g in groups));close(row['total_weight2'],sum(g['weight2'] for g in groups))
        for o,g in enumerate(groups):
            assert g['op']==o and g['last']==row['probability_clock']
            subset=objects[o*p:(o+1)*p];mass=g['mass'];weight=g['weight2'];neff=mass*mass/weight if weight>0 else 0.
            close(g['n_eff'],neff);close(mass,sum(x['mass'] for x in subset));close(g['squares'],sum(x['mass']**2 for x in subset))
            alpha=.75;heterogeneity=0.
            if p>1 and mass>8 and weight>1e-200 and neff>8:
                v=max(0.,(p*g['squares']/(mass*mass)-1-(p-1)/neff)/(1-1/neff));strength=v*(mass-8)/(mass+p)
                alpha=.75/(1+strength);heterogeneity=strength/(1+strength)
            close(g['share'],alpha);close(g['heterogeneity'],heterogeneity);assert 0<=g['share']<=.75
            close(sum(x['flat_p'] for x in subset),sum(x['hier_p'] for x in subset))
        for i,obj in enumerate(objects):
            o,pa=divmod(i,p);part=s['operators'][o]['partitions'][pa];g=groups[o]
            assert (obj['id'],obj['op'],obj['partition'])==(i,o,pa) and obj['size']==part['data_size'] and obj['resident']==part['in_memory']
            eligible=obj['resident'] and obj['size']>0 and (o,pa)!=target
            protected=s['next_op']['type']=='PROBE' and s['next_op']['op_id']==o and s['next_op']['key']%p==pa
            assert obj['eligible']==eligible and obj['next_protected']==protected
            assert obj['frequency_branch']==(eligible and not row['scan'] and not row['cycle'])
            close(obj['flat_p'],(obj['mass']+prior)/denom)
            close(obj['hier_p'],((1-g['share'])*obj['mass']+g['share']*g['mass']/p+prior)/denom)
            assert 0<=obj['flat_p']<=1 and 0<=obj['hier_p']<=1
            if k==1:close(obj['hier_p'],(1-g['share'])*obj['flat_p']+g['share']/p)
        close(sum(x['flat_p'] for x in objects),1.);close(sum(x['hier_p'] for x in objects),1.)
        # Probability rank cannot reverse within a shared operator under the same affine transform.
        for o in range(k):
            ordered=sorted(objects[o*p:(o+1)*p],key=lambda x:x['flat_p'])
            assert all(a['hier_p']<=c['hier_p']+2e-12 for a,c in zip(ordered,ordered[1:]))
        actual_spills=[a for a in row['actual_actions'] if a[0]=='S'];assert actual_spills==row['hier_spills']
        assert row['actual_actions']==actual_spills+[['L',*target]]
        for label,acts in [('hier_set',row['hier_spills']),('flat_set',row['flat_spills'])]:
            assert len({(a[1],a[2]) for a in acts})==len(acts)
            ids=[]
            for t,o,pa in acts:assert t=='S' and objects[o*p+pa]['eligible'];ids.append(o*p+pa)
            freed=sum(objects[i]['size'] for i in ids);assert freed>=need and s['memory_used']-freed+required<=m
            objective=row['cross_objectives'][label];assert objective['spill_bytes']==freed and objective['victim_count']==len(acts)
            assert objective['released_excess_bytes']==freed-need
            assert objective['ordinary_frequency_objective_valid']==all(objects[i]['frequency_branch'] for i in ids)
            write=freed/w;ff=hh=protect=0.
            for i in ids:
                obj=objects[i];c=obj['size']/r+obj['size']/w+100
                ff+=64*obj['flat_p']*c;hh+=64*obj['hier_p']*c
                if obj['next_protected']:protect+=1e12*obj['size']
            for name,expected in [('actual_current_write_us',write),('flat_future_proxy_us',ff),('hier_future_proxy_us',hh),
                ('next_protection_term',protect),('flat_subset_objective',ff+.25*write+protect),('hier_subset_objective',hh+.25*write+protect)]:close(objective[name],expected)
        hier=row['cross_objectives']['hier_set'];flat=row['cross_objectives']['flat_set']
        checks.append({'q':q,'thresholds':thresholds,'callback':row['callback'],**locations[q],
            'hier_copy_equals_actual':True,'flat_vs_hier_spill_sequence_different':row['flat_spills']!=row['hier_spills'],
            'flat_vs_hier_spill_set_different':{tuple(a) for a in row['flat_spills']}!={tuple(a) for a in row['hier_spills']},
            'flat_minus_hier_spill_bytes':flat['spill_bytes']-hier['spill_bytes'],
            'flat_minus_hier_current_write_us':flat['actual_current_write_us']-hier['actual_current_write_us'],
            'flat_minus_hier_flat_objective':flat['flat_subset_objective']-hier['flat_subset_objective'],
            'flat_minus_hier_hier_objective':flat['hier_subset_objective']-hier['hier_subset_objective'],
            'all_spills_ordinary_frequency':flat['ordinary_frequency_objective_valid'] and hier['ordinary_frequency_objective_valid'],
            'scan':row['scan'],'cycle':row['cycle'],'group_share':[g['share'] for g in groups],
            'group_mass':[g['mass'] for g in groups],'group_n_eff':[g['n_eff'] for g in groups]})
    assert len(consumed)==end['thresholds_consumed'] and previous_callback<=end['callbacks']
    return {'passed':True,'snapshots':len(states),'thresholds_consumed':consumed,'reference_io_hit_miss_exact':True,
            'physical_output':{k:str(actual[k]) for k in ('Total_IO_Time','Hit_Count','Miss_Count')},
            'printed_cost_formula_residual_us':str(residual),'numeric':numeric,'checks':checks,'states':states,
            'full_action_trace_available':False,'new_performance_result':False,'global_trajectory_benefit_claimed':False}
