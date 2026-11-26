"""Operator CLI: `bin/dbe <command>`.

    setup                    clone + build the baseline engine, generate data, reference results
    split                    show which templates are train / val / test
    baseline                 time the unmodified engine on every split
    calibrate                A/A runs to measure the noise floor used by the acceptance bar
    evolve [--run ID] ...    run (or resume) the evolution loop
    status [--run ID]        ledger summary of a run
    retime --run R [--from-run S] E   re-check and re-time a reviewed candidate (no agent calls)
    check <commit>           run the mechanical gates on any commit of the engine clone
    report [--run ID]        evaluate all released versions on all splits; tables and plots
    ablate --run ID          time each accepted change alone (on v0) and removed (from the last release)
    transfer --run ID        time the releases on another workload (e.g. --config config/tpcds.toml)
    specialize q09 q13 ...   one run per template that specialises v0 to that template alone
    crosseval --prefix spec  time v0 and every specialised or merged system on all templates
    groups --cross DIR --k 1 2 4   group templates by the cross-evaluation (plus a random baseline)
    merge --name N --group q01,q09 combine the group's specialised systems into one engine
    merge-groups --k 1 2 3   merge every group chosen for those k
    curve --cross DIR        geomean speedup against the number of systems
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys

from . import bench, config, data, gates, loop, report
from .bench import Harness
from .engine import GIT_ID, Engine
from .loop import Loop, Run
from .util import append_jsonl, log, now, read_json, sh, write_json
from .workload import Workload


def _ctx(args):
    cfg = config.load(args.config)
    engine, wl = Engine(cfg), Workload(cfg)
    return cfg, engine, wl, Harness(cfg, engine, wl)


def _latest_run(cfg) -> str:
    runs = sorted(p.name for p in cfg.runs.glob("*") if (p / "state.json").exists()) if cfg.runs.exists() else []
    if not runs:
        sys.exit("no runs yet: start one with `bin/dbe evolve`")
    return runs[-1]


def cmd_setup(args):
    cfg, engine, wl, h = _ctx(args)
    base = engine.setup()
    binary = engine.binary(base, log_file=cfg.work / "logs" / "baseline_build.log")
    log(f"baseline binary: {binary}")
    for name in cfg["datasets"]:
        data.ensure_dataset(cfg, wl, binary, name)
        data.ensure_db(cfg, wl, binary, base, name)
        sf = data.scale_factor(cfg, name)
        insts = [i for g in wl.gate_instances(sf).values() for i in g] + wl.instances("test", sf)
        h.ensure_references(insts, name)
        log(f"dataset {name}: reference results for {len(insts)} query instances")
    cmd_split(args)


def cmd_split(args):
    cfg, engine, wl, h = _ctx(args)
    for s, ts in wl.split.items():
        print(f"{s:<6}{len(ts):>3} templates: {' '.join(ts)}")


def cmd_baseline(args):
    cfg, engine, wl, h = _ctx(args)
    rep = report.write(h, {"v0": engine.base_sha()}, cfg.results / "baseline")
    v0 = rep["versions"]["v0"]
    for s, d in v0["splits"].items():
        print(f"{s:<6} geomean {1000 * d['geomean_s']:8.1f} ms   total {1000 * d['total_s']:8.0f} ms")
    print(f"wrong results: {len(v0['failures'])}   (details in {cfg.results / 'baseline'})")


def cmd_calibrate(args):
    cfg, engine, wl, h = _ctx(args)
    if args.templates:
        new = bench.calibrate_templates(h, args.templates, args.repeats)
        print("added per-template noise: " + ", ".join(f"{t} {100 * x:.1f}%" for t, x in sorted(new.items())))
        return
    cal = bench.calibrate(h, args.repeats)
    print(f"noise floor (A/A train geomean deviation): {100 * cal['noise']:.2f}%")
    print(f"validation noise (3 templates): {100 * cal['val_noise']:.2f}%")
    noisy = sorted(cal["template_noise"].items(), key=lambda kv: -kv[1])
    print("per-template noise (largest A/A deviation): " + ", ".join(f"{t} {100 * x:.1f}%" for t, x in noisy))
    print(f"bar: {loop.bar_text(cfg)}")


def cmd_evolve(args):
    cfg, engine, wl, h = _ctx(args)
    if args.backend:
        os.environ["DBE_AGENT_BACKEND"] = args.backend
    if bench.calibration(cfg) is None:
        log("no noise calibration found; running it first")
        bench.calibrate(h)
    if args.run and (cfg.runs / args.run / "state.json").exists():
        run = Run(cfg, args.run)
        log(f"resuming run {run.id}")
    else:
        run_id = args.run or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        engine.accept(engine.base_sha())  # a new run starts from the unmodified engine
        run = Run.create(cfg, run_id, engine.base_sha())
        if args.seed_from:
            seed_run(cfg, run, args.seed_from)
        log(f"started run {run.id}")
    Loop(cfg, run).evolve(args.generations, args.rounds)
    cmd_status(argparse.Namespace(config=args.config, run=run.id))


def seed_run(cfg, run: Run, source: str) -> None:
    """Carry the record of an earlier run into a new one: ledger, issue backlog, planner memory.
    The engine itself restarts from v0; only the knowledge carries over."""
    src = Run(cfg, source)
    shutil.copy(src.dir / "ledger.jsonl", run.dir / "ledger.jsonl")
    shutil.copy(src.dir / "issues.json", run.dir / "issues.json")
    note = (f"\n\n## Harness note (new run seeded from `{source}`)\n\n"
            "The measurement protocol changed after the experiments above: the benchmark data is larger, "
            "borderline results are re-timed, and the bar now accepts a change that makes some visible "
            "templates clearly faster (beyond their own noise) while nothing gets slower, instead of "
            "requiring a gain in the geomean over all templates. Ideas retired only at the old bar may be "
            "worth another look.\n")
    (run.dir / "memory.md").write_text((src.dir / "memory.md").read_text().rstrip() + note)
    run.state["experiments"] = src.state["experiments"]
    run.state["seeded_from"] = source
    run.save()
    log(f"seeded {run.id} with {len(src.ledger)} experiments from {source}")


def cmd_retime(args):
    """Re-check and re-time a candidate that already passed the gates and the review in some run.
    Correctness gates run again (the data may have changed); no agent is called."""
    cfg, engine, wl, h = _ctx(args)
    run = Run(cfg, args.run)
    src = Run(cfg, args.from_run or args.run)
    old = next(r for r in src.ledger if r["id"] == args.experiment)
    cand, best = old["candidate"], run.state["best_sha"]
    gates_ok = json.load(open(sorted((src.dir / "experiments" / args.experiment).glob("attempt-*/gates.json"))[-1]))
    if gates_ok.get("failed") or gates_ok.get("review", {}).get("verdict") != "approve":
        sys.exit(f"{args.experiment} did not pass the gates and the review; it cannot be re-timed")
    if engine.git("merge-base", cand, best) != best:
        sys.exit(f"{args.experiment}'s candidate is not based on the current best; it would need rebasing")
    run.state["experiments"] += 1
    exp_id = f"E{run.state['experiments']:04d}"
    edir = run.dir / "experiments" / exp_id
    rec = {"id": exp_id, "title": f"{old['title']} (re-timed {src.id}/{args.experiment})", "started": now(),
           "base": best, "candidate": cand, "outcome": "retired", "reasons": [], "attempts": 0, "cost_usd": 0.0,
           "summary": old.get("summary", ""), "notes": old.get("notes", ""),
           "note": f"Not a new implementation: {src.id}/{args.experiment}'s reviewed change, re-checked and re-timed "
                   "under the current protocol."}
    log(f"{exp_id}: re-checking {args.experiment} ({cand[:12]})")
    c = gates.correctness(h, cand)
    smoke = gates.smoke(h, cand)
    write_json(edir / "gates.json", {"correctness": c, "smoke": smoke})
    if not c["ok"] or smoke:
        rec["reasons"] = ["failed correctness gates when re-checked"]
    else:
        loop.time_and_decide(cfg, h, best, cand, edir, rec)
    rec["finished"] = now()
    if rec["outcome"] == "accepted":
        engine.accept(cand)
        run.state["best_sha"] = cand
        run.state["train_ratio_vs_base"] *= rec["train_ratio"]
    run.save()
    write_json(edir / "record.json", rec)
    append_jsonl(run.dir / "ledger.jsonl", rec)
    log(f"{exp_id}: {rec['outcome'].upper()} - {'; '.join(rec['reasons']) or 'cleared the bar'}")


def cmd_status(args):
    cfg = config.load(args.config)
    run = Run(cfg, args.run or _latest_run(cfg))
    st = run.state
    print(f"run {run.id}: generation {st['generation']}, round {st['round']}, {st['experiments']} experiments, "
          f"agent cost ${st['cost_usd']:.2f}")
    print(f"best {st['best_sha'][:12]}: visible geomean {1 / st['train_ratio_vs_base']:.3f}x vs v0; "
          f"releases: {', '.join(f'{k}={v[:10]}' for k, v in st['releases'].items())}")
    for r in run.ledger:
        ratio = f"{100 * (r['train_ratio'] - 1):+6.1f}%" if r.get("train_ratio") else "      -"
        print(f"  {r['id']} {r['outcome']:<9}{ratio}  {r['title'][:60]}  [{'; '.join(r['reasons'])[:90]}]")


def cmd_check(args):
    cfg, engine, wl, h = _ctx(args)
    base, cand = engine.base_sha(), engine.git("rev-parse", args.commit)
    out = {"path_policy": gates.path_policy(engine, base, cand),
           "static_audit": gates.static_audit(engine.diff(base, cand), wl.audit_patterns())}
    engine.binary(cand)
    out["correctness"] = gates.correctness(h, cand)
    out["smoke"] = gates.smoke(h, cand)
    write_json(cfg.work / "logs" / f"check-{cand[:12]}.json", out)
    ok = not out["path_policy"] and not out["static_audit"] and out["correctness"]["ok"] and not out["smoke"]
    for k, v in out.items():
        bad = (not v["ok"]) if isinstance(v, dict) else bool(v)
        print(f"{k:<14}{'FAIL' if bad else 'pass'}")
    return 0 if ok else 1


def cmd_report(args):
    cfg, engine, wl, h = _ctx(args)
    run = Run(cfg, args.run or _latest_run(cfg))
    releases = dict(run.state["releases"])
    if args.include_best and run.state["best_sha"] not in releases.values():
        releases["best"] = run.state["best_sha"]
    out = cfg.results / run.id
    rep = report.write(h, releases, out)
    print(report.markdown(rep))
    print(f"written to {out}")


def _accepted_commits(engine, run) -> list[tuple[str, str]]:
    """(experiment id, sha) of every accepted change between v0 and the last release, oldest first."""
    rel = run.state["releases"]
    last = rel[sorted(rel, key=lambda v: int(v[1:]))[-1]]
    out = engine.git("log", "--reverse", "--format=%H %s", f"{rel['v0']}..{last}")
    return [(line.split()[1].rstrip(":"), line.split()[0]) for line in out.splitlines() if line.strip()]


def cmd_ablate(args):
    """Each accepted change applied alone to v0, and removed alone from the last release."""
    cfg, engine, wl, h = _ctx(args)
    run = Run(cfg, args.run or _latest_run(cfg))
    rel = run.state["releases"]
    last_label = sorted(rel, key=lambda v: int(v[1:]))[-1]
    v0, last = rel["v0"], rel[last_label]
    slot = engine.slot(1)
    variants, skipped = {"v0": v0}, {}
    for eid, sha in _accepted_commits(engine, run):
        for kind, base, cmd in (("only", v0, ["cherry-pick", sha]), ("minus", last, ["revert", "--no-edit", sha])):
            label = f"{kind}-{eid}" if kind == "only" else f"{last_label}-minus-{eid}"
            engine.checkout(slot, base)
            code, _ = sh(["git", *GIT_ID, *cmd], cwd=slot, check=False)
            if code != 0:
                engine.git(cmd[0], "--abort", cwd=slot, check=False)
                skipped[label] = "does not apply cleanly (depends on another change)"
                log(f"{label}: skipped, {skipped[label]}")
                continue
            new = engine.git("rev-parse", "HEAD", cwd=slot)
            engine.git("tag", "-f", f"dbe/ablate/{run.id}/{label}", new)
            variants[label] = new
    variants[last_label] = last
    out = cfg.results / f"{run.id}-ablation"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "variants.json", {"variants": variants, "skipped": skipped})
    for label, sha in variants.items():
        engine.binary(sha, log_file=cfg.work / "logs" / f"ablate-{label}.log")
    rep = report.write(h, variants, out)
    print(report.markdown(rep))
    print(f"skipped: {skipped}" if skipped else "")
    print(f"written to {out}")


def cmd_transfer(args):
    """Time the releases of a run on this config's workload (data made by a build that links its generator)."""
    cfg, engine, wl, h = _ctx(args)
    run_cfg = config.load()  # the run itself lives under the default config's paths
    run = Run(run_cfg, args.run or _latest_run(run_cfg))
    releases = dict(run.state["releases"])
    ext = list(dict.fromkeys(cfg["engine"]["extensions"] + [wl.name]))
    gen_cfg = config.load(args.config)
    gen_cfg.data["engine"]["extensions"] = ext
    gen = Engine(gen_cfg)
    slot = engine.slot(0)
    engine.checkout(slot, releases["v0"])
    ok, out, gen_binary = gen.build(slot, f"datagen-{wl.name}", cfg.work / "logs" / f"datagen-{wl.name}.log")
    if not ok:
        sys.exit(f"build with the {wl.name} generator failed:\n{out}")
    data.ensure_dataset(cfg, wl, gen_binary, "main")
    out_dir = cfg.results / (args.out or f"{run.id}-{wl.name}")
    rep = report.write(h, releases, out_dir)
    print(report.markdown(rep))
    print(f"written to {out_dir}")


