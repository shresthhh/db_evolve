"""`dbe-tool`: the only shell command agents can run. It works on the agent's worktree slot
(DBE_SLOT, or the current directory) and only ever exposes the visible (train) queries.

    dbe-tool build                    incremental build of the working tree
    dbe-tool bench [template ...]     verify + time visible queries: working tree vs current best
    dbe-tool profile <instance>       EXPLAIN ANALYZE on the working-tree build
    dbe-tool sql "<statement>"        run one statement (read-only) on the working-tree build
    dbe-tool queries                  list visible query instances
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from . import bench, config, data
from .bench import Harness
from .config import ROOT
from .util import read_json, write_json
from .engine import Engine
from .loop import explain_analyze
from .session import EngineError, Session
from .workload import Workload

MAX_OUT = 6000


def _slot(cfg) -> Path:
    slot = Path(os.environ.get("DBE_SLOT") or os.getcwd()).resolve()
    if cfg.slots.resolve() not in slot.parents:
        sys.exit("dbe-tool must be run from inside a worktree slot")
    while slot.parent != cfg.slots.resolve():
        slot = slot.parent
    return slot


# --- builds -------------------------------------------------------------------------
# A full rebuild of the engine takes longer than an agent's shell call may last, and an agent that
# backgrounds a build and stops to wait ends its own non-interactive session. So the build runs in
# a detached worker, and `build` waits at most BUILD_WAIT_S per call: the agent just calls it again.

BUILD_WAIT_S = int(os.environ.get("DBE_BUILD_WAIT_S", "100"))  # override only for testing


def _status_path(cfg, slot: Path) -> Path:
    return cfg.builds / f"{slot.name}.status.json"


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _changed_since(slot: Path, t: float) -> list[str]:
    """Working-tree files modified after time t (edits made while a build was running)."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=slot,
                         capture_output=True, text=True).stdout
    names = [line[3:].split(" -> ")[-1] for line in out.splitlines() if line.strip()]
    return [n for n in names if not n.startswith(".dbe/")
            and (slot / n).is_file() and (slot / n).stat().st_mtime > t]


def build(cfg, slot: Path) -> int:
    path = _status_path(cfg, slot)
    st = read_json(path, {})
    if not (st.get("state") == "running" and _alive(st.get("pid"))):
        st = {"state": "running", "started": time.time(), "pid": None}
        write_json(path, st)
        p = subprocess.Popen([sys.executable, "-m", "dbevolve.tool", "_build-worker"], cwd=str(ROOT),
                             env=dict(os.environ, DBE_SLOT=str(slot)), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        st["pid"] = p.pid
        write_json(path, st)
    deadline = time.time() + BUILD_WAIT_S
    while time.time() < deadline:
        cur = read_json(path, {})
        if cur.get("state") in ("ok", "failed"):
            print("BUILD OK" if cur["state"] == "ok" else f"BUILD FAILED\n{cur.get('output', '')}")
            late = _changed_since(slot, cur["started"])
            if late:
                print(f"NOTE: {', '.join(late[:5])} changed after this build started; run `build` again.")
            return 0 if cur["state"] == "ok" else 1
        if not _alive(cur.get("pid")):
            write_json(path, {**cur, "state": "failed", "output": "build process died"})
            print("BUILD FAILED\nbuild process died unexpectedly; run `build` again")
            return 1
        time.sleep(2)
    print(f"BUILD RUNNING ({time.time() - st['started']:.0f} s so far). Run `dbe-tool build` again to keep "
          "waiting; it returns as soon as the build finishes. Do not run it in the background.")
    return 2


def build_worker(cfg, engine: Engine, slot: Path) -> int:
    path = _status_path(cfg, slot)
    st = read_json(path, {})
    st.update(state="running", pid=os.getpid())
    st.setdefault("started", time.time())
    write_json(path, st)
    try:
        ok, out, _ = engine.build(slot, slot.name)
    except Exception as e:  # never leave the status stuck at "running"
        ok, out = False, f"{type(e).__name__}: {e}"
    write_json(path, {**st, "state": "ok" if ok else "failed", "output": out, "finished": time.time()})
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cfg = config.load()
    engine, wl = Engine(cfg), Workload(cfg)
    slot = _slot(cfg)
    cmd, args = argv[0], argv[1:]

    if cmd == "_build-worker":          # internal: the detached process behind `build`
        return build_worker(cfg, engine, slot)
    if cmd == "build":
        return build(cfg, slot)

    h = Harness(cfg, engine, wl)
    binary = cfg.builds / slot.name / "duckdb"
    best = engine.best_sha()
    best_db = data.ensure_db(cfg, wl, engine.binary(best), best, "main")

    if cmd == "queries":
        for inst in h.instances("train"):
            print(f"{inst.id}\t.dbe/queries/{inst.id}.sql")
        return 0

    if not binary.exists():
        print("no build of this working tree yet: run `dbe-tool build` first")
        return 1

    if cmd == "bench":
        wanted = set(args)
        # quick check: two bindings per template keeps a full run to a few minutes at large scale factors
        insts = [i for i in h.instances("train") if (not wanted or i.item in wanted or i.template in wanted) and i.index < 2]
        if not insts:
            print(f"no visible templates match {sorted(wanted)}; visible: {wl.split['train']}")
            return 1
        r = h.interleaved({"A": best, "B": (binary, best_db)}, "ABBA", insts, timed_runs=2)
        a, b = bench.template_times(r["times"]["A"], insts), bench.template_times(r["times"]["B"], insts)
        print(f"{'template':<10}{'best ms':>10}{'yours ms':>10}{'change':>9}")
        for t in sorted(a):
            if t in b:
                print(f"{t:<10}{1000 * a[t]:>10.1f}{1000 * b[t]:>10.1f}{100 * (b[t] / a[t] - 1):>+8.1f}%")
        rs = bench.ratios(b, a)
        if rs:
            print(f"{'geomean':<10}{'':>20}{100 * (bench.geomean(rs.values()) - 1):>+8.1f}%")
        for f in r["failures"]["B"]:
            print(f"FAILED {f['instance']}: {f['reason']}")
        print("(quick check: 2 bindings per template, 4 hot runs each; differences under ~5% are noise)")
        return 1 if r["failures"]["B"] else 0

    if cmd == "profile":
        inst = next((i for i in h.instances("train") if args and i.id == args[0]), None)
        if inst is None:
            print("usage: dbe-tool profile <instance>   (see `dbe-tool queries`)")
            return 1
        with Session(binary, best_db, cfg["bench"]["threads"]) as s:
            print(explain_analyze(s, inst.sql, limit=20000))
        return 0

    if cmd == "sql":
        if not args:
            print('usage: dbe-tool sql "<statement>"')
            return 1
        with Session(binary, best_db, cfg["bench"]["threads"], timeout=120) as s:
            try:
                for stmt in [x for x in " ".join(args).split(";") if x.strip()]:
                    elapsed, out = s.run(stmt)
                    print(out[:MAX_OUT] + ("\n... (truncated)" if len(out) > MAX_OUT else ""))
                    print(f"({1000 * elapsed:.1f} ms)")
            except EngineError as e:
                print(f"ERROR: {e}")
                return 1
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
