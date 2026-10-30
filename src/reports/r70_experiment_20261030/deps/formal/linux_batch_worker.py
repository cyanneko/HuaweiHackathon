#!/usr/bin/env python3
"""Bounded Linux matrix worker. SOURCE PREPARATION: review/fixtures before use.

Usage: python3 -B linux_batch_worker.py MANIFEST.json  (or '-' for stdin).
Output is output_root/batch_id/. Each cell has immutable attempt_NNNN evidence
and an atomic latest result.json. No solver metrics are guessed by this worker.

Required manifest fields: batch_id, output_root, jobs, private_timeout,
private_gnu_time (alias privategnu_time), allowed_binary_paths. A job contains
cell_id, method_id, case_id, exe, input and cache_key. cache_key may contain the
four identity hashes directly, or be an opaque key plus job.identity containing
input_sha256/binary_sha256/framework_sha256/params_sha256. Framework/parameter
hashes are parent attestations; input/binary hashes are independently verified.

One batch uses a cumulative admission clock, including resumes: work <=240 s,
declared total300 s and cleanup reserve45 s; a new cell requires >=65 s of work
time remaining. This script does NOT itself impose a hard total bound on hashing,
fsync or cleanup. The parent must enforce its mature external300 s deadline and
then take over ownership-registry cleanup for up to45 s. A case
gets the complete60 s GNU timeout and outer wait63 s. A later invocation of the
same batch cannot reset its original clock. Confirmed measurement terminal
statuses are distinct from mere attempt-cleanup completion. Unknown, launch-error
and cancelled attempts remain pending; genuine terminal cells are not silently
rerun when all four identities match.

Each Popen starts its own session/PGID. SIGKILL cannot run Python cleanup; the
parent MUST recover ownership.json registries if it force-kills this worker.
The worker never group-kills an ambiguous process or reports ambiguous as zero.
"""
from __future__ import annotations

import contextlib
import datetime
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


IDENTITY_KEYS = ("input_sha256", "binary_sha256", "framework_sha256", "params_sha256")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
CASE_SECONDS = 60.0
OUTER_WAIT_SECONDS = 63.0
SIGNAL_RECEIVED = None
FILE_HASH_CACHE = {}
IN_CLEANUP = False
IN_LAUNCH_REGISTRATION = False
MEASUREMENT_TERMINAL_STATUSES = frozenset({
    "EXITED", "FAILED_EXIT", "FAILED_EXIT_TIMEOUT_STATUS", "TIMEOUT", "OUTER_TIMEOUT",
    "EXITED_WITH_OWNED_RESIDUAL_CLEANED",
})


class WorkerSignal(BaseException):
    pass


class AmbiguousOwnership(RuntimeError):
    pass


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified_file_hash(path):
    path = Path(path).resolve()
    stat = path.stat()
    key = (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if key not in FILE_HASH_CACHE:
        FILE_HASH_CACHE[key] = sha_file(path)
    return FILE_HASH_CACHE[key]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    with temp.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def journal(path, value):
    with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_stat(pid):
    raw = (Path("/proc") / str(pid) / "stat").read_text()
    # comm may contain spaces or ')' characters. Remaining fields start at3.
    fields = raw[raw.rfind(")") + 2:].split()
    return dict(pid=int(pid), state=fields[0], ppid=int(fields[1]),
                pgid=int(fields[2]), session=int(fields[3]), start_ticks=int(fields[19]))


def process_info(pid):
    info = read_stat(pid)
    proc = Path("/proc") / str(pid)
    info.update(exe=os.path.realpath(os.readlink(proc / "exe")),
                cwd=os.path.realpath(os.readlink(proc / "cwd")))
    return info


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def boot_ticks():
    ticks = os.sysconf("SC_CLK_TCK")
    clock = getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC)
    return math.floor(time.clock_gettime(clock) * ticks)