def spec_config(base, template: str, prefix: str = "spec"):
    """Config for the specialisation run of one template: its own branch, tags and visible set."""
    return config.derive(base, {"workload": {"focus": template},
                                "engine": {"branch": f"dbe/{prefix}/{template}", "tag_prefix": f"dbe/{prefix}/{template}"}},
                         base.work / "configs" / f"{prefix}-{template}.toml")


def cmd_specialize(args):
    base = config.load(args.config)
    for t in args.templates:
        cfg = spec_config(base, t, args.prefix)
        sub = argparse.Namespace(config=str(cfg.path), run=f"{args.prefix}-{t}", generations=1,
                                 rounds=args.rounds, backend=args.backend, seed_from=None)
        log(f"### specialising for {t} ({args.rounds} rounds) with {cfg.path}")
        cmd_evolve(sub)


def _system_sha(run: Run) -> str:
    st = run.state
    return st.get("merged_sha") or st["best_sha"] if "merge" in st else st["best_sha"]


def cmd_crosseval(args):
    cfg, engine, wl, h = _ctx(args)
    runs = sorted(p.name for p in cfg.runs.glob(f"{args.prefix}-*") if (p / "state.json").exists())
    if args.also:
        runs += [r for r in args.also.split(",") if r]
    if args.with_merges:
        runs += sorted(p.name for pat in ("merge-agent-*", "merge-random-*", "merge-cluster-*")
                       for p in cfg.runs.glob(pat) if (p / "state.json").exists())
    base = engine.base_sha()
    systems, same = {"v0": base}, []
    for rid in runs:
        sha = _system_sha(Run(cfg, rid))
        label = (rid[len(args.prefix) + 1:] if rid.startswith(args.prefix + "-")
                 else rid[len("merge-"):] if rid.startswith("merge-") else rid)
        (same.append(label) if sha == base else systems.__setitem__(label, sha))
    out = cfg.results / args.out
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "systems.json", {"systems": systems, "unchanged_from_v0": same, "runs": runs})
    log(f"cross-evaluating {len(systems) - 1} systems ({', '.join(list(systems)[1:])}); unchanged: {same or 'none'}")
    rep = report.write(h, systems, out)
    print(report.markdown(rep))
    print(f"written to {out}")


