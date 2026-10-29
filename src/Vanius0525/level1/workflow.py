"""Serialize this task's CPU experiments; does not claim system-wide exclusivity."""
from contextlib import contextmanager
from pathlib import Path
import fcntl

@contextmanager
def experiment_lock():
    path=Path(__file__).resolve().parent/'build'/'experiment.lock'
    path.parent.mkdir(exist_ok=True)
    with path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)
