"""Hourly read-only health check and reminder queued to the authorized session.
Local daemon only; stop by creating build/hourly-resume/STOP.
"""
import datetime, fcntl, hashlib, json, os, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STATE=ROOT/'build/hourly-resume'
def main():
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'daemon.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        config=json.loads((STATE/'binding.json').read_text())
        deadline=time.time()+3600
        while not (STATE/'STOP').exists():
            status={'state':'waiting','pid':os.getpid(),'next_check_utc':datetime.datetime.fromtimestamp(deadline,datetime.timezone.utc).isoformat(),'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
            if time.time()>=deadline:
                status['candidate_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['MySpillScheduler.cpp','MySpillSchedulerAI.cpp']}
                try:
                    result=subprocess.run(['codex','queue','--thread',config['thread'],'--message',(ROOT/'HOURLY_RESUME_PROMPT.md').read_text()],capture_output=True,text=True,timeout=45)
                    status['queue_returncode']=result.returncode
                    status['state']='queued' if result.returncode==0 else 'queue_failed'
                except Exception as error:
                    status.update(state='queue_failed',error=type(error).__name__)
                with (STATE/'checks.jsonl').open('a') as out: out.write(json.dumps(status)+'\n')
                deadline=time.time()+3600
                status['next_check_utc']=datetime.datetime.fromtimestamp(deadline,datetime.timezone.utc).isoformat()
            (STATE/'status.json').write_text(json.dumps(status,indent=2)+'\n')
            time.sleep(15)
        (STATE/'status.json').write_text(json.dumps({'state':'stopped','pid':os.getpid(),'next_check_utc':None})+'\n')
if __name__=='__main__':main()
