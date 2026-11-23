"""Configuration loading and the project's directory layout."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Config:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path
        p = data["project"]
        self.work = ROOT / p["work_dir"]
        self.runs = ROOT / p["runs_dir"]
        self.results = ROOT / p["results_dir"]
        self.toolchain = ROOT / ".toolchain" / "env"

    def __getitem__(self, key: str):
        return self.data[key]

    # --- layout under work/ -------------------------------------------------
    @property
    def repo(self) -> Path:            # main clone of the engine
        return self.work / self.data["engine"]["name"]

    @property
    def slots(self) -> Path:           # persistent worktrees, one per concurrent experiment
        return self.work / "slots"

    @property
    def builds(self) -> Path:          # build directories (kept for incremental builds)
        return self.work / "build"

    @property
    def artifacts(self) -> Path:       # engine binaries by commit sha
        return self.work / "artifacts"

    @property
    def datasets(self) -> Path:        # parquet files per dataset
        return self.work / "data"

    @property
    def dbs(self) -> Path:             # database files, loaded by each binary itself
        return self.work / "db"

    @property
    def refs(self) -> Path:            # reference results produced by the baseline
        return self.work / "refs"

    @property
    def visible(self) -> Path:         # the only workload files agents may read
        return self.work / "visible"


def load(path: str | os.PathLike | None = None) -> Config:
    p = Path(path or os.environ.get("DBE_CONFIG") or ROOT / "config" / "default.toml")
    with open(p, "rb") as f:
        return Config(tomllib.load(f), p)


def dump_toml(data: dict) -> str:
    """Minimal TOML writer for config dicts (tables of scalars and lists)."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        raise TypeError(f"cannot write {type(v).__name__} to TOML")

    out = []

    def table(prefix: str, d: dict):
        scalars = {k: v for k, v in d.items() if not isinstance(v, dict)}
        if prefix:
            out.append(f"[{prefix}]")
        out.extend(f"{k} = {val(v)}" for k, v in scalars.items())
        out.append("")
        for k, v in d.items():
            if isinstance(v, dict):
                table(f"{prefix}.{k}" if prefix else k, v)

    table("", data)
    return "\n".join(out)


def derive(base: Config, overrides: dict, path: Path) -> Config:
    """Write base config + overrides (nested dict) to `path` and load it."""
    import copy
    data = copy.deepcopy(base.data)
    for section, kv in overrides.items():
        data.setdefault(section, {}).update(kv)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# generated from {base.path.name}; do not edit\n" + dump_toml(data))
    return load(path)