def _spec_material(cfg, prefix: str, templates: list[str], cross: dict | None) -> tuple[dict, str]:
    """Patches and a summary of every specialised system, for the grouper agent."""
    engine = Engine(cfg)
    base = engine.base_sha()
    patches, parts = {}, ["# Specialised systems", ""]
    for t in templates:
        run = Run(cfg, f"{prefix}-{t}")
        sha = run.state["best_sha"]
        own = (cross or {}).get(t)
        parts.append(f"## {t}")
        parts.append(f"- Speedup on {t} with its own system: " + (f"{own:.2f}x" if own else "not measured"))
        if sha == base:
            parts += ["- No accepted change: this system is the original engine.", ""]
            continue
        patches[t] = engine.diff(base, sha)
        parts.append(f"- Files: {', '.join(sorted({l[6:] for l in patches[t].splitlines() if l.startswith('+++ b/')}))}")
        for r in run.ledger:
            if r["outcome"] == "accepted":
                parts.append(f"- {r['id']} {r['title']}: {r.get('summary', '')[:1200]}")
        parts.append("")
    return patches, "\n".join(parts)


def agent_groups(cfg, prefix: str, templates: list[str], k: int, cross: dict | None, out_dir) -> dict:
    """Ask an agent to split the templates into k groups whose diffs merge well."""
    from .agents import GROUPER_SCHEMA, make
    from .loop import render
    wd = cfg.work / "grouping" / f"{prefix}-k{k}"
    shutil.rmtree(wd, ignore_errors=True)
    (wd / "patches").mkdir(parents=True)
    patches, md = _spec_material(cfg, prefix, templates, cross)
    for t, p in patches.items():
        (wd / "patches" / f"{t}.patch").write_text(p)
    (wd / "systems.md").write_text(md)
    write_json(wd / "templates.json", templates)
    (wd / "k.txt").write_text(str(k))
    prompt = render("grouper", engine=cfg["engine"]["name"], n=len(templates), k=k, templates=", ".join(templates))
    agent, error = make(cfg), ""
    for attempt in range(2):
        res = agent.run("grouper", prompt + error, wd, GROUPER_SCHEMA, cfg["agents"]["planner_budget_usd"],
                        out_dir / f"grouper-k{k}-{attempt + 1}")
        if not res.ok:
            error = f"\n\nYour previous answer failed: {res.error[:300]}"
            continue
        groups = [sorted(g) for g in res.output["groups"] if g]
        flat = [t for g in groups for t in g]
        if len(groups) == k and sorted(flat) == sorted(templates):
            return {"groups": sorted(groups), "rationale": res.output["rationale"], "cost_usd": res.cost_usd}
        error = (f"\n\nYour previous answer was invalid: it must be exactly {k} non-empty groups that together "
                 f"contain each of {templates} exactly once. You returned {res.output['groups']}.")
    raise RuntimeError(f"grouper failed for k={k}: {error.strip()}")


