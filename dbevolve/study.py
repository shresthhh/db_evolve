"""The specialisation study: per-template systems, their cross-evaluation, grouping, and merges.

    specialize q01 q09 ...         one run per template, each specialising v0 to that template alone
    crosseval --systems ...        time v0 and every system on all templates -> speedup matrix
    groups --cross DIR --k 1 2 4   cluster templates into k groups from the matrix (+ random baseline)
    merge --name N --group q01,q09 combine the group's specialised systems into one engine
"""
from __future__ import annotations

import math
import random

from .util import geomean


def matrix(rep: dict, systems: list[str]) -> dict[str, dict[str, float]]:
    """speedup[system][template] vs v0, over every template in the report."""
    out = {}
    for sysname in systems:
        v = rep["versions"][sysname]["speedup_vs_v0"]
        out[sysname] = {t: x for s in v for t, x in v[s]["templates"].items()}
    return out


def similarity(m: dict[str, dict[str, float]], owner: dict[str, str]) -> dict[tuple[str, str], float]:
    """How much two templates benefit from each other's specialised system (log speedup, symmetric).
    `owner[template]` is the system specialised for that template."""
    ts = sorted(owner)
    sim = {}
    for i, a in enumerate(ts):
        for b in ts[i + 1:]:
            x = math.log(m[owner[a]].get(b, 1.0)) + math.log(m[owner[b]].get(a, 1.0))
            sim[(a, b)] = sim[(b, a)] = x
    return sim


def cluster(templates: list[str], sim: dict, k: int) -> list[list[str]]:
    """Average-linkage agglomerative clustering into k groups (deterministic)."""
    groups = [[t] for t in sorted(templates)]
    while len(groups) > k:
        best, pair = -math.inf, None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                s = sum(sim[(a, b)] for a in groups[i] for b in groups[j]) / (len(groups[i]) * len(groups[j]))
                if s > best:
                    best, pair = s, (i, j)
        i, j = pair
        groups[i] = sorted(groups[i] + groups[j])
        del groups[j]
    return sorted(groups)


def random_groups(templates: list[str], k: int, seed: int) -> list[list[str]]:
    ts = sorted(templates)
    random.Random(seed).shuffle(ts)
    return sorted(sorted(ts[i::k]) for i in range(k))


def oracle(m: dict, owner: dict[str, str]) -> dict[str, float]:
    """Per-template speedup when every template runs on its own specialised system."""
    return {t: m[s].get(t, 1.0) for t, s in owner.items()}


def summary(speedups: dict[str, float]) -> float:
    return geomean(speedups.values()) if speedups else float("nan")
