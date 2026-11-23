"""Small shared helpers: subprocesses, locks, JSON, statistics."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import math
import subprocess
from pathlib import Path


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd, cwd=None, env=None, timeout=None, check=True, log_file: Path | None = None):
    """Run a command, capturing combined output. Returns (returncode, output)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout, text=True, errors="replace",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        code, out = p.returncode, p.stdout
    except subprocess.TimeoutExpired as e:
        code, out = 124, (e.stdout or "") + f"\n[timeout after {timeout}s]"
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"$ {' '.join(map(str, cmd))}\n{out}\n")
    if check and code != 0:
        raise RuntimeError(f"command failed ({code}): {' '.join(map(str, cmd))}\n{out[-4000:]}")
    return code, out


_held: dict[str, int] = {}


@contextlib.contextmanager
def machine_lock(work: Path):
    """Serialises builds and benchmarks so measurements never overlap with other load we create.

    Re-entrant within a process: flock on a second open of the same file would block on our own lock.
    """
    work.mkdir(parents=True, exist_ok=True)
    key = str((work / ".machine.lock").resolve())
    if _held.get(key):
        _held[key] += 1
        try:
            yield
        finally:
            _held[key] -= 1
        return
    with open(key, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        _held[key] = 1
        try:
            yield
        finally:
            _held[key] = 0
            fcntl.flock(f, fcntl.LOCK_UN)


def read_json(path: Path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
        f.write("\n")
    tmp.replace(path)


def append_jsonl(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def geomean(xs) -> float:
    xs = [x for x in xs if x > 0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def median(xs) -> float:
    s = sorted(xs)
    n = len(s)
    return float("nan") if n == 0 else (s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2]))


def tail(text: str, lines: int = 60) -> str:
    return "\n".join(text.splitlines()[-lines:])