def scan_group(owner, allowed):
    """Read-only PGID scan; unknown/mismatched live members are ambiguous."""
    live, ambiguous, zombies = [], [], []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            stat = read_stat(int(proc.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, OSError, ValueError, IndexError) as exc:
            # Own private children have the worker's uid. A denied stat prevents
            # a fully verified group-empty claim, rather than becoming zero.
            ambiguous.append(dict(pid=int(proc.name), reason="stat_permission", error=str(exc)))
            continue
        if stat["state"] in ("Z", "X", "x"):
            if stat["pgid"] == owner["pgid"]:
                zombies.append(stat)
            continue
        if stat["pgid"] != owner["pgid"]:
            # A child that calls setsid/setpgid is no longer safely signalable
            # through this owner record. Detect same-uid, same-attempt births
            # outside the tracked group and fail closed instead of claiming0.
            try:
                uid_line = next(line for line in (proc / "status").read_text().splitlines() if line.startswith("Uid:"))
                if int(uid_line.split()[1]) != os.getuid() or stat["start_ticks"] < owner["leader_start_ticks"]:
                    continue
                cwd = os.path.realpath(os.readlink(proc / "cwd"))
                if cwd == owner["cwd"]:
                    ambiguous.append(dict(**stat, cwd=cwd, reason="matching_attempt_birth_outside_owned_group"))
            except (FileNotFoundError, ProcessLookupError):
                pass
            except (PermissionError, OSError, ValueError, StopIteration) as exc:
                ambiguous.append(dict(**stat, reason="escape_check_unreadable", error=repr(exc)))
            continue
        try:
            info = process_info(stat["pid"])
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, OSError) as exc:
            ambiguous.append(dict(**stat, reason="identity_unreadable", error=str(exc)))
            continue
        reasons = []
        if info["pgid"] != owner["pgid"] or info["session"] != owner["session"]:
            reasons.append("group_or_session_changed")
        if info["start_ticks"] < owner["leader_start_ticks"]:
            reasons.append("birth_precedes_owned_leader")
        if info["cwd"] != owner["cwd"]:
            reasons.append("cwd_not_owned_attempt")
        if info["exe"] not in allowed:
            reasons.append("executable_not_private_allowlist")
        if info["pid"] == owner["pid"] and info["start_ticks"] != owner["leader_start_ticks"]:
            reasons.append("leader_pid_reused")
        if reasons:
            ambiguous.append(dict(**info, reason=reasons))
        else:
            live.append(info)
    return dict(live=live, ambiguous=ambiguous, zombies=zombies)


def signal_exact(info, owner, allowed, sig):
    """Use pidfds to avoid signaling a different process after PID reuse."""
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise AmbiguousOwnership("pidfd signaling unavailable; refusing PID-race fallback")
    descriptor = None
    try:
        descriptor = os.pidfd_open(info["pid"], 0)
        current = process_info(info["pid"])
        keys = ("pid", "pgid", "session", "start_ticks", "cwd", "exe")
        if any(current[key] != info[key] for key in keys):
            raise AmbiguousOwnership("process identity changed before signal")
        if (current["pgid"] != owner["pgid"] or current["session"] != owner["session"]
                or current["cwd"] != owner["cwd"] or current["exe"] not in allowed
                or current["start_ticks"] < owner["leader_start_ticks"]):
            raise AmbiguousOwnership("process no longer matches owned group")
        signal.pidfd_send_signal(descriptor, sig, None, 0)
        return dict(pid=info["pid"], start_ticks=info["start_ticks"], signal=int(sig), sent=True)
    except (FileNotFoundError, ProcessLookupError):
        return dict(pid=info["pid"], signal=int(sig), sent=False, reason="already_exited")
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _cleanup_group_impl(owner, allowed, force=False):
    """No blanket killpg: only individually verified private members may die."""
    audit = dict(owner=owner, checked_at=utc_now(), initial=None, signalled=[], remaining=None,
                 ambiguous=[], verified=False, active_owned_processes=None)
    if owner["boot_id"] != boot_id():
        audit["ambiguous"] = [dict(reason="boot_identity_changed")]
        return audit
    try:
        first = scan_group(owner, allowed)
    except BaseException as exc:
        audit["ambiguous"] = [dict(reason="group_scan_failed", error=repr(exc))]
        return audit
    audit["initial"] = first
    if first["ambiguous"]:
        audit["ambiguous"] = first["ambiguous"]
        return audit
    # Even after normal leader exit, surviving private members are cleanup work.
    if first["live"]:
        try:
            for info in first["live"]:
                audit["signalled"].append(signal_exact(info, owner, allowed, signal.SIGTERM))
            deadline = time.monotonic() + 0.25
            while time.monotonic() < deadline:
                state = scan_group(owner, allowed)
                if state["ambiguous"] or not state["live"]:
                    break
                time.sleep(0.01)
            state = scan_group(owner, allowed)
            if state["ambiguous"]:
                audit["ambiguous"] = state["ambiguous"]
                return audit
            for info in state["live"]:
                audit["signalled"].append(signal_exact(info, owner, allowed, signal.SIGKILL))
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                state = scan_group(owner, allowed)
                if state["ambiguous"] or not state["live"]:
                    break
                time.sleep(0.01)
        except (AmbiguousOwnership, PermissionError, OSError) as exc:
            audit["ambiguous"] = [dict(reason="signal_not_proven_safe", error=repr(exc))]
            return audit
    try:
        final = scan_group(owner, allowed)
    except BaseException as exc:
        audit["ambiguous"] = [dict(reason="final_group_scan_failed", error=repr(exc))]
        return audit
    audit["remaining"] = final
    audit["ambiguous"] = final["ambiguous"]
    audit["verified"] = not final["live"] and not final["ambiguous"]
    if audit["verified"]:
        audit["active_owned_processes"] = 0
    else:
        audit["active_owned_processes"] = len(final["live"]) if not final["ambiguous"] else None
    return audit


