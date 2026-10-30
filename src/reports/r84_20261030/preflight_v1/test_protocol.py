"""Synthetic-only checks, no solver/imported native framework execution."""
import copy,json
import scoring as s
def fixture(n,mode):
    cases=[dict(case_id=str(i),family='synthetic',original_split='eval',group=mode,stats=dict(operations=1,probe_count=1,penalty=3)) for i in range(n)]
    selection=dict(cases=cases,methods=[dict(name=k) for k in s.REFERENCES],mode=mode,scope='synthetic protocol test')
    rows=[]
    for c in cases:
        for name in s.REFERENCES:
            cost=10 if name=='Naive' else 8
            rows.append(dict(case_id=c['case_id'],method=name,valid=True,status='PASS',metrics=dict(Total_Score=cost,Total_IO_Time=cost-5,Total_Decision_Time=2,Miss_Count=1,Hit_Count=0)))
    return selection,rows
def tests():
    assert s.score(0,10)==s.score(10,0)==s.score(12,10)==0 and s.score(5,10)==5
    a,r=fixture(12,'dyna');v=s.summarize(a,r)
    assert v['complete'] and abs(v['groups']['all'][1]['average_score']-2)<1e-12
    assert v['per_case'][1]['physical']==6 and v['per_case'][1]['D']==2
    assert not s.summarize(a,r[:-1])['complete'] and s.summarize(a,r[:-1])['aggregate'] is None
    bad=copy.deepcopy(r);bad[-1]['valid']=False
    assert not s.summarize(a,bad)['complete']
    for bad in [r+[r[0]],r+[dict(r[0],case_id='unknown')]]:
        try:s.summarize(a,bad)
        except AssertionError:pass
        else:raise AssertionError('duplicate/unknown accepted')
    loss=copy.deepcopy(r);loss[1]['metrics'].update(Total_Score=12,Total_IO_Time=7)
    q=s.summarize(a,loss)['per_case'][1];assert q['score']==0 and q['raw_unclipped_points']<0 and q['negative_improvement_hidden']
    assert s.ratio_stats([(str(i),i) for i in range(1,7)],6)['p90']==6
    assert s.ratio_stats([(str(i),i) for i in range(1,13)],12)['p90']==11
    assert s.ratio_stats([('undefined',None)],1)['undefined']==1
    zero=copy.deepcopy(r)
    zero[0]['metrics'].update(Total_Score=0,Total_IO_Time=0,Total_Decision_Time=0,Miss_Count=0,Hit_Count=1)
    z=s.summarize(a,zero);assert z['groups']['all'][1]['undefined_naive_denominators']==1 and z['per_case'][1]['score']==0
    b,br=fixture(72,'final');fv=s.summarize(b,br)
    fv['groups']['all'][1]['average_score']=4
    merged=s.combine(v,fv);assert abs(merged['methods'][1]['equal_dataset_mean_score']-3)<1e-12
    assert not s.combine(s.summarize(a,r[:-1]),fv)['complete']
    done=dict(status='ALL_CELLS_TERMINAL',error=None,changed_artifacts=[],terminal=84,valid=84,planned=84)
    assert s.finalize(v,done)['complete']
    assert not s.finalize(v,dict(done,status='CONTROLLER_FAILURE',error='post-last-cell integrity failure'))['complete']
    return dict(status='PASS',synthetic_only=True,checks=['official zero-cost rules','D included; physical separate','dyna mode same-run Naive scoring','missing/invalid/duplicate/unknown cells','negative raw loss retained despite clipping','nearest-rank P90 n6/n12','undefined denominator reported','12/72 dataset means weighted equally; incomplete combined null','post-last-cell controller failure blocks complete aggregate'])
if __name__=='__main__':print(json.dumps(tests(),indent=2))
