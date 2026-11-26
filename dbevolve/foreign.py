"""Hidden gate on a second, unrelated workload (e.g. TPC-DS while evolving on TPC-H).

A candidate must give the baseline's answers on every query of the foreign workload, raise no
errors, and make no query much slower than the current best (more than `max_slowdown` times and
by more than `abs_slack_ms`). Agents only ever see counts. This catches what the main workload
cannot show: a joint48 change broke TPC-DS q83 (a join of 32- and 64-bit keys) and another made
q78 3x slower, though both passed every TPC-H check.

Config (in the evolving workload's config):

    [gates.foreign]
    config = "config/tpcds.toml"   # the foreign workload
    scale_factor = 1.0
    max_slowdown = 2.0
    abs_slack_ms = 20.0

Queries whose baseline answer is not reproducible (ties under ORDER BY ... LIMIT, so different
rows each run) are found once at setup and checked for errors and time only.
"""
from __future__ import annotations

from statistics import median

from . import config, data
from .bench import Harness
from .engine import Engine
from .util import log, machine_lock, read_json, write_json
from .workload import Workload


def settings(cfg) -> dict | None:
    return (cfg.data.get("gates") or {}).get("foreign")


def harness(cfg) -> Harness | None:
    f = settings(cfg)
    if not f:
        return None
    base = config.load(config.ROOT / f["config"])
    fcfg = config.derive(base, {"datasets": {"main": {"scale_factor": float(f.get("scale_factor", 1.0))}}},
                         base.work / "configs" / f"foreign-{base['workload']['name']}.toml")
    return Harness(fcfg, Engine(fcfg), Workload(fcfg))


def _instances(fh: Harness):
    return [i for s in ("train", "val", "test") if fh.wl.split[s] for i in fh.instances(s)]


def _meta_path(fh: Harness):
    return fh.cfg.work / f"foreign-{fh.wl.name}-{data.tag(fh.cfg, 'main')}.json"


def setup(cfg) -> dict:
    """Generate the foreign data with a build that links its generator, make the baseline's
    reference answers, and find the queries whose answer is not reproducible."""
    fh = harness(cfg)
    meta = read_json(_meta_path(fh)) if fh else None
    if fh is None or meta:
        return meta or {}
    eng = fh.engine
    gen_cfg = config.load(config.ROOT / settings(cfg)["config"])
    gen_cfg.data["engine"]["extensions"] = list(dict.fromkeys(gen_cfg["engine"]["extensions"] + [fh.wl.name]))
    slot = eng.slot(0)
    eng.checkout(slot, eng.base_sha())
    ok, out, gen_binary = Engine(gen_cfg).build(slot, f"datagen-{fh.wl.name}",
                                                fh.cfg.work / "logs" / f"datagen-{fh.wl.name}.log")
    if not ok:
        raise RuntimeError(f"build with the {fh.wl.name} generator failed:\n{out}")
    data.ensure_dataset(fh.cfg, fh.wl, gen_binary, "main")
    insts = _instances(fh)
    fh.ensure_references(insts, "main")
    unstable = set()
    with machine_lock(fh.cfg.work):
        for _ in range(2):
            _, fails = fh.run_pass(eng.base_sha(), insts, "main", timed_runs=1, warmup_runs=0)
            unstable |= {f["instance"] for f in fails}
    meta = {"workload": fh.wl.name, "dataset": data.tag(fh.cfg, "main"), "queries": len(insts),
            "unstable": sorted(unstable)}
    write_json(_meta_path(fh), meta)
    log(f"foreign gate: {len(insts)} {fh.wl.name} queries; not reproducible on the baseline: "
        f"{', '.join(sorted(unstable)) or 'none'}")
    return meta


def check(cfg, best: str, cand: str) -> dict:
    """{"ok", "failed": [...], "slower": [...]} for the candidate against the current best."""
    fh = harness(cfg)
    if fh is None:
        return {"ok": True, "skipped": True}
    f = settings(cfg)
    meta = setup(cfg)
    unstable = set(meta.get("unstable", []))
    insts = _instances(fh)
    with machine_lock(fh.cfg.work):
        tb, fb = fh.run_pass(best, insts, "main", timed_runs=3, warmup_runs=1)
        tc, fc = fh.run_pass(cand, insts, "main", timed_runs=3, warmup_runs=1)
    best_failed = {x["instance"] for x in fb}
    failed = [{"instance": x["instance"], "reason": x["reason"][:300]} for x in fc
              if x["instance"] not in best_failed
              and not (x["instance"] in unstable and x["reason"].startswith("wrong result"))]
    factor, slack = f.get("max_slowdown", 2.0), f.get("abs_slack_ms", 20.0) / 1000
    slower = []
    for iid, runs in tc.items():
        if tb.get(iid):
            b, c = median(tb[iid]), median(runs)
            if c > factor * b and c - b > slack:
                slower.append({"instance": iid, "best_s": round(b, 4), "cand_s": round(c, 4)})
    return {"ok": not failed and not slower, "workload": fh.wl.name, "failed": failed, "slower": slower}
