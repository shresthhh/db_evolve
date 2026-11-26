"""Correctness checks and timing: reference results, interleaved A/B passes, the acceptance bar."""
from __future__ import annotations

import time
from pathlib import Path

from . import compare, data
from .config import Config
from .engine import Engine
from .session import EngineError, Session
from .util import geomean, log, machine_lock, median, read_json, write_json
from .workload import Instance, Workload


class Harness:
    def __init__(self, cfg: Config, engine: Engine, wl: Workload):
        self.cfg, self.engine, self.wl = cfg, engine, wl
        self.b = cfg["bench"]

    # --- plumbing ------------------------------------------------------------
    def session(self, target, dataset: str) -> Session:
        """`target` is a commit sha, or a (binary, db) pair for an uncommitted working-tree build."""
        if isinstance(target, tuple):
            binary, db = target
        else:
            binary = self.engine.binary(target)
            db = data.ensure_db(self.cfg, self.wl, binary, target, dataset)
        return Session(binary, db, self.b["threads"], timeout=self.b["statement_timeout_s"])

    def instances(self, split: str, dataset: str = "main", heldout: bool = False) -> list[Instance]:
        if self.wl.item_datasets:   # scale-factor mode: every instance carries its own dataset
            return self.wl.instances(split, 0.0, heldout=heldout)
        return self.wl.instances(split, data.scale_factor(self.cfg, dataset), heldout=heldout)

    # --- reference results ---------------------------------------------------
    def _ref_path(self, inst: Instance, dataset: str) -> Path:
        return self.cfg.refs / self.wl.name / data.tag(self.cfg, inst.dataset or dataset) / f"{inst.key}.csv"

    def ensure_references(self, instances: list[Instance], dataset: str) -> None:
        missing = [i for i in instances if not self._ref_path(i, dataset).exists()]
        by_ds: dict[str, list[Instance]] = {}
        for i in missing:
            by_ds.setdefault(i.dataset or dataset, []).append(i)
        for ds, insts in by_ds.items():
            self._make_references(insts, ds)

    def _make_references(self, missing: list[Instance], dataset: str) -> None:
        with self.session(self.engine.base_sha(), dataset) as s:
            for inst in missing:
                _, out = s.run(inst.sql)
                p = self._ref_path(inst, dataset)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(out)

    def reference(self, inst: Instance, dataset: str) -> str:
        return self._ref_path(inst, dataset).read_text()

    # --- one pass over a set of instances -----------------------------------
    def run_pass(self, target, instances: list[Instance], dataset: str, timed_runs: int,
                 warmup_runs: int) -> tuple[dict, list]:
        """Returns ({instance_id: [seconds, ...]}, [failure, ...]). Every run's output is verified.
        Instances that name their own dataset (scale-factor mode) run on it, one session per dataset."""
        groups: dict[str, list[Instance]] = {}
        for inst in instances:
            groups.setdefault(inst.dataset or dataset, []).append(inst)
        times: dict[str, list[float]] = {}
        failures: list[dict] = []
        for ds, insts in groups.items():
            t, f = self._run_pass_one(target, insts, ds, timed_runs, warmup_runs)
            times.update(t)
            failures.extend(f)
        return times, failures

    def _run_pass_one(self, target, instances: list[Instance], dataset: str, timed_runs: int,
                      warmup_runs: int) -> tuple[dict, list]:
        self.ensure_references(instances, dataset)
        times: dict[str, list[float]] = {}
        failures: list[dict] = []
        s = self.session(target, dataset)
        try:
            for inst in instances:
                want = self.reference(inst, dataset)
                try:
                    runs = []
                    for k in range(warmup_runs + timed_runs):
                        elapsed, out = s.run(inst.sql)
                        if out != want:
                            ok, why = compare.equal(out, want)
                            if not ok:
                                raise EngineError(f"wrong result: {why}")
                        if k >= warmup_runs:
                            runs.append(elapsed)
                    times[inst.id] = runs
                except EngineError as e:
                    failures.append({"instance": inst.id, "template": inst.item, "split": inst.split,
                                     "kind": inst.kind, "dataset": dataset, "reason": str(e)[:1500]})
                    if s.p.poll() is not None:  # crashed or timed out: start a fresh process
                        s.close()
                        s = self.session(target, dataset)
        finally:
            s.close()
        return times, failures

    def check(self, sha: str, instances: list[Instance], dataset: str) -> list[dict]:
        """Correctness only (one untimed execution per instance)."""
        with machine_lock(self.cfg.work):
            return self.run_pass(sha, instances, dataset, timed_runs=1, warmup_runs=0)[1]

    # --- interleaved timing ----------------------------------------------------
    def interleaved(self, shas: dict[str, str], order: str, instances: list[Instance],
                    dataset: str = "main", timed_runs: int | None = None) -> dict:
        """Run full passes in the given label order (e.g. "ABBA") so drift hits every binary equally.

        Returns {"times": {label: {instance_id: [seconds...]}}, "failures": {label: [...]}}.
        """
        timed_runs = timed_runs or self.b["timed_runs"]
        times = {label: {} for label in shas}
        failures = {label: [] for label in shas}
        with machine_lock(self.cfg.work):
            for label in order:
                t, f = self.run_pass(shas[label], instances, dataset, timed_runs, self.b["warmup_runs"])
                for iid, runs in t.items():
                    times[label].setdefault(iid, []).extend(runs)
                failures[label].extend(f)
        return {"times": times, "failures": failures}


