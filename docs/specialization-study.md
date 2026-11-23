# Specialisation study: how much speed does generality cost?

## Result of the pilot (22 Nov 2026)

No merge cost on the 8-template pilot: one merged system 1.540x, per-template systems 1.514x,
k = 2 1.527x, k = 4 1.492x (geomean over the eight templates). Details in `plan.md` (Phase 2b,
pilot findings) and `results/spec-cross-merged/`.

## Question

Each TPC-H template gets its own copy of DuckDB, evolved for that template alone. Merging their
changes back into fewer systems should lose some of the gain, because the changes conflict. How
much is lost when everything goes into one system, and how much comes back when 2, 4 or 8
systems are allowed? Hypothesis: as the number of systems k grows, performance moves from the
single merged system toward the per-template systems.

## Rules (unchanged from the main loop, except what is timed)

- A specialised system may target the **shape** of its query: operators, join structure, kinds
  of predicates and aggregates, data types, cardinalities.
- It may **not** know the schema or the data: no table or column names, no literals from the
  queries, no row counts or value distributions, no caching of results across executions.
  Otherwise the extreme case (recognise the query, return a stored answer) would pass.
- Enforced by:
  - the static audit;
  - the reviewer, who is told the rule;
  - hidden parameter bindings of the target template;
  - a second dataset (SF 1);
  - correctness on **every other template** (84 more queries, on both datasets);
  - the generic SQL suite.
- Only the target template is timed. Other templates may get slower; they must stay correct.
- A merged system follows the same rules. Where two changes disagree, it may choose between them
  only from general properties of the query or plan, never from which query is running.

## Steps and commands

All runs start from v0 (DuckDB v1.5.6). Each one gets its own branch, so nothing touches
`dbe/evolve` or other runs. One step at a time: everything that times queries holds a
machine-wide lock, and other load on the machine adds noise. Keep the machine awake.

### Pilot: eight templates, k = 1, 2, 4, 8

`scripts/run_spec_pilot.sh` runs every step below in order. It waits for anything else that is
timing, tests the merge step with the scripted agent first, and can be re-run after an
interruption. Log: `work/logs/spec-pilot.log`.

Templates, chosen for varied query shapes and low timing noise (A/A noise in brackets):

| Template | Shape | Noise |
| --- | --- | ---: |
| q01 | scan and aggregate | 1.5 % |
| q02 | correlated subquery (minimum cost) | 5.2 % |
| q09 | six-way join with `LIKE` | 5.7 % |
| q13 | outer join with `NOT LIKE` | 9.2 % |
| q16 | `NOT IN` subquery, distinct counts | 5.3 % |
| q18 | `IN` subquery with a large aggregate | 3.3 % |
| q19 | OR of AND predicates over a join | 4.9 % |
| q21 | `EXISTS` / `NOT EXISTS` | 2.6 % |

| # | Step | Command | Time (estimate) |
| --- | --- | --- | --- |
| 1 | Specialise each template, 6 rounds each | `bin/dbe specialize q01 q02 q09 q13 q16 q18 q19 q21 --rounds 6` | 16-32 h |
| 2 | Time v0 and the eight systems on all 22 templates | `bin/dbe crosseval --prefix spec --out spec-cross` | about 1 h |
| 3 | An agent chooses the groups for each k | `bin/dbe groups q01 q02 q09 q13 q16 q18 q19 q21 --k 1 2 4 8` | minutes |
| 4 | Merge each multi-template group (k = 8 is the specialised systems) | `bin/dbe merge-groups --k 1 2 4 8` | 4-6 h (up to 7 merges) |
| 5 | Time every system: specialised, merged, v0, and the jointly evolved v3 | `bin/dbe crosseval --prefix spec --with-merges --also sf10 --out spec-cross-merged` | about 2 h |
| 6 | Speedup against the number of systems | `bin/dbe curve` | seconds |

- `bin/dbe status --run spec-q09` prints any run's ledger.
- `bin/dbe specialize` resumes a run that was interrupted.
- To run the specialisation one template at a time, give `specialize` a single template.