def cleanup_group(owner, allowed, force=False):
    global IN_CLEANUP
    prior = IN_CLEANUP
    IN_CLEANUP = True
    try:
        return _cleanup_group_impl(owner, allowed, force=force)
    finally:
        IN_CLEANUP = prior


def job_identity(job, manifest):
    cache = job.get("cache_key")
    identity = cache if isinstance(cache, dict) else job.get("identity", {})
    identity = {key: identity.get(key, job.get(key, manifest.get(key))) for key in IDENTITY_KEYS}
    if cache is None or not all(isinstance(v, str) and SHA256.fullmatch(v) for v in identity.values()):
        raise ValueError("cache_key plus all four input/binary/framework/params SHA256 identities required")
    for key, path in (("input_sha256", job["input"]), ("binary_sha256", job["exe"])):
        actual = verified_file_hash(path)
        if actual != identity[key]:
            raise ValueError("identity mismatch: " + key + " for " + str(path))
    return dict(identity=identity, cache_key=cache,
                cache_digest=hashlib.sha256(canonical(dict(cache_key=cache, identity=identity)).encode()).hexdigest())


def matches_completed(result, job, identity):
    return (measurement_complete(result)
            and all(result.get(key) == job.get(key) for key in ("cell_id", "method_id", "case_id"))
            and result.get("identity") == identity["identity"]
            and result.get("cache_key") == identity["cache_key"]
            and result.get("cache_digest") == identity["cache_digest"])


def measurement_complete(result):
    """A safe cleanup alone is not a completed solver measurement."""
    return (result.get("status") in MEASUREMENT_TERMINAL_STATUSES
            and result.get("popen_returned") is True
            and result.get("cleanup", {}).get("verified") is True)


def set_completion_fields(result):
    result["attempt_cleanup_complete"] = result.get("cleanup", {}).get("verified") is True
    result["measurement_complete"] = measurement_complete(result)
    # Keep the legacy field, with its corrected measurement-level meaning.
    result["complete"] = result["measurement_complete"]
    return result


def find_completed(cell_dir, job, identity):
    """A later unknown attempt cannot erase an earlier true terminal cache."""
    candidates = [cell_dir / "result.json"]
    for attempt in sorted(cell_dir.glob("attempt_*"), reverse=True):
        candidates.extend((attempt / "recovery_result.json", attempt / "result.json"))
    for path in candidates:
        if path.exists():
            result = read_json(path)
            if matches_completed(result, job, identity):
                return path, result
    return None


def recovery_base(attempt, previous):
    if previous is not None:
        return dict(previous)
    for name in ("started.json", "spawn_returned.json", "intent.json"):
        if (attempt / name).exists():
            return read_json(attempt / name)
    return {}


def persist_recovery(cell_dir, attempt, result):
    set_completion_fields(result)
    atomic_json(attempt / "recovery_result.json", result)
    latest = cell_dir / "result.json"
    current = read_json(latest) if latest.exists() else None
    if current is None or current.get("attempt") == str(attempt) or not measurement_complete(current):
        atomic_json(latest, result)


def classify_exit(result, timeout, stderr_path):
    code = result["returncode"]
    if code == 0:
        result["status"] = "EXITED"
        return
    result["status"] = "FAILED_EXIT"
    if code not in (124, 137):
        return
    elapsed = result["process_exit_elapsed_seconds"]
    # GNU timeout --verbose is emitted in LC_ALL=C. Early124/137 is the
    # program's failed exit, never sufficient evidence of a60 s timeout.
    marker = os.fsencode(Path(timeout).name) + b": sending signal "
    stderr = Path(stderr_path).read_bytes()
    message_seen = any((line.startswith(marker) or line.startswith(os.fsencode(str(timeout)) + b": sending signal "))
                       and b" to command " in line for line in stderr.splitlines())
    evidence = dict(returncode=code, elapsed_seconds=elapsed, configured_seconds=CASE_SECONDS,
                    gnu_timeout_verbose=True, verbose_signal_message=message_seen,
                    elapsed_reached_deadline=elapsed >= CASE_SECONDS)
    result["timeout_evidence"] = evidence
    if elapsed < CASE_SECONDS:
        evidence["classification"] = "early_timeout_like_exit_code_is_failed_exit"
    elif message_seen:
        result["status"] = "TIMEOUT"
        evidence["classification"] = "verbose_gnu_signal_and_elapsed_deadline"
    else:
        result["status"] = "FAILED_EXIT_TIMEOUT_STATUS"
        result["timeout_status_unknown"] = True
        evidence["classification"] = "late_timeout_like_code_without_corroborating_signal_message"