# --- pure functions: summarising and deciding ---------------------------------

def template_times(times: dict[str, list[float]], instances: list[Instance]) -> dict[str, float]:
    """Seconds per template: mean over its instances of the median run."""
    per: dict[str, list[float]] = {}
    for inst in instances:
        if times.get(inst.id):
            per.setdefault(inst.item, []).append(median(times[inst.id]))
    return {t: sum(v) / len(v) for t, v in sorted(per.items())}


def summarize(times: dict[str, list[float]], instances: list[Instance]) -> dict:
    tt = template_times(times, instances)
    return {"templates": tt, "geomean_s": geomean(tt.values()), "total_s": sum(tt.values())}


def ratios(cand: dict[str, float], inc: dict[str, float]) -> dict[str, float]:
    return {t: cand[t] / inc[t] for t in inc if t in cand and inc[t] > 0}


def required_gain(bar: dict, noise: float) -> float:
    """Geomean rule only: the train geomean gain a candidate must reach."""
    return max(bar["min_gain"], bar["noise_multiplier"] * noise)


def decide(train_inc: dict[str, float], train_cand: dict[str, float],
           val_inc: dict[str, float], val_cand: dict[str, float], bar: dict, cal: dict) -> dict:
    """Apply the acceptance bar. Inputs are seconds per template (incumbent vs candidate) and the
    noise calibration. `bar["rule"]` picks the rule: "templates" (default) or "geomean"."""
    if bar.get("rule", "templates") == "geomean":
        return decide_geomean(train_inc, train_cand, val_inc, val_cand, bar, cal.get("noise", 0.0),
                              cal.get("val_noise"))
    return decide_templates(train_inc, train_cand, val_inc, val_cand, bar, cal)


def template_thresholds(bar: dict, cal: dict, t: str) -> tuple[float, float]:
    """(gain, regression) a template must exceed to count, given its own measured noise."""
    n = bar["noise_multiplier"] * cal.get("template_noise", {}).get(t, cal.get("worst_template_deviation", 0.0))
    return max(bar["min_template_gain"], n), max(bar["max_template_regression"], n)


def decide_templates(train_inc, train_cand, val_inc, val_cand, bar: dict, cal: dict) -> dict:
    """Accept when at least one visible template is faster beyond its own noise, no template
    (visible or hidden) is slower beyond its noise, the visible geomean is not slower, and the
    hidden validation geomean is not slower beyond its tolerance.

    Rationale: a geomean-only bar dilutes a large gain on one template below run-to-run noise
    (the pilot retired a change that made one template 21 % faster and slowed nothing)."""
    reasons, improved, regressed = [], [], []
    tr = ratios(train_cand, train_inc)
    for t, r in tr.items():
        gain, reg = template_thresholds(bar, cal, t)
        slower_ms = (train_cand[t] - train_inc[t]) * 1000
        if r <= 1 - gain:
            improved.append(t)
        elif r >= 1 + reg and slower_ms > bar["abs_slack_ms"]:
            regressed.append(t)
            reasons.append(f"{t} slower by {100 * (r - 1):.1f}% ({slower_ms:.0f} ms), beyond its "
                           f"{100 * reg:.1f}% threshold")
    if not improved:
        best = min(tr.items(), key=lambda kv: kv[1]) if tr else ("-", 1.0)
        need = template_thresholds(bar, cal, best[0])[0] if tr else bar["min_template_gain"]
        reasons.append(f"no visible template faster beyond its noise (best: {best[0]} "
                       f"{100 * (best[1] - 1):+.1f}%; needs at least -{100 * need:.1f}%)")
    train_ratio = geomean(tr.values())
    if train_ratio > 1 + bar["max_geomean_regression"]:
        reasons.append(f"visible geomean got slower ({100 * (train_ratio - 1):+.1f}%)")
    vr = ratios(val_cand, val_inc)
    val_ratio = geomean(vr.values()) if vr else float("nan")
    val_limit = 1 + max(bar["val_tolerance"], bar["noise_multiplier"] * cal.get("val_noise", cal.get("noise", 0.0)))
    val_slow = [t for t, r in vr.items() if r >= 1 + template_thresholds(bar, cal, t)[1]
                and (val_cand[t] - val_inc[t]) * 1000 > bar["abs_slack_ms"]]
    val_ok = not vr or (val_ratio <= val_limit and not val_slow)
    if not val_ok:  # never name hidden templates: this text reaches the agents
        reasons.append("hidden validation templates got slower than their noise allows")
    return {"accept": not reasons, "reasons": reasons, "rule": "templates", "train_ratio": train_ratio,
            "val_ratio": val_ratio, "val_ok": val_ok, "improved": improved, "regressed": regressed,
            "required_gain": bar["min_template_gain"], "train_template_ratios": tr}


