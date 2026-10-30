"""Read-only hourly progress and current-session continuation. Never runs tests."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'build/round6/hourly'


def main():
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        config=json.loads((STATE/'binding.json').read_text())
        deadline=config['first_check_epoch']
        while not (STATE/'STOP').exists():
            status={'state':'waiting','pid':os.getpid(),
                'next_check_utc':datetime.datetime.fromtimestamp(deadline,datetime.timezone.utc).isoformat(),
                'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
            if time.time()>=deadline:
                prompt=('每小时检查：继续已授权的round6综合数据集优化。先读round6/HANDOFF.md，检查build/round6/status.json、'
                    'prepare.log与campaign.log及宿主锁，保留失败和partial。旧round4/5评测已明确停止，不得恢复。'
                    '标准为final_dataset2.0.0@33ab5af的50例，不再三成员平均。训练/阈值/提名只用train/dev；'
                    '不能逐小时刷test、不能据test反例调参后声称独立泛化；先核对TEST_ACCESS_LEDGER。'
                    '完成已有阶段的分析与必要修复，避免重复启动。更新HANDOFF；验证完整后提交并推本人分支。')
                try:
                    p=subprocess.run(['codex','queue','--thread',config['thread'],'--message',prompt],capture_output=True,text=True,timeout=45)
                    status.update(queue_returncode=p.returncode,state='queued' if p.returncode==0 else 'queue_failed')
                except Exception as error:
                    status.update(state='queue_failed',error_type=type(error).__name__)
                with (STATE/'checks.jsonl').open('a') as stream:
                    stream.write(json.dumps(status)+'\n')
                deadline=time.time()+3600
            (STATE/'status.json').write_text(json.dumps(status,indent=2)+'\n')
            time.sleep(15)
        (STATE/'status.json').write_text(json.dumps({'state':'stopped','next_check_utc':None})+'\n')


if __name__=='__main__':
    main()
