"""Mechanical gates a candidate must pass before it is reviewed or timed.

  1. path policy   - the diff stays inside the engine's editable paths and under a size limit
  2. static audit  - added lines contain no workload identifiers (schema names, query literals)
  3. build         - (engine.build)
  4. correctness   - same answers as the baseline on visible, held-out and validation instances,
                     on the main dataset and on a second "shadow" dataset
  5. smoke suite   - generic SQL on a schema unrelated to the workload still gives baseline answers

Feedback for anything the agent is not allowed to see (held-out bindings, validation templates)
is reduced to a count, never query text or results.
"""
from __future__ import annotations

import re

from . import compare
from .bench import Harness
from .engine import Engine
from .session import EngineError, Session
from .util import machine_lock


def path_policy(engine: Engine, base: str, cand: str) -> list[str]:
    e = engine.e
    problems = []
    for f in engine.changed_files(base, cand):
        if any(f.startswith(p) for p in e["forbidden_paths"]):
            problems.append(f"{f}: path is off limits")
        elif not any(f.startswith(p) for p in e["editable_paths"]):
            problems.append(f"{f}: outside the editable paths {e['editable_paths']}")
    stat = engine.git("diff", "--shortstat", f"{base}..{cand}")
    changed = sum(int(n) for n in re.findall(r"(\d+) (?:insertion|deletion)", stat))
    if changed > e["max_diff_lines"]:
        problems.append(f"diff touches {changed} lines; the limit is {e['max_diff_lines']}")
    return problems


def static_audit(diff_text: str, patterns: list[str]) -> list[str]:
    """Flag workload-specific identifiers in lines the candidate adds."""
    compiled = [re.compile(p) for p in patterns]
    findings, current = [], "?"
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and not line.startswith("+++"):
            for rx in compiled:
                m = rx.search(line)
                if m:
                    findings.append(f"{current}: added line mentions workload identifier {m.group(0)!r}: "
                                    f"{line[1:].strip()[:120]}")
                    break
    return findings


def correctness(h: Harness, sha: str) -> dict:
    """Returns {"ok": bool, "visible": [failures with detail], "hidden": {category: count}}."""
    visible, hidden = [], {}
    if h.wl.item_datasets:
        # scale-factor mode: every item on its own dataset, then each distinct template once on
        # every dataset that is not an item dataset (the shadow data)
        passes = [("main", h.wl.gate_instances(0.0))]
        for d in h.cfg["datasets"]:
            if d not in h.wl.item_datasets:
                sf = h.cfg["datasets"][d]["scale_factor"]
                g = {"train": h.wl.template_instances("train", sf),
                     "heldout": h.wl.template_instances("train", sf, heldout=True),
                     "val": h.wl.template_instances("val", sf)}
                if h.wl.focus:
                    g["other"] = h.wl.template_instances("test", sf)
                passes.append((d, g))
    else:
        passes = [(d, h.wl.gate_instances(h.cfg["datasets"][d]["scale_factor"])) for d in h.cfg["datasets"]]
    for dataset, groups in passes:
        for group, instances in groups.items():
            for f in h.check(sha, instances, dataset):
                if group == "train":
                    visible.append(f)
                else:
                    label = {"heldout": "new parameter bindings of visible templates",
                             "val": "templates you have not seen",
                             "other": "templates you have not seen"}[group]
                    hidden[label] = hidden.get(label, 0) + 1
    return {"ok": not visible and not hidden, "visible": visible, "hidden": hidden}


# --- smoke suite: generic SQL on an unrelated schema ---------------------------------

