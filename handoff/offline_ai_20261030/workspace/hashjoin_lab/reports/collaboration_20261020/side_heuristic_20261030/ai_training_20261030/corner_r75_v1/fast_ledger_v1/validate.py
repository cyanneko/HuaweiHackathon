"""Linux bounded exact-ledger comparison against every audited stage0 branch."""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,time

HERE=Path(__file__).resolve().parent
CORNER=HERE.parent
WS=CORNER.parent.parents[4]
WORKER=WS/'tmp/handler_support/worker_corner_r75'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def linux(p):
    p=str(p)
    return '/mnt/'+p[0].lower()+p[2:].replace('\\','/') if len(p)>2 and p[1]==':' else p


def validate_input(path):
    lines=path.read_text().splitlines();k,p,m,w,r,penalty=map(int,lines[0].split());n,b=map(int,lines[1].split())
    assert [int(line.split()[0]) for line in lines[2:2+k]]==list(range(k))
    operations=lines[2+k:];assert len(operations)==n
    phase=[False]*k
    for line in operations:
        t=line.split();op=int(t[1]);assert 0<=op<k
        if t[0]=='SWITCH':assert not phase[op];phase[op]=True
        elif t[0]=='INSERT':assert not phase[op]
        elif t[0]=='PROBE':assert phase[op]
        else:raise AssertionError('unknown operation')
    assert all(phase)
    return w,r,penalty


def main():
    assert os.name=='posix'
    protocol=json.loads((HERE/'protocol.json').read_text())
    assert sha(HERE/'adapter_ledger.cpp')==protocol['ledger_source_sha256']
    assert (WORKER/'artifact_audit.json').exists(),'wait for final Worker audit handoff'
    audit=json.loads((WORKER/'artifact_audit.json').read_text())
    assert 'pass' in audit.get('status','').lower(),audit.get('status')
    assert json.loads((WORKER/'cpu_released.json').read_text())['status']=='RELEASED'
    assert not (HERE/'runs').exists();runs=HERE/'runs';runs.mkdir()
    stage=Path('/var/tmp')/('handler_ledger_'+protocol['ledger_source_sha256'][:16]);stage.mkdir(exist_ok=False)
    start=time.perf_counter();deadline=start+90;records=[];error=None
    def run(cmd,stem,env=None):
        left=deadline-time.perf_counter()
        if left<=0:raise TimeoutError('90 second fast-ledger validation budget')
        result=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=left)
        (runs/(stem+'.stdout')).write_text(result.stdout);(runs/(stem+'.stderr')).write_text(result.stderr)
        assert result.returncode==0,(stem,result.stderr[-1500:])
        return result
    try:
        run(['g++','-std=c++14','-O2',str(HERE/'adapter_ledger.cpp'),'-o',str(stage/'adapter_ledger')],'compile')
        shutil.copy2(stage/'adapter_ledger',HERE/'adapter_ledger')
        cases={c['case_id']:c for c in json.loads((CORNER/'teacher_handoff.json').read_text())['cases']}
        coeff={}
        for name,c in cases.items():
            path=Path(c['input_path_linux']);assert sha(path)==c['input_sha256'];coeff[name]=validate_input(path)
        rows=json.loads((WORKER/'results.json').read_text());assert len(rows)==16
        for row in rows:
            assert row['complete_matrix'] and row['control_valid']
            anchor=row['anchor'];case=cases[anchor['case_id']];w,r,penalty=coeff[anchor['case_id']]
            for branch in row['branches']:
                assert branch['status']=='complete' and branch['override_count']==1
                stem=branch['anchor_id']+'_p'+str(branch['plan_index'])
                force=WORKER/'runs'/branch['anchor_id']/('p%02d'%branch['plan_index'])/'force.txt'
                assert sha(force)==branch['force_sha256']
                env={**os.environ,'HANDLER_FAST_LEDGER':'1','HANDLER_TRACE_PATH':str(runs/(stem+'.trace')),'HANDLER_FORCE_FILE':str(force)}
                result=run([str(stage/'adapter_ledger'),case['input_path_linux']],stem,env)
                end=[line.split() for line in result.stderr.splitlines() if line.startswith('HANDLER_END ')]
                ledger=[line.split() for line in result.stderr.splitlines() if line.startswith('HANDLER_LEDGER ')]
                assert len(end)==len(ledger)==1 and int(end[0][2])==1
                wb,rb,miss,all_probe=map(int,ledger[0][1:]);assert all_probe==1 and min(wb,rb,miss)>=0
                expected=branch['final_ledger'];g=wb*r+rb*w+miss*penalty*w*r
                assert (wb,rb,miss,g)==(expected['write_bytes'],expected['read_bytes'],expected['misses'],expected['G'])
                assert int(end[0][1])==branch['callbacks']
                values={k:float(v.strip()) for line in result.stdout.splitlines() if ':' in line for k,v in [line.split(':',1)]}
                assert values['Miss_Count']==miss and values['Hit_Count']==expected['hits']
                assert abs(values['Total_IO_Time']-(wb/w+rb/r))<=.011
                records.append({'anchor_id':branch['anchor_id'],'plan_index':branch['plan_index'],
                    'exact_write_read_miss_G_match':True,'callbacks_hits_match':True,'override_count':1,'all_probe_tail_precondition':True})
            print(json.dumps({'anchor_complete':anchor['anchor_id'],'checked':len(records),'seconds':time.perf_counter()-start}),flush=True)
        assert len(records)==89
        dump(HERE/'validation_report.json',{'status':'EXACT_NATIVE_LEDGER_STAGE0_PASS','primary_branches':records,
            'seconds':time.perf_counter()-start,'native_binary_sha256':sha(HERE/'adapter_ledger'),
            'source_sha256':sha(HERE/'adapter_ledger.cpp'),'worker_results_sha256':sha(WORKER/'results.json'),
            'worker_audit_sha256':sha(WORKER/'artifact_audit.json'),'input_legal_phase_precondition_checked':True,
            'scope':'89 previously fully replayed stage0 branches; no new training/data labels; all future fast labels must satisfy same preconditions',
            'formal_D':None})
    except BaseException as e:
        error=repr(e);dump(HERE/'failure.json',{'error':error,'completed':records});raise
    finally:
        dump(HERE/'cpu_released.json',{'status':'RELEASED','error':error,'active_child_processes':0,'seconds':time.perf_counter()-start})


if __name__=='__main__':main()
