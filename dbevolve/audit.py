"""Changelog and generality audit of a run's accepted changes, release to release.

For every commit between two releases: what it changes (files, lines), how much it helped when it
was accepted and, if the run was ablated, on its own; simple static signals of special-casing in
the added code; and an independent auditor agent's account of the mechanism, the exact trigger
conditions, where its constants come from, a natural class of non-benchmark queries that take the
path, and a label (general / heuristic / special_case) with code citations.

Output: docs/changes/<run>-<from>-<to>.md (readable) and results/<run>-audit/<id>.json (one per
change, also the cache that lets an interrupted audit resume).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .agents import ClaudeCLI
from .config import ROOT, Config
from .engine import Engine
from .loop import Run, render, scope_text, KNOWLEDGE
from .util import log, read_json, write_json

_S = {"type": "string"}
AUDIT_SCHEMA = {"type": "object", "additionalProperties": False,
                "required": ["mechanism", "trigger", "constants", "natural_class", "fallback", "label",
                             "label_reason", "citations"],
                "properties": {"mechanism": _S, "trigger": _S, "constants": _S, "natural_class": _S,
                               "fallback": _S,
                               "label": {"type": "string", "enum": ["general", "heuristic", "special_case"]},
                               "label_reason": _S,
                               "citations": {"type": "array", "items": _S}}}

_NUM = re.compile(r"(?<![\w.])(\d{3,}|\d+\.\d+)(?![\w.])")
_STR = re.compile(r'"[^"\n]{2,}"')
_COND = re.compile(r"\b(if|else if|switch|case)\b")


def static_signals(diff: str) -> dict:
    """Counts over the added source lines (comments excluded) that hint at special-casing."""
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    code = [l for l in added if not l.strip().startswith(("//", "*", "/*"))]
    return {"added_lines": len(added), "removed_lines": sum(1 for l in diff.splitlines()
                                                             if l.startswith("-") and not l.startswith("---")),
            "conditions": sum(len(_COND.findall(l)) for l in code),
            "numeric_constants": sorted({m for l in code for m in _NUM.findall(l)})[:30],
            "string_literals": sorted({m for l in code for m in _STR.findall(l)})[:20]}


def _ablation_alone(cfg: Config, run_id: str) -> dict[str, dict]:
    """Per experiment: speedup over v0 of that change applied alone (from `dbe ablate`), if ablated."""
    rep = read_json(cfg.results / f"{run_id}-ablation" / "report.json")
    if not rep:
        return {}

    def times(v):
        out = {}
        for s in rep["versions"][v]["splits"].values():
            out.update(s["templates"])
        return out
    v0 = times("v0")
    out = {}
    for v in rep["versions"]:
        if v.startswith("only-"):
            t = times(v)
            sp = {k: v0[k] / t[k] for k in v0 if k in t}
            out[v[5:]] = {"geomean": math.exp(sum(map(math.log, sp.values())) / len(sp)),
                          "faster": {k: round(x, 2) for k, x in sorted(sp.items()) if x >= 1.05},
                          "slower": {k: round(x, 2) for k, x in sorted(sp.items()) if x <= 0.95}}
    return out


def audit(cfg: Config, run_id: str, frm: str = "v0", to: str | None = None, budget: float = 2.0,
          agent: bool = True) -> Path:
    run = Run(cfg, run_id)
    rel = run.state["releases"]
    to = to or sorted(rel, key=lambda v: int(v[1:]))[-1]
    engine = Engine(cfg)
    ledger = {r["id"]: r for r in run.ledger}
    alone = _ablation_alone(cfg, run_id)
    out_dir = cfg.results / f"{run_id}-audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = engine.git("log", "--reverse", "--format=%H %s", f"{rel[frm]}..{rel[to]}").splitlines()
    slot = engine.slot(2)
    cli = ClaudeCLI(cfg)
    entries = []
    for line in filter(str.strip, lines):
        sha, subject = line.split(" ", 1)
        eid = subject.split(":")[0]
        cache = out_dir / f"{eid}.json"
        entry = read_json(cache) or {}
        diff = engine.git("diff", f"{sha}~1", sha, "--", "src", "extension")
        entry.update({"id": eid, "sha": sha, "subject": subject,
                      "files": engine.git("diff", "--name-only", f"{sha}~1", sha).splitlines(),
                      "static": static_signals(diff)})
        rec = ledger.get(eid, {})
        if rec.get("train_ratio"):
            entry["accepted_gain"] = 1 / rec["train_ratio"]
            entry["accepted_faster"] = {t: round(1 / r, 2) for t, r in sorted(rec.get("train_template_ratios", {}).items())
                                        if r <= 1 / 1.05}
        if eid in alone:
            entry["alone"] = alone[eid]
        if agent and "audit" not in entry:
            engine.checkout(slot, sha)
            ctx = slot / ".dbe"
            import shutil
            shutil.rmtree(ctx, ignore_errors=True)
            shutil.copytree(KNOWLEDGE, ctx / "knowledge")
            (ctx / "review").mkdir(parents=True)
            (ctx / "review" / "diff.patch").write_text(diff)
            (ctx / "review" / "issue.md").write_text(
                f"### {rec.get('title', subject)}\n\n## Author's summary\n\n{rec.get('summary', '(none)')}\n\n"
                f"## Author's notes\n\n{rec.get('notes', '(none)')}\n")
            prompt = render("auditor", engine=cfg["engine"]["name"], workload=cfg["workload"]["name"].upper(),
                            scope=scope_text(cfg))
            log(f"auditing {eid}: {subject[:70]}")
            res = cli.run("auditor", prompt, slot, AUDIT_SCHEMA, budget, out_dir / "logs" / eid)
            if res.ok:
                entry["audit"] = res.output
                entry["audit_cost_usd"] = res.cost_usd
            else:
                log(f"audit of {eid} failed: {res.error[:200]}")
        write_json(cache, entry)
        entries.append(entry)
    doc = ROOT / "docs" / "changes" / f"{run_id}-{frm}-{to}.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(markdown(run_id, frm, to, entries))
    log(f"changelog written to {doc}")
    return doc


def markdown(run_id: str, frm: str, to: str, entries: list[dict]) -> str:
    labels = [e.get("audit", {}).get("label", "not audited") for e in entries]
    count = {l: labels.count(l) for l in dict.fromkeys(labels)}
    out = [f"# {run_id}: what changed from {frm} to {to}\n",
           f"{len(entries)} accepted changes. Auditor labels: "
           + ", ".join(f"{n} {l.replace('_', ' ')}" for l, n in count.items()) + ".\n",
           "Gain at acceptance is the visible-geomean speedup over the previous best when the change was "
           "accepted; alone is the change applied by itself to v0 (from `dbe ablate`, if it was run).\n",
           "| Id | Change | Label | Files | +/- lines | Conditions added | Gain at acceptance | Alone |",
           "|---|---|---|---|---|---|---|---|"]
    for e in entries:
        s, a = e["static"], e.get("alone", {})
        gain = f"{e['accepted_gain']:.3f}×" if "accepted_gain" in e else "–"
        alone = f"{a['geomean']:.3f}×" if a else "–"
        out.append(f"| {e['id']} | {e['subject'].split(':', 1)[-1].strip()[:70]} | "
                   f"{e.get('audit', {}).get('label', '–').replace('_', ' ')} | {len(e['files'])} | "
                   f"+{s['added_lines']} / -{s['removed_lines']} | {s['conditions']} | {gain} | "
                   f"{alone} |")
    for e in entries:
        a, au = e.get("alone", {}), e.get("audit", {})
        out += [f"\n## {e['id']}: {e['subject'].split(':', 1)[-1].strip()}\n",
                f"Commit `{e['sha'][:12]}`. Files: " + ", ".join(f"`{f}`" for f in e["files"]) + "."]
        if e.get("accepted_faster"):
            out.append("Faster when accepted: " + ", ".join(f"{t} {x}×" for t, x in e["accepted_faster"].items()) + ".")
        if a:
            out.append(f"Alone on v0: {a['geomean']:.3f}× over all templates"
                       + (("; faster " + ", ".join(f"{t} {x}×" for t, x in a["faster"].items())) if a["faster"] else "")
                       + (("; slower " + ", ".join(f"{t} {x}×" for t, x in a["slower"].items())) if a["slower"] else "")
                       + ".")
        s = e["static"]
        if s["numeric_constants"]:
            out.append("Numeric constants in added code: " + ", ".join(f"`{c}`" for c in s["numeric_constants"]) + ".")
        if au:
            out += [f"\n**Label: {au['label'].replace('_', ' ')}.** {au['label_reason']}\n",
                    f"- **Mechanism.** {au['mechanism']}", f"- **Trigger.** {au['trigger']}",
                    f"- **Constants.** {au['constants']}", f"- **Outside this benchmark.** {au['natural_class']}",
                    f"- **Otherwise.** {au['fallback']}",
                    "- **Code.** " + "; ".join(au["citations"][:8])]
        else:
            out.append("\n(not audited)")
    return "\n".join(out) + "\n"