SMOKE_SETUP = [
    """CREATE TABLE t1 AS SELECT i AS id, (i * 7919) % 1000 AS a, (i * 104729) % 97 AS b,
              CASE WHEN i % 11 = 0 THEN NULL ELSE (i % 500) / 7.0 END AS x,
              'k' || ((i * 31) % 200) AS s, DATE '2020-01-01' + CAST(i % 900 AS INTEGER) AS d
       FROM range(200000) r(i)""",
    """CREATE TABLE t2 AS SELECT i AS id, (i * 13) % 1000 AS a, 'v' || (i % 50) AS tag,
              CAST((i * 17) % 10007 AS DECIMAL(12,2)) / 100 AS amt
       FROM range(5000) r(i)""",
    "CREATE TABLE t3 AS SELECT i AS b, 'g' || (i % 7) AS grp FROM range(97) r(i)",
    "CREATE TABLE empty_t AS SELECT * FROM t2 WHERE false",
]
SMOKE_QUERIES = [
    "SELECT count(*), count(x), sum(a), min(s), max(s), min(d), max(d) FROM t1",
    "SELECT b, count(*) AS n, sum(a) AS sa, avg(x) AS ax FROM t1 GROUP BY b ORDER BY b",
    "SELECT s, count(DISTINCT a) AS da, max(x) AS mx FROM t1 GROUP BY s ORDER BY s",
    "SELECT t3.grp, count(*) AS n, sum(t1.a) AS sa FROM t1 JOIN t3 ON t1.b = t3.b GROUP BY t3.grp ORDER BY t3.grp",
    "SELECT t2.tag, count(*) AS n, sum(t2.amt) AS amt FROM t1 JOIN t2 ON t1.a = t2.a WHERE t1.id % 3 = 0 GROUP BY t2.tag ORDER BY t2.tag",
    "SELECT count(*), count(t2.id) FROM t1 LEFT JOIN t2 ON t1.id = t2.id AND t2.amt > 50",
    "SELECT count(*) FROM t1 WHERE EXISTS (SELECT 1 FROM t2 WHERE t2.a = t1.a AND t2.id < 100)",
    "SELECT count(*) FROM t1 WHERE a NOT IN (SELECT a FROM t2 WHERE id % 2 = 0)",
    "SELECT id, a, s FROM t1 WHERE s LIKE 'k1%' AND a BETWEEN 100 AND 140 ORDER BY a DESC, id LIMIT 25",
    "SELECT id, x FROM t1 ORDER BY x DESC NULLS LAST, id LIMIT 15",
    "SELECT id, x FROM t1 ORDER BY x NULLS FIRST, id LIMIT 15 OFFSET 5",
    "SELECT count(*) FROM (SELECT a, count(*) FROM t1 GROUP BY a LIMIT 10) q",
    "SELECT count(*) FROM (SELECT DISTINCT a, b FROM t1) q",
    "SELECT b, id, a, rn FROM (SELECT b, id, a, row_number() OVER (PARTITION BY b ORDER BY a DESC, id) AS rn FROM t1) q WHERE rn <= 2 ORDER BY b, rn",
    "SELECT extract(year FROM d) AS y, extract(month FROM d) AS m, count(*) AS n FROM t1 WHERE d >= DATE '2021-06-01' AND d < DATE '2021-06-01' + INTERVAL '3' MONTH GROUP BY y, m ORDER BY y, m",
    "SELECT CASE WHEN x IS NULL THEN 'null' WHEN x < 10 THEN 'low' ELSE 'high' END AS bucket, count(*) AS n FROM t1 GROUP BY bucket ORDER BY bucket",
    "SELECT a, n FROM (SELECT a, count(*) AS n FROM t1 GROUP BY a HAVING count(*) > 200) q ORDER BY n DESC, a LIMIT 20",
    "WITH big AS (SELECT a, sum(amt) AS total FROM t2 GROUP BY a) SELECT count(*), max(total) FROM big WHERE total > (SELECT avg(total) FROM big)",
    "SELECT a FROM t2 WHERE id < 20 UNION SELECT a FROM t1 WHERE id < 20 ORDER BY a",
    "SELECT sum(CAST(id AS HUGEINT) * 1000000007) FROM t1",
    "SELECT substring(s FROM 1 FOR 2) AS p, upper(min(s)), length(max(s)), count(*) FROM t1 GROUP BY p ORDER BY p",
    "SELECT count(*), sum(amt), min(tag) FROM empty_t",
    "SELECT tag, count(*) FROM empty_t GROUP BY tag ORDER BY tag",
    "SELECT * FROM t2 ORDER BY id LIMIT 0",
    "SELECT t2.id, t2.amt FROM t2 WHERE amt = (SELECT max(amt) FROM t2) ORDER BY id",
    "SELECT id FROM t1 WHERE id IN (0, 199999, 200000, -1) ORDER BY id",
    "SELECT count(*) FROM t1 a JOIN t1 b ON a.id = b.id + 1 WHERE a.b <> b.b",
    "SELECT median(a), quantile_cont(x, 0.9), stddev_samp(a), string_agg(DISTINCT grp, ',' ORDER BY grp) FROM t1 JOIN t3 USING (b)",
]


def _smoke_outputs(binary, threads: int) -> list[str]:
    out = []
    with Session(binary, None, threads, timeout=120) as s:
        for stmt in SMOKE_SETUP:
            s.run(stmt)
        for q in SMOKE_QUERIES:
            try:
                out.append(s.run(q)[1])
            except EngineError as e:
                out.append(f"ERROR: {e}")
    return out


def smoke(h: Harness, sha: str) -> list[str]:
    """Differential test against the baseline. Query text is fine to show: it is not the workload."""
    with machine_lock(h.cfg.work):
        want = _smoke_outputs(h.engine.binary(h.engine.base_sha()), h.b["threads"])
        got = _smoke_outputs(h.engine.binary(sha), h.b["threads"])
    failures = []
    for q, g, w in zip(SMOKE_QUERIES, got, want):
        ok, why = (False, g[:300]) if g.startswith("ERROR") else compare.equal(g, w)
        if not ok:
            failures.append(f"{q}\n    -> {why}")
    return failures