def stop_requested(batch_dir, root):
    return SIGNAL_RECEIVED is not None or (batch_dir / "STOP_REQUESTED").exists() or (root / "STOP_REQUESTED").exists()


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or not SAFE_ID.fullmatch(str(manifest.get("batch_id", ""))):
        raise ValueError("safe batch_id required")
    root = Path(manifest["output_root"])
    if not root.is_absolute():
        raise ValueError("absolute Linux output_root required")
    root = root.resolve()
    timeout_raw = manifest["private_timeout"]
    time_raw = manifest.get("private_gnu_time", manifest.get("privategnu_time"))
    if not isinstance(time_raw, str) or not Path(timeout_raw).is_absolute() or not Path(time_raw).is_absolute():
        raise ValueError("absolute private utility paths required")
    timeout = Path(timeout_raw).resolve()
    gnu_time = Path(time_raw).resolve()
    raw_allowed = manifest.get("allowed_binary_paths", manifest.get("allowed_binaries"))
    if not isinstance(raw_allowed, list) or not raw_allowed:
        raise ValueError("nonempty private executable allowlist required")
    if not all(isinstance(p, str) and Path(p).is_absolute() for p in raw_allowed):
        raise ValueError("private executable allowlist paths must be absolute")
    allowed = {str(Path(p).resolve()) for p in raw_allowed}
    if str(timeout) not in allowed or str(gnu_time) not in allowed:
        raise ValueError("both private utilities must be allowlisted")
    if float(manifest.get("case_timeout", manifest.get("case_timeout_seconds", CASE_SECONDS))) != CASE_SECONDS:
        raise ValueError("latest matrix contract requires a full60 second case timeout")
    work = float(manifest.get("batch_work_seconds", 240))
    total = float(manifest.get("batch_total_seconds", 300))
    reserve = float(manifest.get("cleanup_reserve_seconds", 45))
    if not all(math.isfinite(x) for x in (work, total, reserve)) or not (0 < work <= 240 and total <= 300 and reserve >= 45 and work <= total - reserve):
        raise ValueError("batch work<=240,total<=300,cleanup reserve>=45 required")
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("jobs list required")
    seen = set()
    resolved_job_executables = {}
    for job in jobs:
        if not isinstance(job, dict) or not SAFE_ID.fullmatch(str(job.get("cell_id", ""))):
            raise ValueError("safe unique cell_id required")
        if job["cell_id"] in seen:
            raise ValueError("duplicate cell_id")
        seen.add(job["cell_id"])
        if "method_id" not in job or "case_id" not in job:
            raise ValueError("method_id and case_id required")
        for name in ("exe", "input"):
            if not Path(job[name]).is_absolute():
                raise ValueError("absolute job paths required")
        if job["exe"] not in resolved_job_executables:
            resolved_job_executables[job["exe"]] = str(Path(job["exe"]).resolve())
        if resolved_job_executables[job["exe"]] not in allowed:
            raise ValueError("job executable not in private allowlist")
    cases = manifest.get("cases", [])
    if isinstance(cases, dict):
        cases = [dict(value, case_id=key) for key, value in cases.items()]
    case_map = {}
    for case in cases:
        if not isinstance(case, dict) or "case_id" not in case or case["case_id"] in case_map:
            raise ValueError("unique case metadata identities required")
        case_map[case["case_id"]] = case
    for job in jobs:
        case = case_map.get(job["case_id"], {})
        declared_input = case.get("input", case.get("path"))
        if declared_input is not None and Path(declared_input).resolve() != Path(job["input"]).resolve():
            raise ValueError("job/case metadata input path mismatch")
    return root, timeout, gnu_time, allowed, work, total, reserve, case_map


@contextlib.contextmanager
def timing_locks(root, batch_dir):
    """Hold kernel locks for the worker lifetime; never unlink lock inodes."""
    root.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)
    owner = dict(pid=os.getpid(), start_ticks=read_stat(os.getpid())["start_ticks"],
                 boot_id=boot_id(), at=utc_now(), batch_id=batch_dir.name)
    opened, records = [], []
    try:
        # Always acquire global before per-batch, so two batch ids cannot time
        # concurrently. Stale file contents grant no authority to unlink/steal.
        for scope, path in (("matrix", root / "matrix_timing.lock"),
                            ("batch", batch_dir / "worker.lock")):
            fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0), 0o600)
            os.set_inheritable(fd, False)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                os.close(fd)
                if exc.errno in (errno.EAGAIN, errno.EACCES):
                    raise RuntimeError(scope + " timing lock already held") from exc
                raise
            opened.append(fd)
            record = dict(owner, scope=scope, path=str(path))
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            payload = (canonical(record) + "\n").encode("utf-8")
            with os.fdopen(os.dup(fd), "wb", closefd=True) as stream:
                stream.write(payload);stream.flush();os.fsync(stream.fileno())
            records.append(record)
        yield records
    finally:
        for fd in reversed(opened):
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