def cmd_groups(args):
    """Choose the groups for k = 1, 2, 4, ... systems. Default: an agent reads the diffs and decides.
    `--method cluster` uses the cross-evaluation matrix instead; a seeded random grouping is always
    written alongside as a baseline."""
    from . import study
    cfg = config.load(args.config)
    templates = sorted(args.templates or [p.name[len(args.prefix) + 1:] for p in cfg.runs.glob(f"{args.prefix}-q*")
                                          if (p / "state.json").exists()])
    out = cfg.results / args.cross
    out.mkdir(parents=True, exist_ok=True)
    rep = read_json(out / "report.json")
    own = None
    if rep:
        m = study.matrix(rep, [s for s in rep["versions"]])
        own = {t: m[t][t] for t in templates if t in m}
    result = read_json(out / "groups.json", {"templates": templates, "k": {}})
    for k in args.k:
        entry = result["k"].setdefault(str(k), {})
        entry["random"] = study.random_groups(templates, k, seed=args.seed + k)
        if k >= len(templates):
            entry["agent"] = [[t] for t in templates]
            continue
        if args.method == "agent":
            entry["agent"] = agent_groups(cfg, args.prefix, templates, k, own, out)
            log(f"k={k}: {entry['agent']['groups']}")
        else:
            if not rep:
                sys.exit("--method cluster needs a cross-evaluation first (bin/dbe crosseval)")
            owner = {t: t if t in rep["versions"] else "v0" for t in templates}
            entry["cluster"] = study.cluster(templates, study.similarity(m, owner), k)
        write_json(out / "groups.json", result)
    print(json.dumps(result, indent=1))


