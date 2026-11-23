"""Result equivalence between a candidate and the reference (baseline) engine.

Every workload query has a total ORDER BY (or returns one row), so results are compared row by
row, in order. Numeric cells are compared with a small relative tolerance because a legitimate
change to parallel aggregation can reorder floating-point additions.
"""
from __future__ import annotations

import csv
import io
import math

REL_TOL = 1e-9
ABS_TOL = 1e-9


def parse(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def _cell_equal(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        fa, fb = float(a), float(b)
    except ValueError:
        return False
    return math.isclose(fa, fb, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def equal(got: str, want: str) -> tuple[bool, str]:
    """Returns (ok, short reason)."""
    g, w = parse(got), parse(want)
    if len(g) != len(w):
        return False, f"row count {max(len(g) - 1, 0)} != expected {max(len(w) - 1, 0)}"
    for i, (rg, rw) in enumerate(zip(g, w)):
        if len(rg) != len(rw):
            return False, f"row {i}: column count {len(rg)} != expected {len(rw)}"
        for j, (a, b) in enumerate(zip(rg, rw)):
            if not _cell_equal(a, b):
                where = "header" if i == 0 else f"row {i}"
                return False, f"{where}, column {j + 1}: got {a[:60]!r}, expected {b[:60]!r}"
    return True, ""