def check_unfinished(cell_dir, allowed):
    """Recover only documented owned attempts; an unknown live cwd is a stop."""
    for attempt in sorted(cell_dir.glob("attempt_*")):
        if not attempt.is_dir():
            continue
        terminal_path = attempt / "recovery_result.json" if (attempt / "recovery_result.json").exists() else attempt / "result.json"
        previous = read_json(terminal_path) if terminal_path.exists() else None
        if previous is not None and previous.get("cleanup", {}).get("verified") is True:
            # Safe cleanup ends this attempt; an unknown measurement still may
            # need a new attempt, but must not trigger repeated cleanup itself.
            continue
        owner_path = attempt / "ownership.json"
        if owner_path.exists():
            owner = read_json(owner_path)
            if (owner.get("cwd") != str(attempt.resolve()) or owner.get("cell_id") != cell_dir.name
                    or owner.get("batch_id") != cell_dir.parent.parent.name):
                raise AmbiguousOwnership("ownership registry does not belong to this attempt directory")
            audit = cleanup_group(owner, allowed, force=True)
            atomic_json(attempt / "recovery_cleanup.json", audit)
            if not audit["verified"]:
                raise AmbiguousOwnership("unfinished attempt has unverified cleanup: " + str(attempt))
            result = recovery_base(attempt, previous)
            result.update(cleanup=audit, recovered_at=utc_now())
            if result.get("status") not in MEASUREMENT_TERMINAL_STATUSES:
                result.update(status="INTERRUPTED_RESULT_UNKNOWN",
                              error="previous worker ended without a confirmed measurement terminal status",
                              launch_result_uncertainty=True)
            elif result["status"] == "EXITED" and audit.get("signalled"):
                result["status"] = "EXITED_WITH_OWNED_RESIDUAL_CLEANED"
            # Original failed result and raw evidence remain untouched. Safe
            # recovery is not itself evidence of an unknown solver's result.
            persist_recovery(cell_dir, attempt, result)
        else:
            if not any((attempt / name).exists() for name in ("intent.json", "spawn_returned.json")):
                # This worker persists intent before Popen. An empty directory
                # alone is not a launch and is not grounds for any signal.
                continue
            for proc in Path("/proc").iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    stat = read_stat(int(proc.name))
                    if stat["state"] in ("Z", "X", "x"):
                        continue
                    cwd = os.path.realpath(os.readlink(proc / "cwd"))
                except (FileNotFoundError, ProcessLookupError):
                    continue
                except PermissionError as exc:
                    raise AmbiguousOwnership("cannot disprove live unregistered attempt after denied /proc read: " + repr(exc))
                if cwd == str(attempt.resolve()):
                    raise AmbiguousOwnership("live attempt lacks durable Popen ownership markers: " + str(attempt))
            if (attempt / "intent.json").exists():
                result = recovery_base(attempt, previous)
                result.update(status="INTERRUPTED_RESULT_UNKNOWN",
                              cleanup=dict(verified=True, active_owned_processes=0,
                                           reason="no live process with unfinished attempt cwd; launch/return unknown"),
                              error="previous worker ended before durable ownership/return result",
                              recovered_at=utc_now(), launch_result_uncertainty=True)
                persist_recovery(cell_dir, attempt, result)