def cmd_merge(args):
    base_cfg = config.load(args.config)
    group = sorted(args.group.split(","))
    cfg = config.derive(base_cfg, {"workload": {"focus": group},
                                   "engine": {"branch": f"dbe/merge/{args.name}", "tag_prefix": f"dbe/merge/{args.name}"}},
                        base_cfg.work / "configs" / f"merge-{args.name}.toml")
    engine = Engine(cfg)
    sources = {t: Run(cfg, f"{args.prefix}-{t}").state["best_sha"] for t in group}
    rid = f"merge-{args.name}"
    if (cfg.runs / rid / "state.json").exists():
        sys.exit(f"run {rid} exists already")
    engine.accept(engine.base_sha())
    run = Run.create(cfg, rid, engine.base_sha())
    rec = Loop(cfg, run).merge(sources)
    log(f"merge {args.name}: {rec.get('outcome', 'nothing to merge')}; merged sha "
        f"{(run.state.get('merged_sha') or '-')[:12]}")


def cmd_merge_groups(args):
    """Merge every group chosen for each k (runs `merge-k<k>-g<i>`)."""
    cfg = config.load(args.config)
    groups = read_json(cfg.results / args.cross / "groups.json")
    for k in args.k:
        entry = groups["k"].get(str(k))
        if entry is None:  # k = number of templates: the specialised systems themselves
            log(f"k={k}: no groups to merge (one system per template)")
            continue
        chosen = entry[args.method]
        chosen = chosen["groups"] if isinstance(chosen, dict) else chosen
        for i, g in enumerate(chosen, 1):
            name = f"{args.method}-k{k}-g{i}"
            if len(g) == 1:
                log(f"{name}: single template {g[0]}; its specialised system is used as is")
                continue
            if (cfg.runs / f"merge-{name}" / "state.json").exists():
                log(f"{name}: merged already")
                continue
            cmd_merge(argparse.Namespace(config=args.config, name=name, group=",".join(g), prefix=args.prefix))


