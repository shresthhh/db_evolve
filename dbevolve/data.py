"""Datasets and per-binary database files.

The baseline binary generates each dataset once and exports it to Parquet. Every binary then
loads those Parquet files into its *own* database file, so a candidate that changes the storage
layer is measured on storage it produced itself.

Every path carries the scale factor (`main-sf10`), so data, databases and reference results from
different scale factors can never be mixed.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from .config import Config
from .session import Session
from .util import log, read_json, write_json
from .workload import Workload


def scale_factor(cfg: Config, name: str) -> float:
    return cfg["datasets"][name]["scale_factor"]


def tag(cfg: Config, name: str) -> str:
    return f"{name}-sf{scale_factor(cfg, name):g}"


def ensure_dataset(cfg: Config, wl: Workload, baseline_binary: Path, name: str) -> Path:
    out = cfg.datasets / wl.name / tag(cfg, name)
    if (out / "DONE").exists():
        return out
    sf = scale_factor(cfg, name)
    log(f"generating dataset {wl.name}/{tag(cfg, name)}")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    # generate into a file-backed database so large scale factors can spill to disk
    scratch = out / "generate.duckdb"
    with Session(baseline_binary, scratch, cfg["bench"]["threads"], readonly=False, timeout=4 * 3600) as s:
        s.run(wl.datagen_sql(sf))
        rows = {}
        for t in wl.tables:
            s.run(f"COPY {t} TO '{out / (t + '.parquet')}' (FORMAT parquet)")
            rows[t] = int(s.run(f"SELECT count(*) FROM {t}")[1].splitlines()[-1])
    for f in (scratch, Path(str(scratch) + ".wal")):
        f.unlink(missing_ok=True)
    write_json(out / "DONE", {"scale_factor": sf, "rows": rows})
    return out


def db_path(cfg: Config, wl: Workload, sha: str, name: str) -> Path:
    return cfg.dbs / sha[:12] / f"{wl.name}-{tag(cfg, name)}.duckdb"


def ensure_db(cfg: Config, wl: Workload, binary: Path, sha: str, name: str) -> Path:
    """Load a dataset into a database file with the given binary. Records the load time."""
    db = db_path(cfg, wl, sha, name)
    meta = db.with_suffix(".json")
    if db.exists() and meta.exists():
        db.parent.touch()   # recency for prune_dbs
        return db
    prune_dbs(cfg, keep={sha[:12]})
    src = cfg.datasets / wl.name / tag(cfg, name)
    if not (src / "DONE").exists():
        raise RuntimeError(f"dataset {tag(cfg, name)} has not been generated; run `bin/dbe setup`")
    db.parent.mkdir(parents=True, exist_ok=True)
    for stale in (db, Path(str(db) + ".wal")):
        stale.unlink(missing_ok=True)
    start = time.perf_counter()
    with Session(binary, db, cfg["bench"]["threads"], readonly=False, timeout=3600) as s:
        for t in wl.tables:
            s.run(f"CREATE TABLE {t} AS SELECT * FROM read_parquet('{src / (t + '.parquet')}')")
        s.run("CHECKPOINT")
    write_json(meta, {"load_seconds": round(time.perf_counter() - start, 3), "bytes": db.stat().st_size})
    return db


def prune_dbs(cfg: Config, keep: set[str] = frozenset()) -> None:
    """Keep the per-binary database files under `bench.db_cache_gb` (default 300 GB) by deleting the
    least recently used binaries' databases. Each binary reloads its databases if needed again."""
    cap = cfg["bench"].get("db_cache_gb", 300) * 1e9
    root = cfg.dbs
    if not root.exists():
        return
    dirs = [(d.stat().st_mtime, d, sum(f.stat().st_size for f in d.iterdir() if f.is_file()))
            for d in root.iterdir() if d.is_dir()]
    total = sum(sz for _, _, sz in dirs)
    for _, d, sz in sorted(dirs):
        if total <= cap:
            break
        if d.name in keep:
            continue
        shutil.rmtree(d, ignore_errors=True)
        total -= sz
        log(f"pruned databases of {d.name} ({sz / 1e9:.1f} GB) to stay under {cap / 1e9:.0f} GB")


def db_meta(cfg: Config, wl: Workload, sha: str, name: str) -> dict:
    return read_json(db_path(cfg, wl, sha, name).with_suffix(".json"), {})
