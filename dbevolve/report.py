"""Release evaluation: time every released version on every split and write the report.

This is the only place the test split is ever executed. Its numbers go to results/ for people to
read; nothing here is fed back to the agents.
"""
from __future__ import annotations

from pathlib import Path

from . import bench, data
from .bench import Harness
from .util import geomean, log, now, write_json

CONTROL = "v0-control"
SPLIT_LABEL = {"train": "train (visible)", "val": "validation (hidden)", "test": "test (held out)"}
# validated with the dataviz palette checker (light surface); green needs the direct labels it gets
SPLIT_COLOR = {"train": "#2a78d6", "val": "#eb6834", "test": "#1baf7a"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"


def evaluate(h: Harness, releases: dict[str, str], timed_runs: int | None = None) -> dict:
    """Interleave full passes over all versions (forward, then reversed) on every split."""
    labels = list(releases)
    instances = {s: h.instances(s) for s in ("train", "val", "test") if h.wl.split[s]}
    everything = [i for s in instances.values() for i in s]
    # The first version is measured twice, as itself and as a control. The control's distance
    # from 1.0 is this report's own measurement noise.
    shas = {**releases, CONTROL: releases[labels[0]]}
    seq = list(shas)
    order = [lab for k in range(h.cfg["report"]["passes"]) for lab in (seq if k % 2 == 0 else seq[::-1])]
    log(f"evaluating {', '.join(labels)} on {len(everything)} query instances, {len(order)} passes")
    r = _interleave(h, shas, order, everything, timed_runs)
    versions = {}
    for lab in seq:
        splits = {s: bench.summarize(r["times"][lab], inst) for s, inst in instances.items()}
        meta = data.db_meta(h.cfg, h.wl, shas[lab], "main")
        versions[lab] = {"sha": shas[lab], "splits": splits, "failures": r["failures"][lab],
                         "load_seconds": meta.get("load_seconds"), "db_bytes": meta.get("bytes")}
    base = versions[labels[0]]
    for lab in seq:
        v = versions[lab]
        v["speedup_vs_v0"] = {}
        for s in instances:
            rs = bench.ratios(base["splits"][s]["templates"], v["splits"][s]["templates"])  # v0 / v
            v["speedup_vs_v0"][s] = {"geomean": geomean(rs.values()), "templates": rs}
    control = versions.pop(CONTROL)
    noise = {s: abs(control["speedup_vs_v0"][s]["geomean"] - 1) for s in instances}
    return {"created": now(), "workload": h.wl.name, "split": h.wl.split, "threads": h.b["threads"],
            "scale_factor": data.scale_factor(h.cfg, "main"), "passes": len(order) // len(seq),
            "noise": noise, "control": control, "versions": versions}


def _interleave(h: Harness, shas: dict, order: list[str], instances, timed_runs):
    from .util import machine_lock
    timed_runs = timed_runs or h.b["timed_runs"]
    times = {lab: {} for lab in shas}
    failures = {lab: [] for lab in shas}
    with machine_lock(h.cfg.work):
        for lab in order:
            t, f = h.run_pass(shas[lab], instances, "main", timed_runs, h.b["warmup_runs"])
            for iid, runs in t.items():
                times[lab].setdefault(iid, []).extend(runs)
            seen = {x["instance"] for x in failures[lab]}
            failures[lab].extend(x for x in f if x["instance"] not in seen)
    return {"times": times, "failures": failures}


def _active(rep: dict) -> list[str]:
    """Splits that have templates (a transfer workload may put everything in one split)."""
    return [s for s in SPLIT_LABEL if rep["split"].get(s) and s in rep["noise"]]


def markdown(rep: dict) -> str:
    vs = rep["versions"]
    labels = list(vs)
    active = _active(rep)
    out = [f"# Release report: {rep['workload']} (SF {rep['scale_factor']}, {rep['threads']} threads)", "",
           f"Generated {rep['created']}. Times are hot-run medians; a split's score is the geometric mean of "
           "its per-template times. Speedup is relative to v0 (the unmodified engine); above 1.0 is faster.", "",
           "## Geomean latency (ms) and speedup by split", "",
           "| Version | Commit | " + " | ".join(SPLIT_LABEL[s] for s in active) + " | Wrong results |",
           "| --- | --- | " + " | ".join("---:" for _ in active) + " | ---: |"]
    for lab in labels:
        v = vs[lab]
        cells = [f"{1000 * v['splits'][s]['geomean_s']:.1f} ({v['speedup_vs_v0'][s]['geomean']:.3f}x)" for s in active]
        out.append(f"| {lab} | `{v['sha'][:10]}` | " + " | ".join(cells) + f" | {len(v['failures'])} |")
    out += ["", "Measurement noise in this report (v0 timed twice, as itself and as a control): "
            + ", ".join(f"{s} ±{100 * rep['noise'][s]:.1f}%" for s in active)
            + ". Differences smaller than this are not evidence.",
            "", "## Speedup vs v0 by template", "",
            "| Split | Template | v0 ms | " + " | ".join(labels[1:]) + " |",
            "| --- | --- | ---: | " + " | ".join("---:" for _ in labels[1:]) + " |"]
    for s in active:
        for t in rep["split"][s]:
            base_ms = 1000 * vs[labels[0]]["splits"][s]["templates"].get(t, float("nan"))
            cells = [f"{vs[lab]['speedup_vs_v0'][s]['templates'].get(t, float('nan')):.2f}x" for lab in labels[1:]]
            out.append(f"| {s} | {t} | {base_ms:.1f} | " + " | ".join(cells) + " |")
    out += ["", "The test split is held out: agents never see its queries, and it is not used to accept or "
            "reject changes. A gain on train that does not appear on test is overfitting.", ""]
    return "\n".join(out)


def plots(rep: dict, out_dir: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    import math

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#c3c2b7",
                         "axes.labelcolor": "#52514e", "xtick.color": MUTED, "ytick.color": MUTED,
                         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})
    vs = rep["versions"]
    labels = list(vs)
    paths = []

    # 1. latency relative to v0, by version, one line per split
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ends = []
    for s, color in SPLIT_COLOR.items():
        if s not in _active(rep):
            continue
        y = [1 / vs[lab]["speedup_vs_v0"][s]["geomean"] for lab in labels]
        ax.plot(range(len(labels)), y, color=color, lw=2, marker="o", ms=6, mec=SURFACE, mew=1.5, label=SPLIT_LABEL[s])
        ends.append((y[-1], s))
    # direct labels at the line ends, nudged apart so they never overlap
    ends.sort()
    lo, hi = ax.get_ylim()
    gap, last = (hi - lo) * 0.065, -1e9
    for y, s in ends:
        pos = max(y, last + gap)
        ax.annotate(f"{SPLIT_LABEL[s].split(' ')[0]}  {y:.2f}", (len(labels) - 1, y), xytext=(len(labels) - 1 + 0.12, pos),
                    color=INK, fontsize=9, va="center", annotation_clip=False)
        last = pos
    band = max(rep["noise"].values())
    ax.axhspan(1 - band, 1 + band, color="#898781", alpha=0.13, lw=0, zorder=0)
    ax.annotate(f"noise ±{100 * band:.1f}%", (-0.15, 1 + band), xytext=(0, 3), textcoords="offset points",
                color=MUTED, fontsize=8)
    ax.axhline(1.0, color="#c3c2b7", lw=1, zorder=0)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_xlim(-0.2, len(labels) - 1 + 0.9)
    ax.set_ylabel("Geomean latency relative to v0")
    ax.set_title("Query latency by engine version (lower is faster)", loc="left", color=INK, fontsize=12, pad=12)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(frameon=False, loc="lower left", labelcolor="#52514e", fontsize=9)
    fig.tight_layout()
    paths.append(out_dir / "latency_by_version.png")
    fig.savefig(paths[-1], dpi=160)
    plt.close(fig)

    # 2. per-template speedup vs v0 (diverging: blue faster, red slower, grey no change)
    if len(labels) > 1:
        rows = [(s, t) for s in _active(rep) for t in rep["split"][s]]
        grid = [[math.log2(vs[lab]["speedup_vs_v0"][s]["templates"].get(t, 1.0)) for lab in labels[1:]] for s, t in rows]
        lim = max(math.log2(1.5), max(abs(x) for row in grid for x in row))  # +-10% stays pale
        cmap = LinearSegmentedColormap.from_list("div", ["#d03b3b", "#f0efec", "#2a78d6"])
        fig, ax = plt.subplots(figsize=(max(5.2, 2.6 + 0.9 * (len(labels) - 1)), 1.1 + 0.27 * len(rows)))
        ax.imshow(grid, cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
        for i, row in enumerate(grid):
            for j, x in enumerate(row):
                ax.text(j, i, f"{2 ** x:.2f}x", ha="center", va="center", fontsize=8,
                        color="#ffffff" if abs(x) > 0.6 * lim else INK)
        ax.set_xticks(range(len(labels) - 1), labels[1:])
        ax.set_yticks(range(len(rows)), [f"{t}  {s}" for s, t in rows])
        ax.set_xticks([x - 0.5 for x in range(1, len(labels) - 1)], minor=True)
        ax.set_yticks([y - 0.5 for y in range(1, len(rows))], minor=True)
        ax.grid(which="minor", color=SURFACE, lw=2)
        ax.tick_params(which="both", length=0)
        ax.xaxis.tick_top()
        for sp in ax.spines.values():
            sp.set_visible(False)
        fig.suptitle("Speedup vs v0 by template", x=0.03, ha="left", color=INK, fontsize=12)
        fig.text(0.03, 1 - 0.62 / fig.get_figheight(), "Blue is faster than v0, red is slower", color="#52514e", fontsize=9)
        fig.tight_layout(rect=(0, 0, 1, 1 - 0.7 / fig.get_figheight()))
        paths.append(out_dir / "speedup_by_template.png")
        fig.savefig(paths[-1], dpi=160)
        plt.close(fig)
    return paths


def write(h: Harness, releases: dict[str, str], out_dir: Path, timed_runs: int | None = None) -> dict:
    rep = evaluate(h, releases, timed_runs)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "report.json", rep)
    (out_dir / "REPORT.md").write_text(markdown(rep))
    try:
        for p in plots(rep, out_dir):
            log(f"wrote {p}")
    except ImportError:
        log("matplotlib is not available; skipped plots")
    return rep