def cmd_curve(args):
    """Speedup vs the number of systems: each template runs on the system of its group."""
    from . import study
    cfg = config.load(args.config)
    out = cfg.results / args.cross
    rep = read_json(out / "report.json")
    groups = read_json(cfg.results / args.groups / "groups.json")
    m = study.matrix(rep, list(rep["versions"]))
    templates = groups["templates"]
    same = set(read_json(out / "systems.json", {}).get("unchanged_from_v0", []))
    rows = []
    for method in ("agent", "random", "cluster"):
        for k, entry in sorted(groups["k"].items(), key=lambda kv: int(kv[0])):
            chosen = entry.get(method)
            if chosen is None:
                continue
            chosen = chosen["groups"] if isinstance(chosen, dict) else chosen
            per = {}
            for i, g in enumerate(chosen, 1):
                system = g[0] if len(g) == 1 else f"{method}-k{k}-g{i}"
                for t in g:
                    # a system identical to v0 (nothing accepted, or nothing merged) runs at 1.0x
                    per[t] = (m[system].get(t, float("nan")) if system in m
                              else 1.0 if system in same else float("nan"))
            rows.append({"method": method, "k": int(k), "geomean": study.summary(per), "per_template": per})
    own = {t: m[t][t] if t in m else 1.0 for t in templates}
    joint = {t: m["sf10"][t] for t in templates} if "sf10" in m else {}
    res = {"specialised": study.summary(own), "joint_evolution": study.summary(joint) if joint else None,
           "rows": rows, "noise": rep["noise"]}
    write_json(out / "curve.json", res)
    print(f"per-template systems (k = {len(templates)}): {res['specialised']:.3f}x")
    if joint:
        print(f"joint evolution on all TPC-H train templates (runs/sf10 v3): {res['joint_evolution']:.3f}x")
    for r in rows:
        print(f"{r['method']:<7} k={r['k']:<3} {r['geomean']:.3f}x")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dbe", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="path to a TOML config (default: config/default.toml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    sub.add_parser("split").set_defaults(fn=cmd_split)
    sub.add_parser("baseline").set_defaults(fn=cmd_baseline)
    p = sub.add_parser("calibrate")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--templates", nargs="*", help="only measure these templates' noise and add it")
    p.set_defaults(fn=cmd_calibrate)
    p = sub.add_parser("evolve")
    p.add_argument("--run", help="run id to create or resume")
    p.add_argument("--generations", type=int)
    p.add_argument("--rounds", type=int, help="rounds per generation")
    p.add_argument("--backend", choices=["claude-cli", "mock"], help="override agents.backend")
    p.add_argument("--seed-from", help="new runs only: carry over the ledger, issues and memory of this run")
    p.set_defaults(fn=cmd_evolve)
    p = sub.add_parser("status")
    p.add_argument("--run")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("retime", help="re-check and re-time a reviewed candidate (no agent calls)")
    p.add_argument("--run", required=True, help="run to record the result in")
    p.add_argument("--from-run", help="run the experiment came from (default: --run)")
    p.add_argument("experiment", help="experiment id, e.g. E0004")
    p.set_defaults(fn=cmd_retime)
    p = sub.add_parser("check")
    p.add_argument("commit")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("report")
    p.add_argument("--run")
    p.add_argument("--include-best", action="store_true", help="also evaluate the unreleased current best")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("ablate")
    p.add_argument("--run")
    p.set_defaults(fn=cmd_ablate)
    p = sub.add_parser("specialize")
    p.add_argument("templates", nargs="+")
    p.add_argument("--rounds", type=int, default=6)
    p.add_argument("--prefix", default="spec")
    p.add_argument("--backend")
    p.set_defaults(fn=cmd_specialize)
    p = sub.add_parser("crosseval")
    p.add_argument("--prefix", default="spec")
    p.add_argument("--also", help="comma-separated extra run ids (e.g. merge runs)")
    p.add_argument("--with-merges", action="store_true", help="also every merge-agent/random/cluster run")
    p.add_argument("--out", default="spec-cross")
    p.set_defaults(fn=cmd_crosseval)
    p = sub.add_parser("groups")
    p.add_argument("templates", nargs="*", help="default: every template with a specialised run")
    p.add_argument("--method", choices=["agent", "cluster"], default="agent")
    p.add_argument("--prefix", default="spec")
    p.add_argument("--cross", default="spec-cross")
    p.add_argument("--k", type=int, nargs="+", default=[1, 2, 4, 8])
    p.add_argument("--seed", type=int, default=20261119)
    p.set_defaults(fn=cmd_groups)
    p = sub.add_parser("merge")
    p.add_argument("--name", required=True)
    p.add_argument("--group", required=True, help="comma-separated templates")
    p.add_argument("--prefix", default="spec")
    p.set_defaults(fn=cmd_merge)
    p = sub.add_parser("merge-groups")
    p.add_argument("--k", type=int, nargs="+", required=True)
    p.add_argument("--method", choices=["agent", "random", "cluster"], default="agent")
    p.add_argument("--prefix", default="spec")
    p.add_argument("--cross", default="spec-cross")
    p.set_defaults(fn=cmd_merge_groups)
    p = sub.add_parser("curve")
    p.add_argument("--cross", default="spec-cross-merged", help="cross-evaluation that includes the merged systems")
    p.add_argument("--groups", default="spec-cross", help="where `groups` wrote groups.json")
    p.set_defaults(fn=cmd_curve)
    p = sub.add_parser("transfer")
    p.add_argument("--run")
    p.add_argument("--out", help="results subdirectory (default <run>-<workload>)")
    p.set_defaults(fn=cmd_transfer)
    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