### Full study: all 22 templates

1. Measure noise for the five templates that were test-only:
   `bin/dbe calibrate --templates q06 q10 q12 q15 q20 --repeats 4` (about 30 minutes).
2. `bin/dbe specialize <all 22> --rounds 6`. This takes 2 to 4 days of machine time and is the
   step most likely to hit plan usage limits; interrupted runs resume.
3. Steps 2-6 as in the pilot, for all 22 templates. That is up to 15 merges (k = 1: 1, k = 2: 2,
   k = 4: 4, k = 8: 8, minus any one-template groups).

## How each piece works

**Specialise (`specialize`).**
- One ordinary evolution run per template (`runs/spec-<t>`, branch `dbe/spec/<t>`).
- Planner, implementer and reviewer as before. Their instructions say the run targets one query
  shape and repeat the rules above.
- Each round is: profile → planner picks an issue → implementer → gates → review → timing on the
  template's 4 bindings → accept or retire.
- 6 rounds = 6 experiments, all on that one template.
- Acceptance: the template is faster by more than max(5 %, 1.5 × its A/A noise).

**Group (`groups`).**
- A grouper agent gets each specialised system's full diff, the summaries of its accepted
  changes, the files it touches, and its speedup on its own template.
- It splits the templates into exactly k groups:
  - together: diffs that are compatible (different code, or the same direction);
  - apart: diffs that conflict;
  - when it has to compromise, it protects the largest gains.
- It returns the groups and its reasons, which are kept in `results/spec-cross/groups.json`.
- A seeded random grouping is written next to it as a baseline. Merging those groups too
  (`merge-groups --method random`) shows whether the agent's choice matters. It is optional and
  costs as many merges again.
- `--method cluster` groups by the cross-evaluation matrix instead.

**Merge (`merge`, `merge-groups`).**
1. The group's changes are cherry-picked onto v0 in order. Those that conflict are left out.
2. A merge agent (the implementer, with a merge task) gets the result plus every source patch. It:
   - applies the patches that did not apply cleanly;
   - reconciles logic that overlaps;
   - may guard or drop a change that hurts another template in the group, and must say which and why.
3. The usual gates and review follow, then timing against v0 on the group's templates.
4. The merged system is evaluated even if it misses the bar against v0, as long as it passed the
   gates. Its record shows what was dropped and why.

**Cross-evaluate (`crosseval`).** Every system is timed on all 22 templates with 4 bindings each.
Passes are interleaved, and v0 is timed a second time as a control for noise. The result is a
system × template speedup matrix:
- the diagonal is each system's gain on its own template;
- the rest of each row is what that specialisation costs or gives elsewhere.

**Curve (`curve`).** For each k, every template runs on its own group's system. The result is the
geomean speedup over the study's templates.

## What we report

1. **Main plot:** geomean speedup against k, with these lines:
   - agent grouping;
   - random grouping (if run);
   - the per-template systems (k = number of templates);
   - v0 (1.0);
   - joint evolution on all templates (`runs/sf10` v3);
   - the report's noise band.
2. **Share of the specialised gain kept:** log(speedup at k) / log(speedup of the per-template
   systems), for each k.
3. **Per-template table** for each k: which templates lose the most in a merge.
4. **The cross matrix** from step 2: how specialised each system is.
5. **Merge records:** conflicts, what the merge agent guarded or dropped, and any wrong results
   caught by the gates.

## Limits to keep in mind

- The pilot has eight templates, and noise per template is 2 to 18 %. Gains below a template's
  noise threshold do not show up.
- Six rounds per template is a fixed effort. Some templates will not get any accepted change and
  stay at v0. They still count in the curve as 1.0.
- The merge agent's skill affects the result. A poor merge looks like a "conflict" cost. The merge
  records say which changes were dropped, so the two can be told apart.
- Grouping is chosen from the diffs, before the merged systems exist. An agent that also sees the
  cross matrix may group better; that is a follow-up.