def run_cell(job, identity, manifest, batch_dir, timeout, gnu_time, allowed, invocation):
    global IN_LAUNCH_REGISTRATION
    cell_dir = batch_dir / "cells" / job["cell_id"]
    cell_dir.mkdir(parents=True, exist_ok=True)
    check_unfinished(cell_dir, allowed)
    cached = find_completed(cell_dir, job, identity)
    if cached is not None:
        _, recovered = cached
        recovered["recovered_without_new_launch"] = True
        return recovered
    attempt_number = 1 + max([int(p.name.split("_")[-1]) for p in cell_dir.glob("attempt_*") if p.is_dir() and p.name.split("_")[-1].isdigit()] or [0])
    attempt = cell_dir / ("attempt_%04d" % attempt_number)
    attempt.mkdir(exist_ok=False)
    command = [str(timeout), "--verbose", "-k", "0.2", "60", str(gnu_time), "-v", str(Path(job["exe"]).resolve()), str(Path(job["input"]).resolve())]
    result = dict(cell_id=job["cell_id"], method_id=job["method_id"], case_id=job["case_id"],
                  member=job.get("member"), name=job.get("name"), batch_id=manifest["batch_id"],
                  invocation_id=invocation["invocation_id"], worker_identity=invocation,
                  **identity, input=job["input"], exe=job["exe"], command=command,
                  attempt=str(attempt), stdout_path=str(attempt / "stdout.txt"), stderr_path=str(attempt / "stderr.txt"),
                  started_at=utc_now(), started_time_ns=time.time_ns(), started_monotonic_ns=time.monotonic_ns(),
                  timeout_seconds=60, outer_wait_seconds=63, status="STARTED", complete=False,
                  measurement_complete=False, attempt_cleanup_complete=False, locale_override="C",
                  pid=None, pgid=None, owner=None, cleanup=None, returncode=None, metrics_parsed=False,
                  popen_returned=False)
    atomic_json(attempt / "intent.json", result)
    process = None
    owner = None
    unexpected = None
    try:
        with (attempt / "stdout.txt").open("wb") as stdout, (attempt / "stderr.txt").open("wb") as stderr:
            lower_ticks = boot_ticks()
            # Defer our handler's exception until ownership is durable. Do not
            # block signals with pthread_sigmask: that mask would be inherited
            # by GNU timeout/the solver and change their termination semantics.
            IN_LAUNCH_REGISTRATION = True
            try:
                result["launch_monotonic_ns"] = time.monotonic_ns()
                environment = os.environ.copy();environment["LC_ALL"] = "C"
                process = subprocess.Popen(command, cwd=str(attempt), stdout=stdout, stderr=stderr,
                                           start_new_session=True, env=environment)
                result.update(pid=process.pid, popen_returned=True)
                atomic_json(attempt / "spawn_returned.json", result)
                # The unreaped leader has a stat entry even if it exits immediately.
                leader = read_stat(process.pid)
                if leader["pgid"] != process.pid or leader["session"] != process.pid or leader["start_ticks"] < lower_ticks - 2:
                    raise AmbiguousOwnership("Popen did not establish its expected private session")
                owner = dict(pid=process.pid, pgid=process.pid, session=process.pid, leader_start_ticks=leader["start_ticks"],
                             birth_lower_ticks=lower_ticks - 2, cwd=str(attempt.resolve()), boot_id=boot_id(), command=command,
                             identity=identity, cell_id=job["cell_id"], batch_id=manifest["batch_id"], captured_at=utc_now())
                atomic_json(attempt / "ownership.json", owner)
                result.update(pid=process.pid, pgid=process.pid, owner=owner)
                atomic_json(attempt / "started.json", result)
            finally:
                IN_LAUNCH_REGISTRATION = False
            if SIGNAL_RECEIVED is not None:
                raise WorkerSignal("stop signal received during launch registration")
            try:
                elapsed = (time.monotonic_ns() - result["launch_monotonic_ns"]) / 1e9
                result["returncode"] = process.wait(timeout=max(0.0, OUTER_WAIT_SECONDS - elapsed))
                result["process_exit_elapsed_seconds"] = (time.monotonic_ns() - result["launch_monotonic_ns"]) / 1e9
                classify_exit(result, timeout, attempt / "stderr.txt")
            except subprocess.TimeoutExpired:
                result["status"] = "OUTER_TIMEOUT"
                result["error"] = "owned leader exceeded63 second outer wait"
    except WorkerSignal as exc:
        unexpected = exc
        result.update(status="CANCELLED_SIGNAL", error=repr(exc))
    except BaseException as exc:
        unexpected = exc
        result.update(status="LAUNCH_OR_WORKER_ERROR", error=repr(exc))
    finally:
        if owner is not None:
            try:
                result["cleanup"] = cleanup_group(owner, allowed, force=process is not None and process.poll() is None)
            except BaseException as exc:
                result["cleanup"] = dict(verified=False, active_owned_processes=None,
                                         ambiguous=[dict(reason="cleanup_exception", error=repr(exc))])
        elif process is not None:
            result["cleanup"] = dict(verified=False, active_owned_processes=None,
                                     ambiguous=[dict(reason="Popen ownership capture failed", pid=process.pid)])
        else:
            result["cleanup"] = dict(verified=True, active_owned_processes=0, reason="Popen never returned a process")
        if process is not None:
            try:
                after_cleanup = process.wait(timeout=0.25)
                if result["returncode"] is None:
                    result["returncode"] = after_cleanup
            except subprocess.TimeoutExpired:
                result["cleanup"]["verified"] = False
                result["cleanup"]["active_owned_processes"] = None
                result["cleanup"].setdefault("ambiguous", []).append(dict(reason="owned leader not reaped after cleanup", pid=process.pid))
        result.update(finished_at=utc_now(), finished_time_ns=time.time_ns(), finished_monotonic_ns=time.monotonic_ns())
        result["wall_seconds"] = (result["finished_monotonic_ns"] - result["started_monotonic_ns"]) / 1e9
        if result["status"] == "EXITED" and result["cleanup"].get("signalled"):
            result["status"] = "EXITED_WITH_OWNED_RESIDUAL_CLEANED"
        set_completion_fields(result)
        result["stdout_sha256"] = sha_file(attempt / "stdout.txt") if (attempt / "stdout.txt").exists() else None
        result["stderr_sha256"] = sha_file(attempt / "stderr.txt") if (attempt / "stderr.txt").exists() else None
        atomic_json(attempt / "cleanup.json", result["cleanup"])
        atomic_json(attempt / "result.json", result)
        atomic_json(cell_dir / "result.json", result)
        journal(batch_dir / "journal.jsonl", dict(event="cell_finished", at=utc_now(), result=result))
    if not result["cleanup"]["verified"]:
        raise AmbiguousOwnership("cleanup is not verified for " + job["cell_id"])
    if isinstance(unexpected, WorkerSignal):
        raise unexpected
    return result


