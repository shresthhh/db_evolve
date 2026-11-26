"""The evolution loop.

Outer loop (per round): profile the current best -> planner files issues and picks what to run.
Inner loop (per experiment): implementer -> mechanical gates -> independent reviewer -> interleaved
A/B timing against the current best -> accept or retire, with a written reason in the ledger.
A generation ends by tagging the current best as a release (v1, v2, ...).
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from . import agents, bench, gates
from .agents import IMPLEMENTER_SCHEMA, PLANNER_SCHEMA, REVIEWER_SCHEMA, TOOL
from .bench import Harness
from .config import ROOT, Config
from .engine import GIT_ID, Engine
from .session import EngineError
from .util import append_jsonl, log, now, read_json, read_jsonl, sh, write_json
from .workload import Workload

PROMPTS = Path(__file__).parent / "prompts"
KNOWLEDGE = ROOT / "knowledge"


def render(name: str, **kw) -> str:
    text = (PROMPTS / f"{name}.md").read_text()
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


class Run:
    """Persistent state of one evolution run, under runs/<id>/."""

    def __init__(self, cfg: Config, run_id: str):
        self.dir = cfg.runs / run_id
        self.id = run_id
        self.state_path = self.dir / "state.json"
        self.state = read_json(self.state_path)
        if self.state is None:
            raise FileNotFoundError(f"no such run: {run_id}")

    @classmethod
    def create(cls, cfg: Config, run_id: str, base_sha: str) -> "Run":
        d = cfg.runs / run_id
        d.mkdir(parents=True, exist_ok=False)
        write_json(d / "state.json", {"run_id": run_id, "created": now(), "base_sha": base_sha,
                                      "best_sha": base_sha, "generation": 1, "round": 0, "experiments": 0,
                                      "train_ratio_vs_base": 1.0, "cost_usd": 0.0,
                                      "releases": {"v0": base_sha}, "config": cfg.data})
        (d / "memory.md").write_text("# Memory\n\n(empty: first round)\n")
        write_json(d / "issues.json", [])
        return cls(cfg, run_id)

    def save(self) -> None:
        write_json(self.state_path, self.state)

    # issues ---------------------------------------------------------------
    @property
    def issues(self) -> list[dict]:
        return read_json(self.dir / "issues.json", [])

    def save_issues(self, issues: list[dict]) -> None:
        write_json(self.dir / "issues.json", issues)

    def issues_md(self) -> str:
        open_ = [i for i in self.issues if i["status"] == "open"]
        if not open_:
            return "# Open issues\n\n(none)\n"
        parts = ["# Open issues\n"]
        for i in open_:
            parts.append(f"## {i['title']}\n\n- Hypothesis: {i['hypothesis']}\n- Plan: {i['plan']}\n"
                         f"- Target files: {', '.join(i['target_files'])}\n- Expected gain: {i['expected_gain']}\n"
                         f"- Generality: {i['generality']}\n- Risk: {i['risk']}\n")
        return "\n".join(parts)

    # ledger ---------------------------------------------------------------
    @property
    def ledger(self) -> list[dict]:
        return read_jsonl(self.dir / "ledger.jsonl")

    def ledger_md(self) -> str:
        """The shared record as agents see it. Hidden-split numbers are reduced to pass/fail."""
        rows = self.ledger
        if not rows:
            return "# Experiment ledger\n\n(no experiments yet)\n"
        parts = ["# Experiment ledger\n"]
        for r in rows:
            parts.append(f"## {r['id']}: {r['title']} [{r['outcome'].upper()}]\n")
            if r.get("train_ratio"):
                if r.get("rule") == "templates":
                    parts.append(f"- Visible geomean: {100 * (r['train_ratio'] - 1):+.1f}%; faster beyond noise: "
                                 f"{', '.join(r.get('improved') or []) or 'none'}; slower beyond noise: "
                                 f"{', '.join(r.get('regressed') or []) or 'none'}; hidden validation: "
                                 f"{'ok' if r.get('val_ok', True) else 'REGRESSED'}")
                else:
                    parts.append(f"- Visible geomean: {100 * (r['train_ratio'] - 1):+.1f}% "
                                 f"(needed {-100 * r.get('required_gain', 0):.1f}% under the old geomean bar); "
                                 f"hidden validation: {'ok' if r.get('val_ok', True) else 'REGRESSED'}")
            if r.get("note"):
                parts.append(f"- Harness note: {r['note']}")
                moved = sorted(r.get("train_template_ratios", {}).items(), key=lambda kv: kv[1])
                moved = [f"{t} {100 * (x - 1):+.0f}%" for t, x in moved if abs(x - 1) >= 0.03]
                if moved:
                    parts.append(f"- Templates that moved: {', '.join(moved)}")
            parts.append(f"- Reason: {'; '.join(r['reasons']) or 'cleared the bar'}")
            if r.get("summary"):
                parts.append(f"- Implementer summary: {r['summary']}")
            if r.get("notes"):
                parts.append(f"- Implementer notes: {r['notes']}")
            parts.append("")
        return "\n".join(parts)


class Loop:
    def __init__(self, cfg: Config, run: Run):
        self.cfg, self.run = cfg, run
        self.engine = Engine(cfg)
        self.wl = Workload(cfg)
        self.h = Harness(cfg, self.engine, self.wl)
        self.agent = agents.make(cfg)
        self.a = cfg["agents"]
        self.slot = self.engine.slot(0)

    # --- every agent call goes through here so the run-level budget is enforced -----
    def remaining(self) -> float:
        cap = self.a.get("max_total_usd")
        return float("inf") if not cap else cap - self.run.state["cost_usd"]

    def call(self, role: str, prompt: str, schema: dict, role_budget: float, log_dir: Path,
             writable: bool = False) -> agents.AgentResult:
        left = self.remaining()
        if left < 0.5:
            return agents.AgentResult(False, error="run budget exhausted")
        budget = round(min(role_budget, left), 2)
        prompt = prompt.replace("{{budget}}", f"{budget:.2f}")
        res = self.agent.run(role, prompt, self.slot, schema, budget, log_dir, writable=writable)
        self.run.state["cost_usd"] += res.cost_usd
        if getattr(res, "billing", "plan") == "api":   # real spend on the fallback key
            self.run.state["api_cost_usd"] = self.run.state.get("api_cost_usd", 0.0) + res.cost_usd
        self.run.save()
        return res

    # --- context handed to agents (files under <slot>/.dbe/) -----------------------
    def write_context(self, extra: dict[str, str] | None = None) -> Path:
        exclude = self.engine.repo / ".git" / "info" / "exclude"
        if ".dbe/" not in (exclude.read_text() if exclude.exists() else ""):
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with open(exclude, "a") as f:
                f.write(".dbe/\n")
        ctx = self.slot / ".dbe"
        shutil.rmtree(ctx, ignore_errors=True)
        shutil.copytree(KNOWLEDGE, ctx / "knowledge")
        (ctx / "queries").mkdir()
        for inst in self.h.instances("train"):
            (ctx / "queries" / f"{inst.id}.sql").write_text(inst.sql + ";\n")
        files = {"ledger.md": self.run.ledger_md(), "issues.md": self.run.issues_md(),
                 "memory.md": (self.run.dir / "memory.md").read_text(),
                 "profile.md": (self.run.dir / "profile.md").read_text() if (self.run.dir / "profile.md").exists() else ""}
        files.update(extra or {})
        for name, text in files.items():
            (ctx / name).parent.mkdir(parents=True, exist_ok=True)
            (ctx / name).write_text(text)
        return ctx

    # --- profile of the current best -----------------------------------------------
    def profile(self) -> str:
        best = self.run.state["best_sha"]
        train = self.h.instances("train")
        r = self.h.interleaved({"A": best}, "A", train, timed_runs=3)
        tt = bench.template_times(r["times"]["A"], train)
        total = sum(tt.values())
        lines = ["# Profile of the current best build", "",
                 f"Visible templates, hot runs, {self.h.b['threads']} threads. Geomean "
                 f"{1000 * bench.geomean(tt.values()):.1f} ms, total {1000 * total:.0f} ms.", "",
                 "| Template | Time (ms) | Share of total |", "| --- | ---: | ---: |"]
        ranked = sorted(tt.items(), key=lambda kv: -kv[1])
        lines += [f"| {t} | {1000 * s:.1f} | {100 * s / total:.1f}% |" for t, s in ranked]
        lines += ["", "## Plans with operator timings (slowest templates)", ""]
        with self.h.session(best, "main") as s:
            for t, _ in ranked[:4]:
                inst = next(i for i in train if i.template == t)
                lines += [f"### {inst.id}", "", "```sql", inst.sql, "```", "", "```", explain_analyze(s, inst.sql), "```", ""]
        text = "\n".join(lines)
        (self.run.dir / "profile.md").write_text(text)
        return text

    # --- outer loop -------------------------------------------------------------------
    def evolve(self, generations: int | None = None, rounds: int | None = None) -> None:
        lp = self.cfg["loop"]
        generations = generations or lp["generations"]
        rounds = rounds or lp["rounds_per_generation"]
        st = self.run.state
        if st.get("in_round"):
            self.undo_interrupted_round()
        while st["generation"] <= generations:
            while st["round"] < rounds and self.remaining() >= 0.5:
                st["round"] += 1
                st["in_round"] = True
                self.run.save()
                log(f"=== generation {st['generation']} round {st['round']}/{rounds} "
                    f"(best {st['best_sha'][:12]}, visible geomean x{1 / st['train_ratio_vs_base']:.3f}) ===")
                self.round(rounds)
                st["in_round"] = False
                self.run.save()
            self.engine.tag_release(st["generation"], st["best_sha"])
            st["releases"][f"v{st['generation']}"] = st["best_sha"]
            log(f"released v{st['generation']} = {st['best_sha'][:12]}")
            if self.remaining() < 0.5:
                log(f"run budget of ${self.a['max_total_usd']:.2f} is used up; stopping")
                self.run.save()
                return
            st["generation"] += 1
            st["round"] = 0
            self.run.save()

    def undo_interrupted_round(self) -> None:
        """The process died mid-round (reboot, kill): set the round's partial files aside and
        redo it. Experiments that reached the ledger stay; the rest are rerun from scratch."""
        st = self.run.state
        done = max((int(r["id"][1:]) for r in self.run.ledger), default=0)
        stash = self.run.dir / "interrupted" / time.strftime("%Y%m%d-%H%M%S")
        partial = [self.run.dir / "rounds" / f"g{st['generation']}r{st['round']:02d}"]
        partial += [d for d in sorted((self.run.dir / "experiments").glob("E*")) if int(d.name[1:]) > done]
        for d in partial:
            if d.exists():
                stash.mkdir(parents=True, exist_ok=True)
                shutil.move(str(d), str(stash / d.name))
        log(f"round {st['round']} of generation {st['generation']} was interrupted; redoing it "
            f"(partial files in {stash.relative_to(self.run.dir)})")
        st["experiments"] = done
        st["round"] = max(0, st["round"] - 1)
        st["in_round"] = False
        self.run.save()

    def round(self, rounds: int) -> None:
        st = self.run.state
        rdir = self.run.dir / "rounds" / f"g{st['generation']}r{st['round']:02d}"
        self.engine.checkout(self.slot, st["best_sha"])
        self.profile()
        self.write_context()
        n = self.cfg["loop"]["experiments_per_round"]
        prompt = render("planner", scope=scope_text(self.cfg), engine=self.engine.e["name"], threads=self.h.b["threads"], tool=TOOL,
                        dispatch=n, generation=st["generation"], round=st["round"], rounds=rounds,
                        speedup=f"{1 / st['train_ratio_vs_base']:.3f}x")
        res = self.call("planner", prompt, PLANNER_SCHEMA, self.a["planner_budget_usd"], rdir)
        if not res.ok:
            log(f"planner failed: {res.error}")
            return
        issues = self.run.issues
        known = {i["title"] for i in issues}
        for i in res.output["issues"]:
            if i["title"] not in known:
                issues.append({**i, "status": "open", "filed": f"g{st['generation']}r{st['round']}"})
        self.run.save_issues(issues)
        if res.output.get("memory", "").strip():
            (self.run.dir / "memory.md").write_text(res.output["memory"])
        for title in res.output["dispatch"][:n]:
            issue = next((i for i in issues if i["title"] == title and i["status"] == "open"), None)
            if issue is None:
                log(f"planner dispatched an unknown or closed issue: {title!r}")
                continue
            record = self.experiment(issue)
            issue["status"] = record["outcome"]
            issue["experiment"] = record["id"]
            self.run.save_issues(issues)

    # --- inner loop --------------------------------------------------------------------
    def experiment(self, issue: dict, start: str | None = None, extra: dict[str, str] | None = None) -> dict:
        """One experiment. `start` begins the worktree at another commit than the current best (the
        merge step starts from a mechanical merge); `extra` adds files to the agent's `.dbe/`."""
        st = self.run.state
        st["experiments"] += 1
        exp_id = f"E{st['experiments']:04d}"
        edir = self.run.dir / "experiments" / exp_id
        best = st["best_sha"]
        log(f"{exp_id}: {issue['title']}")
        write_json(edir / "issue.json", issue)
        rec = {"id": exp_id, "title": issue["title"], "started": now(), "base": best, "candidate": None,
               "outcome": "retired", "reasons": [], "attempts": 0, "cost_usd": 0.0, "summary": "", "notes": ""}
        issue_md = (f"### {issue['title']}\n\n**Hypothesis.** {issue['hypothesis']}\n\n**Plan.** {issue['plan']}\n\n"
                    f"**Target files.** {', '.join(issue['target_files'])}\n\n"
                    f"**Expected gain.** {issue['expected_gain']}\n\n**Generality.** {issue['generality']}\n\n"
                    f"**Risk.** {issue['risk']}")
        self.engine.checkout(self.slot, start or best)
        cand, feedback, passed = (start if start and start != best else None), "", False
        e = self.engine.e
        for attempt in range(1, self.a["max_fix_attempts"] + 2):
            rec["attempts"] = attempt
            adir = edir / f"attempt-{attempt}"
            self.write_context(extra)
            fb = "" if not feedback else ("## Feedback on your previous attempt\n\nYour earlier changes are still in "
                                          "the working tree. Fix the following and finish again.\n\n" + feedback)
            prompt = render("implementer", scope=scope_text(self.cfg), engine=e["name"], issue=issue_md, feedback=fb, tool=TOOL,
                            editable=", ".join(f"`{p}`" for p in e["editable_paths"]),
                            forbidden=", ".join(f"`{p}`" for p in e["forbidden_paths"]),
                            bar_text=bar_text(self.cfg))
            res = self.call("implementer", prompt, IMPLEMENTER_SCHEMA,
                            self.a["implementer_budget_usd"], adir, writable=True)
            rec["cost_usd"] += res.cost_usd
            if not res.ok:
                self.save_wip(adir)
                rec["reasons"].append(f"implementer run failed: {res.error[:300]}")
                break
            rec["summary"], rec["notes"] = res.output["summary"], res.output["notes"]
            if res.output["status"] == "abandon":
                self.save_wip(adir)
                rec["reasons"].append("abandoned by the implementer after investigation")
                break
            new = self.engine.commit_all(self.slot, f"{exp_id}: {issue['title']}\n\n{res.output['summary']}")
            if new is None and cand is None:
                rec["reasons"].append("implementer reported ready but changed nothing")
                break
            if new is None and attempt == 1 and cand == start:
                new = start  # merge accepted as merged mechanically
            if new is None:
                rec["reasons"].append("implementer made no further changes after feedback")
                break
            cand = rec["candidate"] = new
            feedback = self.gate(best, cand, adir, issue_md, res.output, rec)
            if feedback is None:
                passed = True
                break
            log(f"{exp_id} attempt {attempt}: sent back ({feedback.splitlines()[0][:100]})")
        else:
            rec["reasons"].append("still failing gates or review after the last allowed attempt")
        if passed:
            self.time_and_decide(best, cand, edir, rec)
        elif cand and not rec["reasons"]:
            rec["reasons"].append("did not pass the gates")
        rec["finished"] = now()
        if rec["outcome"] == "accepted":
            self.engine.accept(cand)
            st["best_sha"] = cand
            st["train_ratio_vs_base"] *= rec["train_ratio"]
        self.run.save()
        write_json(edir / "record.json", rec)
        append_jsonl(self.run.dir / "ledger.jsonl", rec)
        log(f"{exp_id}: {rec['outcome'].upper()} - {'; '.join(rec['reasons']) or 'cleared the bar'}")
        return rec

    # --- merging specialised systems ----------------------------------------------------
    def merge(self, sources: dict[str, str]) -> dict:
        """Combine the changes of several specialised systems (label -> best sha, all based on this run's
        base) into one engine: cherry-pick what applies cleanly, then let an agent reconcile the rest
        under the usual gates, review and timing. The result is released as v1 of this run."""
        st = self.run.state
        base = st["base_sha"]
        slot = self.slot
        self.engine.checkout(slot, base)
        applied, conflicts, patches = [], [], {}
        for label, sha in sources.items():
            if sha == base:
                continue
            patches[f"merge/{label}.patch"] = self.engine.diff(base, sha)
            commits = self.engine.git("rev-list", "--reverse", f"{base}..{sha}").split()
            ok = True
            for c in commits:
                code, _ = sh(["git", *GIT_ID, "cherry-pick", c], cwd=slot, check=False)
                if code != 0:
                    self.engine.git("cherry-pick", "--abort", cwd=slot, check=False)
                    ok = False
                    break
            (applied if ok else conflicts).append(label)
            if not ok:  # undo the partial application of this source
                self.engine.git("reset", "--hard", "-q", "HEAD", cwd=slot)
        start = self.engine.git("rev-parse", "HEAD", cwd=slot)
        log(f"mechanical merge: applied {applied or 'nothing'}; conflicts {conflicts or 'none'}")
        st["merge"] = {"sources": sources, "applied": applied, "conflicts": conflicts, "start": start}
        self.run.save()
        if not patches:
            log("nothing to merge: every source equals the base")
            return {}
        self.profile_at(start)
        lines = [f"- `{label}`: {'already applied in your working tree' if label in applied else 'NOT applied (it conflicted with the ones before it); apply it by hand'}"
                 + f" (`.dbe/merge/{label}.patch`)" for label in sources if f"merge/{label}.patch" in patches]
        issue = {"title": f"Merge {len(patches)} specialised systems: {', '.join(l for l in sources if f'merge/{l}.patch' in patches)}",
                 "hypothesis": "Each source change was accepted in a run specialised to its own templates. One engine "
                               "that contains all of them should be fast on every template of this group.",
                 "plan": "Your working tree already contains the changes that applied cleanly. Bring in the rest "
                         "from their patch files. Where two changes touch the same logic, combine them so that each "
                         "applies in the situations it was written for, deciding from general properties of the query "
                         "or plan, never from which query is running. Then build and run `bench` on all visible "
                         "templates. If one change clearly hurts another template of the group, guard it or drop it, "
                         "and say which and why. Sources:\n" + "\n".join(lines),
                 "target_files": sorted({f for p in patches.values() for f in _files_of(p)}),
                 "expected_gain": "close to the best specialised system on each template of the group",
                 "generality": "same rules as the source changes", "risk": "interactions between changes"}
        rec = self.experiment(issue, start=start, extra=patches)
        # the merged engine is evaluated even if it misses the bar against v0, as long as it passed the gates
        st["merged_sha"] = rec.get("candidate") if rec.get("passes") else None
        st["generation"] = 2
        self.engine.tag_release(1, st["best_sha"])
        st["releases"]["v1"] = st["best_sha"]
        self.run.save()
        return rec

    def profile_at(self, sha: str) -> None:
        saved = self.run.state["best_sha"]
        self.run.state["best_sha"] = sha
        try:
            self.profile()
        finally:
            self.run.state["best_sha"] = saved

    def save_wip(self, adir: Path) -> None:
        """Keep the diff of work that will not be committed (abandoned or interrupted) for the record."""
        self.engine.git("add", "-A", cwd=self.slot)
        diff = self.engine.git("diff", "--cached", cwd=self.slot)
        self.engine.git("reset", "-q", cwd=self.slot)
        if diff:
            adir.mkdir(parents=True, exist_ok=True)
            (adir / "abandoned.diff").write_text(diff + "\n")

    def gate(self, best: str, cand: str, adir: Path, issue_md: str, impl: dict, rec: dict) -> str | None:
        """Run gates then review. Returns None if everything passed, else feedback for the implementer."""
        report: dict = {}
        diff = self.engine.diff(best, cand)
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "diff.patch").write_text(diff)

        def fail(stage: str, text: str) -> str:
            report["failed"] = stage
            write_json(adir / "gates.json", report)
            return f"**Failed: {stage}.**\n\n{text}"

        report["path_policy"] = gates.path_policy(self.engine, best, cand)
        if report["path_policy"]:
            return fail("path policy", "\n".join(f"- {p}" for p in report["path_policy"]))
        report["static_audit"] = gates.static_audit(diff, self.wl.audit_patterns())
        if report["static_audit"]:
            return fail("static audit", "Engine code must not mention the workload.\n\n"
                        + "\n".join(f"- {p}" for p in report["static_audit"][:20]))
        ok, out, binary = self.engine.build(self.slot, self.slot.name, adir / "build.log")
        report["build"] = ok
        if not ok:
            return fail("build", f"```\n{out}\n```")
        self.engine.store(cand, binary)
        try:
            report["correctness"] = c = gates.correctness(self.h, cand)
        except EngineError as err:
            return fail("correctness", f"The engine could not load the benchmark data: {err}")
        if not c["ok"]:
            text = [f"- {f['instance']} on dataset `{f['dataset']}`: {f['reason']}" for f in c["visible"][:15]]
            text += [f"- {n} failure(s) on {what} (hidden; no details are given)" for what, n in c["hidden"].items()]
            return fail("correctness", "Results differ from the original engine.\n\n" + "\n".join(text))
        report["smoke"] = gates.smoke(self.h, cand)
        if report["smoke"]:
            return fail("generic SQL suite", "Queries on an unrelated schema no longer match the original engine:\n\n"
                        + "\n".join(f"- {s}" for s in report["smoke"][:10]))
        self.write_context({"review/diff.patch": diff,
                            "review/issue.md": f"{issue_md}\n\n## Author's summary\n\n{impl['summary']}\n\n"
                                               f"## Author's generality argument\n\n{impl['generality']}\n"})
        res = self.call("reviewer", render("reviewer", scope=scope_text(self.cfg), engine=self.engine.e["name"]),
                        REVIEWER_SCHEMA, self.a["reviewer_budget_usd"], adir)
        rec["cost_usd"] += res.cost_usd
        if not res.ok:
            report["review"] = {"error": res.error}
            return fail("review", f"The reviewer could not complete: {res.error[:300]}")
        report["review"] = res.output
        if res.output["verdict"] != "approve":
            items = res.output["findings"] + [f"Required: {c}" for c in res.output["required_changes"]]
            return fail("independent review", "\n".join(f"- {i}" for i in items) or "- rejected without findings")
        write_json(adir / "gates.json", report)
        return None

    def time_and_decide(self, best: str, cand: str, edir: Path, rec: dict) -> None:
        time_and_decide(self.cfg, self.h, best, cand, edir, rec)


