"""Engine adapter: source checkout, worktree slots, builds and binary artifacts.

Everything DuckDB-specific about *building* lives here. The rest of the framework only needs
`binary(sha)` and the SQL dialect details in `session.py`.
"""
from __future__ import annotations

import glob
import os
import shutil
import time
from pathlib import Path

from .config import Config
from .util import log, machine_lock, sh, tail

EVOLVE_BRANCH = "dbe/evolve"
GIT_ID = ["-c", "user.name=db_evolve", "-c", "user.email=db_evolve@localhost", "-c", "commit.gpgsign=false"]


class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.e = cfg["engine"]
        self.repo = cfg.repo
        # each run family gets its own branch and release tags (specialised runs: dbe/spec/q09, ...)
        self.branch = self.e.get("branch", EVOLVE_BRANCH)
        self.tag_prefix = self.e.get("tag_prefix", "dbe")

    # --- git ---------------------------------------------------------------
    def git(self, *args, cwd: Path | None = None, check=True) -> str:
        return sh(["git", *GIT_ID, *args], cwd=cwd or self.repo, check=check)[1].strip()

    def setup(self) -> str:
        """Clone the engine (if needed) and create the evolve branch at the base ref. Returns v0's sha."""
        if not (self.repo / ".git").exists():
            log(f"cloning {self.e['repo']} @ {self.e['base_ref']}")
            self.repo.parent.mkdir(parents=True, exist_ok=True)
            sh(["git", "clone", "--branch", self.e["base_ref"], "--depth", "1", self.e["repo"], str(self.repo)])
        base = self.git("rev-parse", f"{self.e['base_ref']}^{{commit}}")
        if self.git("rev-parse", "--verify", "--quiet", EVOLVE_BRANCH, check=False) == "":
            self.git("branch", EVOLVE_BRANCH, base)
            self.git("tag", "-f", "dbe/v0", base)
        return base

    def base_sha(self) -> str:
        return self.git("rev-parse", "dbe/v0^{commit}")

    def best_sha(self) -> str:
        return self.git("rev-parse", self.branch)

    def slot(self, n: int = 0) -> Path:
        path = self.cfg.slots / f"slot{n}"
        if not path.exists():
            self.cfg.slots.mkdir(parents=True, exist_ok=True)
            self.git("worktree", "prune")
            self.git("worktree", "add", "--detach", str(path), self.base_sha())
        return path

    def checkout(self, slot: Path, sha: str) -> None:
        try:
            self.git("reset", "--hard", "-q", cwd=slot)
        except RuntimeError:
            self.repair_after_crash(slot, sha)
        self.git("clean", "-fdq", cwd=slot)
        self.git("checkout", "-q", "--detach", sha, cwd=slot)

    def repair_after_crash(self, slot: Path, sha: str) -> None:
        """A hard reboot can leave empty object files from the last commits (of an experiment that
        never reached the ledger) and a worktree HEAD pointing at one. Set the empty files aside,
        point HEAD at a known-good commit and reset."""
        objects = Path(self.git("rev-parse", "--git-common-dir", cwd=slot)).resolve() / "objects"
        if not objects.is_absolute():
            objects = (slot / objects).resolve()
        aside = self.cfg.work / "logs" / "empty-objects" / time.strftime("%Y%m%d-%H%M%S")
        empty = [f for f in objects.glob("??/*") if f.is_file() and f.stat().st_size == 0]
        for f in empty:
            (aside / f.parent.name).mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(aside / f.parent.name / f.name))
        log(f"repairing {slot.name} after a crash: {len(empty)} empty git objects set aside in {aside}")
        self.git("update-ref", "--no-deref", "HEAD", sha, cwd=slot)
        self.git("reflog", "expire", "--expire-unreachable=now", "--all", cwd=slot, check=False)
        self.git("reset", "--hard", "-q", cwd=slot)

    def commit_all(self, slot: Path, message: str) -> str | None:
        """Commit whatever the agent left in the worktree. Returns the new sha, or None if nothing changed."""
        self.git("add", "-A", cwd=slot)
        if self.git("status", "--porcelain", cwd=slot) == "":
            return None
        self.git("commit", "-q", "-m", message, cwd=slot)
        return self.git("rev-parse", "HEAD", cwd=slot)

    def changed_files(self, base: str, cand: str) -> list[str]:
        out = self.git("diff", "--name-only", f"{base}..{cand}")
        return [line for line in out.splitlines() if line]

    def diff(self, base: str, cand: str) -> str:
        return sh(["git", "diff", f"{base}..{cand}"], cwd=self.repo)[1]

    def accept(self, sha: str) -> None:
        self.git("branch", "-f", self.branch, sha)

    def tag_release(self, version: int, sha: str) -> None:
        self.git("tag", "-f", f"{self.tag_prefix}/v{version}", sha)

    def releases(self) -> dict[str, str]:
        out = self.git("tag", "-l", f"{self.tag_prefix}/v*")
        tags = sorted(out.split(), key=lambda t: int(t.rsplit("v", 1)[1]))
        return {t.rsplit("/", 1)[1]: self.git("rev-parse", f"{t}^{{commit}}") for t in tags}

    # --- build -------------------------------------------------------------
    def build_env(self, src: Path) -> dict:
        tc = self.cfg.toolchain
        env = dict(os.environ)
        if tc.exists():
            env["PATH"] = f"{tc / 'bin'}:{env['PATH']}"
            cc = glob.glob(str(tc / "bin" / "*-gnu-cc"))
            cxx = glob.glob(str(tc / "bin" / "*-gnu-c++"))
            if cc and cxx:
                env["CC"], env["CXX"] = cc[0], cxx[0]
            # binaries must find the toolchain's libstdc++ at run time
            env["LDFLAGS"] = f"-Wl,-rpath,{tc / 'lib'} -L{tc / 'lib'}"
        env["CCACHE_DIR"] = str(self.cfg.work / "ccache")
        env["CCACHE_BASEDIR"] = str(src)
        env["CCACHE_NOHASHDIR"] = "1"
        env["CCACHE_MAXSIZE"] = "20G"
        return env

    def build(self, src: Path, name: str, log_file: Path | None = None) -> tuple[bool, str, Path]:
        """Configure (first time) and build incrementally. Returns (ok, output tail, binary path)."""
        bdir = self.cfg.builds / name
        env = self.build_env(src)
        with machine_lock(self.cfg.work):
            if not (bdir / "build.ninja").exists():
                bdir.mkdir(parents=True, exist_ok=True)
                cmd = ["cmake", "-G", "Ninja", "-S", str(src), "-B", str(bdir),
                       "-DCMAKE_BUILD_TYPE=Release",
                       f"-DBUILD_EXTENSIONS={';'.join(self.e['extensions'])}",
                       "-DBUILD_UNITTESTS=0", "-DBUILD_SHELL=1",
                       "-DENABLE_EXTENSION_AUTOLOADING=0", "-DENABLE_EXTENSION_AUTOINSTALL=0",
                       f"-DOVERRIDE_GIT_DESCRIBE={self.e['version_override']}",
                       "-DCMAKE_C_COMPILER_LAUNCHER=ccache", "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache"]
                code, out = sh(cmd, env=env, check=False, log_file=log_file)
                if code != 0:
                    shutil.rmtree(bdir, ignore_errors=True)
                    return False, tail(out, 80), bdir / "duckdb"
            code, out = sh(["ninja", "-C", str(bdir), "-j", str(self.e["build_jobs"])],
                           env=env, check=False, log_file=log_file, timeout=3 * 3600)
        return code == 0, _build_errors(out), bdir / "duckdb"

    def artifact(self, sha: str) -> Path:
        return self.cfg.artifacts / sha[:12] / "duckdb"

    def binary(self, sha: str, slot_n: int = 0, log_file: Path | None = None) -> Path:
        """Return the binary for a commit, building it in a slot if it is not in the artifact store."""
        art = self.artifact(sha)
        if art.exists():
            return art
        slot = self.slot(slot_n)
        self.checkout(slot, sha)
        log(f"building {sha[:12]} in {slot.name}")
        ok, out, binary = self.build(slot, slot.name, log_file)
        if not ok:
            raise RuntimeError(f"build of {sha[:12]} failed:\n{out}")
        return self.store(sha, binary)

    def store(self, sha: str, binary: Path) -> Path:
        art = self.artifact(sha)
        art.parent.mkdir(parents=True, exist_ok=True)
        tmp = art.with_suffix(".tmp")
        shutil.copy2(binary, tmp)
        tmp.replace(art)
        return art


def _build_errors(out: str) -> str:
    """Compiler output is long; keep the lines an agent needs to fix the build."""
    lines = out.splitlines()
    hits = [i for i, line in enumerate(lines) if "error" in line.lower() or "FAILED:" in line]
    if not hits:
        return tail(out, 15)
    keep: list[str] = []
    for i in hits[:12]:
        keep.extend(lines[i:i + 6])
        keep.append("...")
    return "\n".join(keep)[-6000:]
