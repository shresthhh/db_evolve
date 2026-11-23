"""Drives an engine binary through its CLI over pipes and times statements from the outside.

The harness trusts nothing inside the candidate except "SQL in on stdin, CSV out on stdout":
it writes a statement followed by a `.print <sentinel>` command and stops the clock when the
sentinel line comes back. Timing therefore includes parsing, planning, execution and result
rendering, exactly what a client would see, and a candidate cannot influence the clock.
"""
from __future__ import annotations

import os
import select
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


class EngineError(RuntimeError):
    pass


class Session:
    def __init__(self, binary: Path, db: Path | None, threads: int, readonly: bool = True,
                 timeout: float = 300.0):
        self.timeout = timeout
        self.sentinel = f"__dbe_{uuid.uuid4().hex}__"
        self._err = tempfile.TemporaryFile()
        args = [str(binary), "-init", os.devnull, "-csv"]
        if db is not None:
            if readonly:
                args.append("-readonly")
            args.append(str(db))
        env = dict(os.environ, HOME=tempfile.gettempdir())  # never pick up a user's ~/.duckdbrc
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err,
                                  env=env, bufsize=0)
        self._buf = b""
        self.run(f"SET threads = {int(threads)}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        if self.p.poll() is None:
            try:
                self.p.stdin.close()
                self.p.wait(timeout=10)
            except Exception:
                self.p.kill()
        self._err.close()

    def _stderr_since(self, offset: int) -> str:
        self._err.seek(offset)
        return self._err.read().decode(errors="replace").strip()

    def run(self, sql: str, timeout: float | None = None) -> tuple[float, str]:
        """Execute one statement. Returns (seconds, csv_text). Raises EngineError on any engine error."""
        timeout = timeout or self.timeout
        self._err.seek(0, os.SEEK_END)
        err_offset = self._err.tell()
        payload = f"{sql.rstrip().rstrip(';')};\n.print {self.sentinel}\n".encode()
        marker = self.sentinel.encode() + b"\n"
        start = time.perf_counter()
        try:
            self.p.stdin.write(payload)
        except (BrokenPipeError, OSError):
            raise EngineError(f"engine process is gone: {self._stderr_since(0)[-2000:]}")
        fd = self.p.stdout.fileno()
        deadline = start + timeout
        while True:
            idx = self._buf.find(marker)
            if idx != -1 and (idx == 0 or self._buf[idx - 1:idx] == b"\n"):
                elapsed = time.perf_counter() - start
                out, self._buf = self._buf[:idx], self._buf[idx + len(marker):]
                break
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                self.p.kill()
                raise EngineError(f"statement timed out after {timeout:.0f}s")
            ready, _, _ = select.select([fd], [], [], min(remaining, 1.0))
            if ready:
                chunk = os.read(fd, 1 << 16)
                if not chunk:
                    raise EngineError(f"engine exited (code {self.p.wait()}): {self._stderr_since(err_offset)[-2000:]}")
                self._buf += chunk
        err = self._stderr_since(err_offset)
        if err:
            raise EngineError(err[-2000:])
        return elapsed, out.decode(errors="replace")