def _files_of(patch: str) -> list[str]:
    return [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")]


def scope_text(cfg: Config) -> str:
    """Extra instructions for specialisation runs (one visible template); empty otherwise."""
    focus = cfg["workload"].get("focus")
    if not focus:
        return ""
    focus = [focus] if isinstance(focus, str) else focus
    what = (f"ONE query shape: the visible template `{focus[0]}`" if len(focus) == 1 else
            f"a GROUP of {len(focus)} query shapes: the visible templates {', '.join(f'`{t}`' for t in focus)}")
    return f"""## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for {what} (instances are in `.dbe/queries/`). The only timing that
counts is on these visible templates. Other kinds of queries may
get slower, but every query must still return correct results, and it is checked on many query
shapes you cannot see.

The code must stay general in what it refers to. Specialise to the *shape* of the query (its
operators, join structure, kinds of predicates and aggregates, data types, cardinalities), never to
names: no table or column names, no literal values from the queries, no knowledge of this dataset
(row counts, value distributions), and no caching of results across executions. A condition that
only this shape of query meets is fine here; a condition that names this query is not. Parameter
values change between runs and the data size changes, so anything tied to either will fail.
"""


def bar_text(cfg: Config) -> str:
    bar = cfg["bar"]
    if cfg["workload"].get("focus"):
        return (f"at least one visible template at least {100 * bar['min_template_gain']:.0f}% faster (more if "
                "its timings are noisy), no visible template slower beyond its noise, and the visible geomean not "
                "slower. Templates you cannot see are not timed in this run; they only have to stay correct.")
    if bar.get("rule", "templates") == "geomean":
        need = bench.required_gain(bar, bench.noise_floor(cfg))
        return (f"at least {100 * need:.1f}% faster on the visible geomean, no visible template slower by more "
                f"than {100 * bar['max_template_regression']:.0f}%, and no slowdown on the hidden templates.")
    return (f"at least one visible template at least {100 * bar['min_template_gain']:.0f}% faster (more for "
            f"templates whose timings are noisy); no template, visible or hidden, slower by more than "
            f"{100 * bar['max_template_regression']:.0f}% (again more for noisy ones); and the visible geomean not "
            "slower. A change that makes one kind of query clearly faster and nothing slower is accepted.")


def time_and_decide(cfg: Config, h: Harness, best: str, cand: str, edir: Path, rec: dict) -> dict:
    """Interleaved timing of candidate (B) against the incumbent (A), then the bar. A retired
    result that looks borderline is re-timed once with the opposite pass order and decided on all
    passes together, so a real gain is not lost to one noisy measurement."""
    train, val = h.instances("train"), h.instances("val")
    cal = bench.calibration(cfg) or {}
    times = {"A": {}, "B": {}}
    orders = [h.b["ab_order"], h.b.get("retime_order", "BAAB")]
    d: dict = {}
    for k, order in enumerate(orders):
        if k == 1 and not bench.borderline(d, cfg["bar"]):
            break
        if k == 1:
            log(f"borderline result ({'; '.join(d['reasons'])[:120]}); re-timing with order {order}")
        r = h.interleaved({"A": best, "B": cand}, order, train + val)
        write_json(edir / f"timing-{k + 1}.json", r)
        if r["failures"]["B"]:
            rec["reasons"] = [f"{len(r['failures']['B'])} wrong or failed result(s) during timing runs"]
            rec["outcome"] = "retired"
            return {}
        for lab in "AB":
            for iid, runs in r["times"][lab].items():
                times[lab].setdefault(iid, []).extend(runs)
        ta, tb = times["A"], times["B"]
        d = bench.decide(bench.template_times(ta, train), bench.template_times(tb, train),
                         bench.template_times(ta, val), bench.template_times(tb, val), cfg["bar"], cal)
        d["passes"] = sum(len(o) for o in orders[:k + 1])
    write_json(edir / "decision.json", d)
    rec.update({k: d[k] for k in ("train_ratio", "val_ratio", "val_ok", "required_gain", "train_template_ratios")})
    rec.update(improved=d.get("improved"), regressed=d.get("regressed"), passes=d["passes"], rule=d["rule"])
    rec["reasons"] = d["reasons"]
    rec["outcome"] = "accepted" if d["accept"] else "retired"
    return d


def explain_analyze(session, sql: str, limit: int = 10000) -> str:
    try:
        _, out = session.run(f"EXPLAIN ANALYZE {sql}")
    except EngineError as e:
        return f"(failed: {e})"
    # the shell prints a banner and echoes the statement before the plan; keep the plan
    lines = out.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if line.startswith("EXPLAIN ANALYZE")), 0)
    text = "\n".join(lines[start:])
    return text[:limit] + ("\n... (truncated)" if len(text) > limit else "")