def decide_geomean(train_inc, train_cand, val_inc, val_cand, bar: dict, noise: float,
                   val_noise: float | None = None) -> dict:
    """The original rule: the train geomean must improve beyond the noise floor."""
    reasons = []
    tr = ratios(train_cand, train_inc)
    train_ratio = geomean(tr.values())
    need = required_gain(bar, noise)
    if not train_ratio <= 1 - need:
        reasons.append(f"train geomean changed by {100 * (train_ratio - 1):+.1f}%; the bar requires at least "
                       f"-{100 * need:.1f}%")
    for t, r in tr.items():
        slower_ms = (train_cand[t] - train_inc[t]) * 1000
        if r > 1 + bar["max_template_regression"] and slower_ms > bar["abs_slack_ms"]:
            reasons.append(f"{t} regressed by {100 * (r - 1):.0f}% ({slower_ms:.1f} ms)")
    vr = ratios(val_cand, val_inc)
    val_ratio = geomean(vr.values()) if vr else float("nan")
    val_limit = 1 + max(bar["val_tolerance"], bar["noise_multiplier"] * (noise if val_noise is None else val_noise))
    val_ok = not vr or val_ratio <= val_limit
    if not val_ok:
        reasons.append("hidden validation templates got slower than the tolerance allows")
    return {"accept": not reasons, "reasons": reasons, "rule": "geomean", "train_ratio": train_ratio,
            "val_ratio": val_ratio, "val_ok": val_ok, "required_gain": need, "train_template_ratios": tr}


def borderline(d: dict, bar: dict) -> bool:
    """A retired decision worth re-timing: some visible template moved at least half the way to a gain."""
    return not d["accept"] and any(r <= 1 - bar["min_template_gain"] / 2 for r in d["train_template_ratios"].values())


# --- noise calibration ------------------------------------------------------------

def _cal_path(cfg: Config) -> Path:
    ds = cfg["workload"].get("datasets")
    tag = "items-" + "-".join(data.tag(cfg, d) for d in ds) if ds else data.tag(cfg, "main")
    return cfg.work / f"calibration-{tag}.json"


def calibrate(h: Harness, repeats: int = 3) -> dict:
    """A/A experiment: the baseline against itself, with the same protocol as a decision.

    Records the geomean deviation per split and, per template, the largest deviation seen.
    """
    base = h.engine.base_sha()
    train, val = h.instances("train"), h.instances("val")
    samples, val_samples, per_t, seconds = [], [], {}, []
    for k in range(repeats):
        t0 = time.time()
        r = h.interleaved({"A": base, "B": base}, h.b["ab_order"], train + val)
        a, b = r["times"]["A"], r["times"]["B"]
        rs = ratios(template_times(b, train), template_times(a, train))
        vs = ratios(template_times(b, val), template_times(a, val))
        samples.append(abs(geomean(rs.values()) - 1))
        val_samples.append(abs(geomean(vs.values()) - 1))
        for t, x in {**rs, **vs}.items():
            per_t[t] = max(per_t.get(t, 0.0), abs(x - 1))
        seconds.append(round(time.time() - t0))
        log(f"calibration {k + 1}/{repeats}: A/A train geomean {100 * samples[-1]:.2f}%, "
            f"worst template {100 * max(abs(x - 1) for x in rs.values()):.1f}%, took {seconds[-1]} s")
    out = {"dataset": data.tag(h.cfg, "main"), "noise": max(samples), "val_noise": max(val_samples),
           "samples": samples, "template_noise": per_t, "worst_template_deviation": max(per_t.values()),
           "threads": h.b["threads"], "order": h.b["ab_order"], "repeats": repeats,
           "seconds_per_repeat": seconds}
    write_json(_cal_path(h.cfg), out)
    return out


def calibrate_templates(h: Harness, templates: list[str], repeats: int = 4) -> dict:
    """A/A noise for extra templates (e.g. ones that were only ever in the test split), merged into
    the existing calibration without changing its split-level numbers."""
    base = h.engine.base_sha()
    insts = [i for s in ("train", "val", "test") for i in h.instances(s) if i.item in templates]
    cal = calibration(h.cfg) or {}
    per_t = dict(cal.get("template_noise", {}))
    new = {}
    for k in range(repeats):
        r = h.interleaved({"A": base, "B": base}, h.b["ab_order"], insts)
        rs = ratios(template_times(r["times"]["B"], insts), template_times(r["times"]["A"], insts))
        for t, x in rs.items():
            new[t] = max(new.get(t, 0.0), abs(x - 1))
        log(f"template calibration {k + 1}/{repeats}: " + ", ".join(f"{t} {100 * abs(x - 1):.1f}%" for t, x in rs.items()))
    per_t.update(new)
    cal["template_noise"] = per_t
    write_json(_cal_path(h.cfg), cal)
    return new


def calibration(cfg: Config) -> dict | None:
    return read_json(_cal_path(cfg))


def noise_floor(cfg: Config, key: str = "noise") -> float:
    cal = calibration(cfg)
    return cal.get(key, cal["noise"]) if cal else 0.0
