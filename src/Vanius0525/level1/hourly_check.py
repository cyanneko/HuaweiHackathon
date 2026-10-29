"""Hourly regression + new-seed trial, then queue research in the existing session.
Only writes ignored build/hourly/. Never edits tracked candidate sources or Git.
Stop safely by creating build/hourly/STOP; the daemon finishes its current case.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from benchmark import benchmark
from build import ROOT
from generate import generate
from workflow import experiment_lock

HOME=ROOT/'build'/'hourly'

def status(value):
    HOME.mkdir(parents=True,exist_ok=True)
    value['updated_utc']=datetime.now(timezone.utc).isoformat();value['pid']=os.getpid()
    (HOME/'status.json').write_text(json.dumps(value,indent=2)+'\n')

def cycle(index,probes=4000):
    now=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=HOME/f'{now}-{index:04}';out.mkdir(parents=True,exist_ok=False)
    candidates={}
    for name,filename in [('pure','MySpillScheduler.cpp'),('ai','MySpillSchedulerAI.cpp')]:
        original=ROOT/filename
        if not original.exists():continue
        snap=out/filename;snap.write_bytes(original.read_bytes());candidates[name]=snap
    assert 'pure' in candidates
    # One reversible trial per cycle; generated artifact is never auto-promoted.
    coefficient=[8,64,256,1000][index%4]
    trial=out/'pure_trial.cpp';trial.write_text(candidates['pure'].read_text().replace('1.0 / part.data_size',f'{coefficient}.0 / part.data_size'))
    if trial.read_bytes()!=candidates['pure'].read_bytes():candidates['trial']=trial
    manifest=generate(out/'data',8,900000+index*8,probes)
    report=benchmark(out/'data',candidates,3,True,out/'report.json')
    summary={'cycle':index,'path':str(out.relative_to(ROOT)),'summary':report['summary'],
             'trial_penalty_surrogate':coefficient,'auto_promoted':False,
             'note':'Fresh small synthetic regression; no claim of hidden-test quality or autonomous AI reasoning.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary

def queue_research():
    binding=HOME/'session_binding.json'
    if not binding.exists():return {'queued':False,'reason':'no validated local session binding'}
    config=json.loads(binding.read_text())
    prompt=(ROOT/config['prompt_file']).read_text()
    p=subprocess.run(['codex','queue','--thread',config['thread'],'--message',prompt],capture_output=True,text=True,timeout=30)
    # Session and queue IDs remain local and are never included in public summaries.
    outcome={'queued':p.returncode==0,'returncode':p.returncode,'utc':datetime.now(timezone.utc).isoformat()}
    if p.returncode:outcome['error']=(p.stderr or p.stdout)[-1000:].replace(config['thread'],'<current-session>')
    (HOME/'last_queue.json').write_text(json.dumps(outcome,indent=2)+'\n')
    return outcome

def main(first,interval,once=False):
    HOME.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (HOME/'daemon.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('An hourly checker already owns this directory')
        (HOME/'pid').write_text(str(os.getpid())+'\n')
        deadline=first if first is not None else time.time()+interval
        existing=[]
        for summary in HOME.glob('*/summary.json'):
            try:existing.append(json.loads(summary.read_text())['cycle'])
            except (ValueError,KeyError):pass
        index=1+max(existing) if existing else 0
        while not (HOME/'STOP').exists():
            status({'state':'waiting','next_check_utc':datetime.fromtimestamp(deadline,timezone.utc).isoformat(),'cycle':index,
                    'scope':'local regression, parameter trial, and research queued to the existing session via codex queue'})
            if not once and time.time()<deadline:
                time.sleep(min(30,max(0,deadline-time.time())));continue
            try:
                with experiment_lock():
                    status({'state':'running','cycle':index});summary=cycle(index)
                queue=queue_research()
                status({'state':'completed','cycle':index,'last_summary':summary,'research_queue':queue})
            except Exception as error:
                try:queued=queue_research()
                except Exception as queue_error:queued={'queued':False,'error':repr(queue_error)}
                status({'state':'failed','cycle':index,'error':repr(error),'research_queue':queued})
            index+=1
            if once:return
            deadline+=interval
            if deadline<time.time():deadline=time.time()+interval
        status({'state':'stopped','cycle':index})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--first-at',help='UTC ISO timestamp');p.add_argument('--interval',type=int,default=3600);p.add_argument('--once',action='store_true')
    a=p.parse_args();first=datetime.fromisoformat(a.first_at).timestamp() if a.first_at else None
    main(first,a.interval,a.once)