def run_locked(manifest, root, timeout, gnu_time, allowed, work, total, reserve, case_map, batch_dir, lock_records):
    manifest_hash = hashlib.sha256(canonical(manifest).encode()).hexdigest()
    status = dict(batch_id=manifest["batch_id"], manifest_sha256=manifest_hash, status="RUNNING", started_at=utc_now(),
                  planned_jobs=len(manifest["jobs"]), cell_launch_attempts=0, confirmed_popen_this_invocation=0,
                  cached_complete=0, terminal_this_invocation=0, recovered_terminal=0, nonterminal_this_invocation=0,
                  cleanup_verified=None, active_owned_processes=None, results=[], pending_jobs=[], error=None,
                  case_timeout_seconds=60, work_limit_seconds=work, total_limit_seconds=total, reserve_seconds=reserve,
                  lifecycle_flock=lock_records, hard_total_deadline_enforced_by="external parent300s watchdog plus45s ownership cleanup takeover")
    try:
        ledger_path = batch_dir / "budget_origin.json"
        if ledger_path.exists():
            origin = read_json(ledger_path)
            if origin["manifest_sha256"] != manifest_hash or origin["boot_id"] != boot_id():
                raise ValueError("batch identity/boot changed; use a new batch_id instead of resetting this window")
        else:
            origin = dict(manifest_sha256=manifest_hash, boot_id=boot_id(), monotonic_ns=time.monotonic_ns(), wall_time_ns=time.time_ns(), at=utc_now())
            atomic_json(ledger_path, origin)
        atomic_json(batch_dir / "manifest.json", manifest)
        invocation_id = str(os.getpid()) + "_" + str(time.monotonic_ns())
        invocation = dict(invocation_id=invocation_id, worker_sha256=sha_file(__file__), manifest_sha256=manifest_hash,
                    private_timeout_sha256=sha_file(timeout), private_gnu_time_sha256=sha_file(gnu_time),
                    python=sys.version, pid=os.getpid(), boot_id=boot_id(), allowed_binary_paths=sorted(allowed))
        atomic_json(batch_dir / ("worker_identity_" + invocation_id + ".json"), invocation)
        atomic_json(batch_dir / "worker_identity.json", invocation)
        # A stale worker may have left independently-sessioned children. Resolve
        # all durable attempts before either cache decisions or budget yielding.
        for existing_cell in sorted((batch_dir / "cells").glob("*")) if (batch_dir / "cells").exists() else []:
            if existing_cell.is_dir():
                check_unfinished(existing_cell, allowed)
        status.update(cleanup_verified=True, active_owned_processes=0)
        deadline = origin["monotonic_ns"] / 1e9 + work
        for index, raw_job in enumerate(manifest["jobs"]):
            job = dict(case_map.get(raw_job["case_id"], {}), **raw_job)
            if stop_requested(batch_dir, root):
                status["status"] = "STOP_REQUESTED"
                status["pending_jobs"] = [j["cell_id"] for j in manifest["jobs"][index:]]
                break
            if time.monotonic() >= deadline:
                status["status"] = "YIELDED_BUDGET"
                status["pending_jobs"] = [j["cell_id"] for j in manifest["jobs"][index:]]
                break
            identity = job_identity(job, manifest)
            cell_dir = batch_dir / "cells" / job["cell_id"]
            latest = cell_dir / "result.json"
            cached = find_completed(cell_dir, job, identity)
            if cached is not None:
                cache_path, _ = cached
                status["cached_complete"] += 1
                status["results"].append(dict(cell_id=job["cell_id"], cached=True, measurement_complete=True, result=str(cache_path), identity=identity))
                continue
            if stop_requested(batch_dir, root):
                status["status"] = "STOP_REQUESTED"
                status["pending_jobs"] = [j["cell_id"] for j in manifest["jobs"][index:]]
                break
            if deadline - time.monotonic() < CASE_SECONDS + 5:
                status["status"] = "YIELDED_BUDGET"
                status["pending_jobs"] = [j["cell_id"] for j in manifest["jobs"][index:]]
                break
            status["cell_launch_attempts"] += 1
            # From this point until run_cell returns, a terminal cleanup claim
            # is deliberately unavailable to the batch-level exception path.
            status.update(cleanup_verified=None, active_owned_processes=None)
            result = run_cell(job, identity, manifest, batch_dir, timeout, gnu_time, allowed, invocation)
            terminal = measurement_complete(result)
            if result.get("recovered_without_new_launch") and terminal:
                status["recovered_terminal"] += 1
            elif terminal:
                status["terminal_this_invocation"] += 1
            else:
                status["nonterminal_this_invocation"] += 1
            status["confirmed_popen_this_invocation"] += int(result.get("popen_returned", False) and result.get("invocation_id") == invocation_id)
            status.update(cleanup_verified=True, active_owned_processes=0)
            status["results"].append(dict(cell_id=job["cell_id"], cached=False, result=str(latest), status=result["status"], measurement_complete=terminal, identity=identity))
            atomic_json(batch_dir / "batch_status.json", status)
            print(canonical(dict(event="cell_finished", batch_id=manifest["batch_id"], cell_id=job["cell_id"], status=result["status"], cleanup_verified=True)), flush=True)
        else:
            status["status"] = "COMPLETE"
    except WorkerSignal as exc:
        status.update(status="STOPPED_SIGNAL", error=repr(exc))
    except AmbiguousOwnership as exc:
        status.update(status="STOPPED_AMBIGUOUS_CLEANUP", error=repr(exc), cleanup_verified=False, active_owned_processes=None)
    except BaseException as exc:
        status.update(status="FAILED_PREPARATION_OR_IDENTITY", error=repr(exc))
    finally:
        # Count only durable current-invocation Popen-return markers, including
        # an attempt whose cleanup failed before the run_cell return path.
        invocation_id = locals().get("invocation_id")
        if invocation_id is not None:
            confirmed = []
            for marker in (batch_dir / "cells").glob("*/attempt_*/spawn_returned.json") if (batch_dir / "cells").exists() else []:
                record = read_json(marker)
                if record.get("invocation_id") == invocation_id and record.get("popen_returned"):
                    confirmed.append(record["cell_id"])
            status["confirmed_popen_this_invocation"] = len(confirmed)
            status["confirmed_popen_cell_ids"] = confirmed
        unresolved = []
        for attempt in (batch_dir / "cells").glob("*/attempt_*") if (batch_dir / "cells").exists() else []:
            terminal = attempt / "recovery_result.json" if (attempt / "recovery_result.json").exists() else attempt / "result.json"
            if terminal.exists():
                record = read_json(terminal)
                if not record.get("cleanup", {}).get("verified"):
                    unresolved.append(str(attempt))
            elif any((attempt / name).exists() for name in ("intent.json", "spawn_returned.json", "ownership.json")):
                unresolved.append(str(attempt))
        status["unresolved_attempts"] = unresolved
        if unresolved:
            status.update(cleanup_verified=False, active_owned_processes=None)
            if status["status"] in ("COMPLETE", "YIELDED_BUDGET", "STOP_REQUESTED"):
                status["status"] = "STOPPED_AMBIGUOUS_CLEANUP"
        elif status["cleanup_verified"] is not False:
            status.update(cleanup_verified=True, active_owned_processes=0)
        terminal_ids = {r["cell_id"] for r in status["results"] if r.get("measurement_complete") is True}
        # A signal can arrive after a terminal result was persisted but before
        # run_cell returned. Such a completed cell is not pending for rerun.
        for job in manifest["jobs"]:
            cache = job.get("cache_key")
            wanted = cache if isinstance(cache, dict) else job.get("identity", {})
            wanted = {key: wanted.get(key, job.get(key, manifest.get(key))) for key in IDENTITY_KEYS}
            expected = dict(cache_key=cache, identity=wanted,
                            cache_digest=hashlib.sha256(canonical(dict(cache_key=cache, identity=wanted)).encode()).hexdigest())
            cell_dir = batch_dir / "cells" / job["cell_id"]
            if find_completed(cell_dir, job, expected) is not None:
                terminal_ids.add(job["cell_id"])
        status["remaining_jobs"] = [job["cell_id"] for job in manifest["jobs"] if job["cell_id"] not in terminal_ids]
        status["terminal_jobs_total"] = len(terminal_ids)
        if status["status"] == "COMPLETE" and status["remaining_jobs"]:
            status["status"] = "PARTIAL_MEASUREMENT_PENDING"
        status["finished_at"] = utc_now()
        status["finished_monotonic_ns"] = time.monotonic_ns()
        if (batch_dir / "budget_origin.json").exists():
            status["elapsed_from_original_start_seconds"] = (status["finished_monotonic_ns"] - read_json(batch_dir / "budget_origin.json")["monotonic_ns"]) / 1e9
        atomic_json(batch_dir / "batch_status.json", status)
        journal(batch_dir / "journal.jsonl", dict(event="batch_finished", at=utc_now(), status=status))
    print(canonical(status), flush=True)
    return 0 if status["status"] in ("COMPLETE", "YIELDED_BUDGET", "STOP_REQUESTED") else 2


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "-"
    manifest = json.load(sys.stdin) if source == "-" else read_json(source)
    root, timeout, gnu_time, allowed, work, total, reserve, case_map = validate_manifest(manifest)
    batch_dir = root / manifest["batch_id"]
    # All batches of this matrix must share output_root. Held FDs, rather than
    # check/unlink stale-PID files, serialize the full worker/cleanup lifetime.
    with timing_locks(root, batch_dir) as locks:
        return run_locked(manifest, root, timeout, gnu_time, allowed, work, total, reserve, case_map, batch_dir, locks)


def on_signal(number, frame):
    global SIGNAL_RECEIVED
    SIGNAL_RECEIVED = number
    # Avoid a second graceful-stop signal interrupting ownership cleanup.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if IN_CLEANUP or IN_LAUNCH_REGISTRATION:
        return
    raise WorkerSignal("received signal " + str(number))


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    sys.exit(main())
