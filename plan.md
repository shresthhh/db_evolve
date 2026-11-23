# Plan

Goal: show that an agentic loop can evolve DuckDB into measurably faster versions (v1, v2, v3)
for a workload, with the gain holding on query templates the agents never saw.

Status key: done, next, later.

## Phase 0: foundation (done)

- [x] Read the sources in `docs/` and the Intent Lab post; notes in `docs/related-work.md`.
- [x] Architecture: `docs/architecture.md`.
- [x] Project-local toolchain without sudo (`scripts/bootstrap_toolchain.sh`).
- [x] Engine adapter: clone DuckDB v1.5.6, worktree slots, incremental ccache builds, binaries
      stored by commit.
- [x] TPC-H as 22 parameterised templates with seeded bindings; template split 14 / 3 / 5.
- [x] Harness: per-binary data loading, external clock, reference results, interleaved A/B
      timing, noise calibration, acceptance bar.
- [x] Gates: path policy, static audit, correctness on hidden bindings and a second dataset,
      generic SQL suite.
- [x] Agents: Claude Code headless driver, planner / implementer / reviewer prompts, knowledge
      library, `dbe-tool`.
- [x] Loop with ledger, issue backlog, planner memory, releases; report with tables and plots.
- [x] Pipeline exercised end to end with the mock backend.

## Phase 1: first real run with Opus 5.5 (done: `runs/pilot`)

The first run is about the framework, not the speedup.

1. `bin/dbe evolve --run pilot --generations 1 --rounds 3`. Budget cap per run is roughly
   rounds x (planner + (1 + max_fix_attempts) x implementer + reviewer) from `[agents]`.
2. Read every artifact of the pilot by hand: planner issues (are they grounded in the profile?),
   implementer diffs, reviewer findings, gate feedback. Fix prompts and tooling where agents
   wasted effort.
3. Things to watch for and tune:
   - time per experiment (build + gates + timing) and where it goes;
   - how often gates versus review versus the bar retire an experiment;
   - measurement noise. On the development machine (WSL2) A/A runs at SF 1 differ by 0.1 to 1.4 %
     on the train geomean and up to 4 % on the 3-template validation split, with queries taking
     only 20 to 120 ms. If small real gains keep getting retired, raise the scale factor (SF 10
     makes queries about ten times longer), add timed runs, or move timing to a quiet machine;
   - whether permission denials block legitimate agent actions.

Exit: at least one experiment travels the whole path with sensible artifacts, accepted or retired.

### Phase 1 findings (pilot, `runs/pilot`)

- Six experiments cost $7.91 in total ($0.4 to $1.8 each). The pipeline, the gates and the review
  behaved as designed. Fixed during the pilot: builds outlasting the agent's shell timeout (now
  polled), agents trying blocked shell commands, abandoned diffs not being saved.
- **Measurement is the bottleneck.** E0004 (lazy perfect-hash aggregate tables) measured -0.3 % in
  the loop and -2.4 % train / -3.2 % test on a careful 8-pass recheck. Changes to make first:
  1. Raise the scale factor to SF 10 so queries run 0.2 to 1.5 s and relative noise drops.
  2. Re-time borderline candidates (within 2x the required gain) with more passes before deciding.
  3. Reconsider a geomean-only bar: a change that makes one template 20 % faster and nothing
     slower is a real improvement. Alternative: accept when some templates improve beyond their
     own A/A noise and none regress beyond it.
- The machine slept overnight during one experiment; the timeout clock pauses with it. Keep the
  machine awake during runs.

## Phase 2: three generations on TPC-H (first pass done: `runs/sf10`)

Done with all three Phase 1 changes (SF 10, borderline re-timing, per-template bar):
3 generations x 2 rounds, $10.04, five of six experiments accepted, v3 = 1.156x train,
1.158x validation, 1.025x test. Results are in the README "Status" section and in `results/sf10/`.

Still to do:

1. More rounds per release: 6 to 8 instead of 2 (the budget cap is gone; model use comes from
   plan credits). Joint evolution should move to TPC-DS, whose 99 templates allow a split with
   real variety (about 60 / 15 / 24). That needs parameter generators for the hidden bindings;
   until then the second dataset and the audit carry the anti-hardcoding load.
2. Re-run `bin/dbe report` on a quiet machine and with more passes. The test gain (2.5 %) is
   close to the report's own noise, and q16 at v3 (0.95x) needs a check: real regression from
   E0012 or noise.
3. Draw the noise band per split on the latency plot (it currently uses the largest split noise).
4. Write up the accepted diffs one by one: which ones would be upstreamable to DuckDB.

### Phase 2 findings (`runs/sf10`)

- **The test gap is about coverage, not overfitting.** The accepted changes target query shapes
  (substring filters feeding joins, OR-of-AND predicates, correlated EXISTS/NOT EXISTS, semi/anti
  join filters). The hidden validation template q21 has the EXISTS/NOT EXISTS shape and got 1.49x
  faster without agents ever seeing it. The five test templates mostly do not have these shapes
  (q06 is a single scan, q12/q10 plain joins), so little moved there, and nothing got slower.
  A test set chosen at random from 22 templates is too small to tell "generic but narrow" from
  "overfitted"; a larger or synthetic workload with shape-matched held-out templates would.
- The per-template bar did what it was meant to: every accepted change had its gain on specific
  templates (q09, q14/q19, q02/q04/q22, q18/q22), which the geomean bar would have diluted.
- Re-timing settled two borderline results (E0008, E0011) that a single 4-pass timing had flagged
  as regressions just past their thresholds.
- Cost per experiment: $0.35 to $2.26; E0012 took 2 h 20 min of wall time (large build changes).

### Ablation of the SF 10 run (`results/sf10-ablation`)

Each accepted change applied alone to v0 and removed alone from v3, timed on all 22 templates
(noise in that report: train and val ±0.8 %, test ±3.3 %):

- E0008 (contains-filter selectivity) alone: q09 1.58x. E0009 (multi-key bloom filters) alone:
  nothing; on top of E0008 it takes q09 from 1.58x to 1.93x. The two only work together.
- E0010 (OR-derived filters) alone: q19 2.0x. E0011 (deliminator) alone: q04 1.34x, q22 1.26x,
  hidden q21 1.40x. E0012 adds q22 1.26x to 1.44x.
- Test templates: v3 0.975x, inside the ±3.3 % noise. The 1.025x in the first report was noise
  too, and so was the q16 slowdown. Each change helps the query shapes it was written for and
  leaves the rest alone; TPC-H's five test templates do not share those shapes.

## Phase 2b: the specialisation study (TPC-H)

Full plan with commands: [docs/specialization-study.md](docs/specialization-study.md).

Question: how much speed does generality cost? Evolve one system per template, merge them back,
and measure how performance changes with the number of systems allowed.

Rules: the code-generality rule stays. A specialised system may target the *shape* of its query
(operators, join structure, predicate and aggregate kinds, types, cardinalities) but may not name
tables, columns or literals, know the dataset, or cache results. Hidden parameter bindings and the
second dataset still apply, and every other template must still return correct results (they may
get slower).

1. `bin/dbe specialize q01 q09 ... --rounds 6`: one run per template from v0 (`runs/spec-<t>`,
   branch `dbe/spec/<t>`). Visible set = that template; timing only on it.
2. `bin/dbe crosseval --prefix spec`: v0 and every specialised system timed on all 22 templates.
   The diagonal is each system's gain on its own template; the rows show what specialising cost
   everywhere else.
3. `bin/dbe groups --k 1 2 4 8`: an agent reads the specialised diffs and chooses which to
   group for each target number of systems k (compatible diffs together, conflicting ones apart).
   A seeded random grouping is written alongside as a baseline; `--method cluster` groups by the
   cross matrix instead.
4. `bin/dbe merge --name k2-a --group q01,q13`: cherry-pick the group's changes onto v0, then a
   merge agent applies whatever conflicted and reconciles overlapping logic, choosing between
   behaviours only from general query or plan properties. Same gates, review and timing.
