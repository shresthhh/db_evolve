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
    dataset: str | None = None   # scale-factor mode: the dataset this item runs on (else the pass's)
    label: str | None = None     # scale-factor mode: the item, e.g. "q05@sf30"

    @property
    def item(self) -> str:
        """What timings are aggregated and split by: the template, or (template, SF) in SF mode."""
        return self.label or self.template

    @property
    def id(self) -> str:
        return f"{self.item}.{self.kind[0]}{self.index}"

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
        # scale-factor mode: `workload.datasets = ["sf1", "sf3", "main", ...]` makes every
        # (template, dataset) pair an item, labelled by scale factor ("q05@sf30")
        self.item_datasets = list(w.get("datasets") or [])
        self.label_dataset = {f"sf{cfg['datasets'][d]['scale_factor']:g}": d for d in self.item_datasets}
        self.items = ([f"{t}@{lab}" for lab in self.label_dataset for t in self.templates]
                      if self.item_datasets else self.templates)
        self.split = self._split()

    def _split(self) -> dict[str, list[str]]:
        """Seeded shuffle of the templates; whole templates go to exactly one split.

        Specialisation mode (`workload.focus = "q09"` or a list): the focus templates are the only visible ones;
        every other template is held out and used for correctness only (it may get slower)."""
        focus = self.focus
        if focus:
            unknown = set(focus) - set(self.items)
            if unknown:
                raise ValueError(f"unknown focus templates {sorted(unknown)}")
            return {"train": sorted(focus), "val": [], "test": [t for t in self.items if t not in focus]}
        if self.item_datasets:
            return self._split_items()
        order = list(self.templates)
        random.Random(_seed(self.seed, "split")).shuffle(order)
        n_train, n_val, n_test = self.w["train_templates"], self.w["val_templates"], self.w["test_templates"]
        if n_train + n_val + n_test != len(order):
            raise ValueError(f"split sizes must sum to {len(order)} templates")
        return {"train": sorted(order[:n_train]),
                "val": sorted(order[n_train:n_train + n_val]),
                "test": sorted(order[n_train + n_val:])}

    def _split_items(self) -> dict[str, list[str]]:
        """Seeded, stratified split of the (template, SF) items: the test and validation items are
        spread evenly over the scale factors, and no template has more than `max_held_per_template`
        of its items held out (default 2), so most held-out items have their template visible at
        other scale factors: the held-out sets measure transfer across scale."""
        n = {s: self.w[f"{s}_templates"] for s in SPLITS}
        if sum(n.values()) != len(self.items):
            raise ValueError(f"split sizes must sum to {len(self.items)} items")
        order = list(self.items)
        random.Random(_seed(self.seed, "split-items")).shuffle(order)
        cap_t = self.w.get("max_held_per_template", 2)
        held_t: dict[str, int] = {}
        out: dict[str, list[str]] = {}
        for s in ("test", "val"):
            per_sf = -(-n[s] // len(self.label_dataset))   # ceil: even spread over scale factors
            got, by_sf = [], {}
            for item in order:
                if len(got) == n[s]:
                    break
                t, lab = item.split("@")
                if by_sf.get(lab, 0) < per_sf and held_t.get(t, 0) < cap_t:
                    got.append(item)
                    by_sf[lab] = by_sf.get(lab, 0) + 1
                    held_t[t] = held_t.get(t, 0) + 1
            if len(got) < n[s]:
                raise ValueError(f"cannot place {n[s]} {s} items under the stratification caps")
            out[s] = sorted(got)
            order = [i for i in order if i not in got]
        out["train"] = sorted(order)
        return {s: out[s] for s in SPLITS}

    def split_of(self, template: str) -> str:
        return next(s for s in SPLITS if template in self.split[s])

    def instances(self, split: str, scale_factor: float, heldout: bool = False) -> list[Instance]:
        """Parameter bindings for a split. `heldout=True` gives the hidden extra bindings (train only)."""
        kind = "heldout" if heldout else "main"
        n = self.w["heldout_bindings"] if heldout else self.w["instances_per_template"]
        out = []
        for item in self.split[split]:
            t, dataset, sf = item, None, scale_factor
            if self.item_datasets:   # each item runs on its own dataset, at its own scale factor
                t, lab = item.split("@")
                dataset, sf = self.label_dataset[lab], float(lab[2:])
            for i in range(n):
                # same seed for a template at every scale factor: the bindings differ only where
                # the template's parameters scale with the data (e.g. q11's fraction)
                rng = random.Random(_seed(self.seed, "bind", t, kind, i))
                sql, params = self.mod.instantiate(t, rng, sf)
                out.append(Instance(t, split, kind, i, sql, params, dataset, item if dataset else None))
        return out

    def template_instances(self, split: str, scale_factor: float, heldout: bool = False) -> list[Instance]:
        """Scale-factor mode: one instance set per distinct template of a split's items, run on the
        pass's dataset (used for the shadow correctness check on other data)."""
        templates = sorted({i.split("@")[0] for i in self.split[split]})
        kind = "heldout" if heldout else "main"
        n = self.w["heldout_bindings"] if heldout else self.w["instances_per_template"]
        out = []
        for t in templates:
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
