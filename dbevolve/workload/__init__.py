"""Workloads: query templates, seeded parameter bindings, and the template-level split."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from . import tpcds, tpch

WORKLOADS = {"tpch": tpch, "tpcds": tpcds}
SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class Instance:
    template: str        # e.g. "q06"
    split: str           # train | val | test
    kind: str            # "main" or "heldout" (hidden extra bindings of a train template)
    index: int
    sql: str
    params: tuple

    @property
    def id(self) -> str:
        return f"{self.template}.{self.kind[0]}{self.index}"

    @property
    def key(self) -> str:  # content hash: names the cached reference result
        return hashlib.sha256(self.sql.encode()).hexdigest()[:16]


def _seed(*parts) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


class Workload:
    """A workload module must expose TEMPLATES, TABLES, instantiate(), datagen_sql() and audit_patterns()."""

    def __init__(self, cfg):
        w = cfg["workload"]
        self.w = w
        self.name = w["name"]
        self.mod = WORKLOADS[self.name]
        self.seed = w["seed"]
        self.templates = sorted(self.mod.TEMPLATES)
        self.split = self._split()

    def _split(self) -> dict[str, list[str]]:
        """Seeded shuffle of the templates; whole templates go to exactly one split.

        Specialisation mode (`workload.focus = "q09"` or a list): the focus templates are the only visible ones;
        every other template is held out and used for correctness only (it may get slower)."""
        focus = self.focus
        if focus:
            unknown = set(focus) - set(self.templates)
            if unknown:
                raise ValueError(f"unknown focus templates {sorted(unknown)}")
            return {"train": sorted(focus), "val": [], "test": [t for t in self.templates if t not in focus]}
        order = list(self.templates)
        random.Random(_seed(self.seed, "split")).shuffle(order)
        n_train, n_val, n_test = self.w["train_templates"], self.w["val_templates"], self.w["test_templates"]
        if n_train + n_val + n_test != len(order):
            raise ValueError(f"split sizes must sum to {len(order)} templates")
        return {"train": sorted(order[:n_train]),
                "val": sorted(order[n_train:n_train + n_val]),
                "test": sorted(order[n_train + n_val:])}

    def split_of(self, template: str) -> str:
        return next(s for s in SPLITS if template in self.split[s])

    def instances(self, split: str, scale_factor: float, heldout: bool = False) -> list[Instance]:
        """Parameter bindings for a split. `heldout=True` gives the hidden extra bindings (train only)."""
        kind = "heldout" if heldout else "main"
        n = self.w["heldout_bindings"] if heldout else self.w["instances_per_template"]
        out = []
        for t in self.split[split]:
            for i in range(n):
                rng = random.Random(_seed(self.seed, "bind", t, kind, i))
                sql, params = self.mod.instantiate(t, rng, scale_factor)
                out.append(Instance(t, split, kind, i, sql, params))
        return out

    @property
    def focus(self) -> list[str]:
        """Specialisation target: one template or a group of them (`workload.focus`)."""
        f = self.w.get("focus") or []
        return [f] if isinstance(f, str) else list(f)

    def gate_instances(self, scale_factor: float) -> dict[str, list[Instance]]:
        """Everything the acceptance gates may touch. The test split is deliberately absent, except in
        specialisation mode, where the other templates are checked for correctness (never timed)."""
        g = {"train": self.instances("train", scale_factor),
             "heldout": self.instances("train", scale_factor, heldout=True),
             "val": self.instances("val", scale_factor)}
        if self.focus:
            g["other"] = self.instances("test", scale_factor)
        return g

    @property
    def tables(self) -> list[str]:
        return list(self.mod.TABLES)

    def datagen_sql(self, scale_factor: float) -> str:
        return self.mod.datagen_sql(scale_factor)

    def audit_patterns(self) -> list[str]:
        return self.mod.audit_patterns()