5. Cross-evaluate the merged systems. Plot geomean speedup against the number of systems k (1, 2,
   4, 8, all), clustered against random grouping, with v0 and joint evolution (`runs/sf10` v3) as
   reference lines. Hypothesis: the curve rises from the k = 1 merge toward the per-template
   systems.

Pilot first with eight templates (q01 q02 q09 q13 q16 q18 q19 q21), k in {1, 2, 4, 8}:
`scripts/run_spec_pilot.sh`. Then all 22 (needs noise calibration for the five templates that
were test-only).

### Pilot findings (`results/spec-cross-merged`, 22 Nov)

- Specialised systems on their own template (cross-evaluation): q01 1.17x, q02 1.96x, q09 2.16x,
  q13 1.62x, q16 1.13x, q18 1.19x, q19 2.12x, q21 1.21x; geomean 1.514x. 48 experiments, about $81.
- Agent grouping, geomean over the 8 templates: k = 1 1.540x, k = 2 1.527x, k = 4 1.492x, k = 8
  1.514x. **No merge cost**: the curve is flat within about 3 %. The diffs mostly touch different
  code; where they overlapped (join bloom filters q09/q21, perfect-hash aggregates q01/q13) the
  merge agent reconciled them by hand and dropped nothing. Some gains stack (q09 2.16x -> 2.50x,
  q21 1.21x -> 1.31x merged); small losses on q02, q18, q01.
- The k = 1 system on the whole workload: train 1.194x, val 1.137x, test 1.140x (q15 1.44x, q20
  1.20x), against joint evolution's 1.161x / 1.132x / 0.996x. Confounded by effort: 48
  experiments against 6.
- Specialisation cost elsewhere is mostly small; the exception is the q13 system (q17 0.38x, q14
  0.65x, q19 0.62x). The grouping agent kept q13 apart from q19 from the diffs alone.
- Next: (a) the same study on TPC-DS, where 99 templates make real conflicts likely;
  (b) an equal-effort joint-evolution control (48 experiments on all train templates); (c) merge
  the random grouping as the baseline, which matters only once grouping has an effect.

## Phase 3: stronger evidence (later)

- **Ablations**, following VibeServe and JetStream: single agent without a separate reviewer; no
  knowledge library; no ledger or memory; no hidden-template gate (how much does train-only
  acceptance overfit?).
- **TPC-DS**: 99 templates give a far better split (about 65 / 14 / 20). Needs `dsqgen` for
  parameterised instances; the toolchain can build it.
- **A workload the model cannot have memorised** (SEC-EDGAR as in GenDB-V and JetStream, or a
  generated schema and query set).
- **Cross-workload test**: evolve on TPC-H, evaluate on TPC-DS and ClickBench without retraining.
- **Larger scale factors** and a cold-run metric; load time and database size as reported
  side metrics (already recorded per version).
- **Engine's own test suite** as an extra gate (build `unittest`, run the fast group).

## Phase 4: scale and self-improvement (later)

- Parallel experiments: several slots, with builds on any core but timing on a quiet, dedicated
  machine or pinned cores.
- Quick check before the full experiment (Intent Lab's biggest throughput gain): a cheap
  prototype measurement that can retire an idea before review and full timing.
- Stacking and revisiting: re-test retired ideas after the engine has changed; periodically
  re-measure the current best against v0 to catch drift from compounding noise.
- An operations loop that reads the ledger and proposes changes to prompts, gates and workflow,
  each landed through its own review.
- Workload-specialised branches: evolve separate lines for different workloads and compare.

## Open questions

- Is the geomean of template latency the right objective, or should it be total time, or a
  weighted mix closer to a real workload's query frequencies?
- With only 3 validation templates on TPC-H, the hidden gate is coarse. Use cross-validation over
  templates across generations, or move to TPC-DS sooner?
- How much of any gain is "DuckDB had not got to it yet" versus real specialisation? Check
  accepted changes against upstream DuckDB commits after v1.5.6.
