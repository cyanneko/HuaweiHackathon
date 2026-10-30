"""Hourly local regression and reminder to the explicitly bound current session.

Stop by creating build/round5-hourly/STOP. Old cancellation markers are untouched.
No source promotion or Git changes. Requires a live local host and Codex server.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from generate import generate
from round5.run_iteration import candidates
from benchmark import benchmark

STATE = ROOT / 'build/round5-hourly'


def write_status(**value):
    value.update(pid=os.getpid(), updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (STATE / 'status.json').write_text(json.dumps(value, indent=2) + '\n')


def main(once=False):
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deadline = time.time() + 3600
        while not (STATE / 'STOP').exists():
            write_status(state='waiting', next_check_utc=datetime.datetime.fromtimestamp(deadline, datetime.timezone.utc).isoformat())
            if not once and time.time() < deadline:
                time.sleep(min(15, deadline-time.time()))
                continue
            cycle = STATE / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            cycle.mkdir(exist_ok=False)
            write_status(state='running', cycle=cycle.name)
            outcome = {'auto_promoted': False}
            binding = STATE / 'binding.json'
            if binding.exists():
                try:
                    config = json.loads(binding.read_text())
                    proc = subprocess.run(['codex', 'queue', '--thread', config['thread'], '--message',
                        '每小时检查触发。继续已授权的华为Level1优化：先读round5/HANDOFF.md和TEAM_STRATEGY_REVIEW_20261030.md，'
                        '查看build/round5-hourly最新报告及现有进程，避免重复启动。处理本轮负结果，推进合法低频配置教师与纯算法；'
                        '历史测试均为开发回归，训练只用train，冻结后新家族一次性验证。更新HANDOFF。不得自动晋升未完成三成员审核的候选。'],
                        capture_output=True, text=True, timeout=45)
                    outcome['queue_returncode'] = proc.returncode
                except Exception as error:
                    outcome['queue_error_type'] = type(error).__name__
            # Never wait behind a long matrix: reminders still run every hour.
            with (ROOT / 'build/experiment.lock').open('a') as experiment:
                try:
                    fcntl.flock(experiment, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    outcome['regression'] = 'skipped_existing_experiment_holds_lock'
                else:
                    try:
                        seed = 600000000 + int(time.time()) % 100000000
                        generate(cycle / 'data', 8, seed, 4000)
                        benchmark(cycle / 'data', candidates(), 3, True, cycle / 'report.json')
                        outcome['regression'] = 'complete'
                    except Exception as error:
                        outcome.update(regression='failed', error=repr(error))
            with (cycle / 'outcome.json').open('x') as out:
                out.write(json.dumps(outcome, indent=2) + '\n')
            if once:
                write_status(state='once_complete', outcome=outcome, next_check_utc=None)
                return
            deadline = time.time() + 3600
        write_status(state='stopped', next_check_utc=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    main(parser.parse_args().once)
