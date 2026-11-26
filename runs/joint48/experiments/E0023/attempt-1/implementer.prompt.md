You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Deliminate selective ANTI delim joins (NOT EXISTS) with simple RHS

**Hypothesis.** q22 (152ms) runs NOT EXISTS (SELECT * FROM orders WHERE o_custkey=c_custkey) as a RIGHT_DELIM_JOIN (RIGHT_ANTI). Its RHS still contains INNER HASH_JOIN o_custkey = c_custkey(DELIM_SCAN). The Deliminator keeps that join because the LHS (customer) has a selection, and SelectionIsReplaceableByJoinFilter (src/optimizer/deliminator.cpp:81) only accepts delim_join.join_type == SEMI. Warm JSON profile of q22.m0, total CPU about 0.8s: two customer scans 0.155s + 0.160s, orders scan 0.081s (it already has a BF and emits 1.9M rows), INNER HJ with the delim keys 0.137s (1.9M -> 1.9M rows, it filters nothing), RIGHT_ANTI HJ 0.144s, delim join overhead 0.040s, plus a DISTINCT HASH_GROUP_BY 0.012s. E0021 showed the same mechanism for SEMI: a plain join plus runtime join filters (min/max + BF on the probe scan, enabled for RIGHT_SEMI/RIGHT_ANTI in E0021) gives the same reduction without the extra join. With ANTI accepted, orders goes from scan+BF straight into a RIGHT_ANTI built on the 190k filtered customers. That removes the 0.137s inner HJ, the delim materialization/dedup and the delim scan.

**Plan.** In src/optimizer/deliminator.cpp, SelectionIsReplaceableByJoinFilter: accept delim_join.join_type == JoinType::ANTI as well as SEMI. Keep every other guard unchanged (one delim get, one join, INNER/SEMI child join with only colref = colref conditions, SubqueryIsSimple RHS). Optimize() then removes the join with the DelimGet. RemoveJoinWithDelimGet adds IS NOT NULL on the replacing columns. ConvertNotDistinctToEqual turns NDF into = when the RHS column is non-null, so the join filters can be generated (NDF conditions are skipped in JoinFilterPushdownOptimizer::GenerateJoinFilters). Before relying on the NDF->= conversion for ANTI, check semantics: an LHS row with a NULL key must still be emitted, both in ANTI (probe side LHS) and in RIGHT_ANTI (build side LHS, emitted by the unmatched-build scan). Check how JoinHashTable handles NULL build keys for RIGHT_ANTI (null_values_are_equal / the build-side null filtering in join_hashtable.cpp). If NULL build keys are dropped for RIGHT_ANTI, do not convert to = for ANTI; it may then need an explicit IS NOT NULL OR ... rewrite, or just skip the conversion and accept no BF. Tests: (1) a temp table customer-like with NULL keys plus NOT EXISTS over a table with NULL fk values; compare against SET disabled_optimizers='deliminator'. (2) q22 results unchanged. (3) A NOT EXISTS with an extra non-equality correlated predicate (q21 shape) must keep the old plan. Use the JSON profile trick to confirm the INNER HJ and DELIM_JOIN are gone from q22 and that the orders scan still has the BF.

**Target files.** src/optimizer/deliminator.cpp

**Expected gain.** q22 -12..-20% (about 0.18s of 0.8s CPU removed). Geomean about -1%. Possibly hidden NOT EXISTS templates (q21-like ones stay unchanged because of the equality-only guard).

**Generality.** Any correlated NOT EXISTS with a simple equality correlation and a filtered outer query (anti-joins against fact tables are very common). Could be slower when the outer selection is very selective and the BF auto-disables. In that case the old delim join reduced the RHS before an expensive RHS subtree. SubqueryIsSimple limits the RHS to scans/filters/projections/inner joins, so the extra cost is bounded.

**Risk.** Medium-low. One-line gate change on a path already proven for SEMI in E0021. Main risk is NULL-key semantics for ANTI after the NDF->= conversion; the plan includes explicit tests.



## How your change will be judged

After you finish, an automated harness that you cannot influence does the following, in order.
Failing any step sends the change back to you or retires it.

1. Path policy. Only files under `src/`, `extension/parquet/`, `extension/core_functions/` may change; `test/`, `benchmark/`, `tools/`, `scripts/`, `extension/tpch/`, `extension/tpcds/`, `.github/` are off limits.
2. Static audit. Added lines must not mention the workload: no table or column names, no query
   literals, no benchmark names.
3. Build. Release build of the whole engine.
4. Correctness. Results must equal the original engine's on the visible queries, on new parameter
   values for those queries, on query templates you have never seen, on a second dataset of a
   different size, and on a suite of generic SQL over an unrelated schema.
5. Review. An independent reviewer reads your diff looking for benchmark-specific shortcuts and
   correctness holes.
6. Timing. Interleaved runs against the current best. The bar was fixed in advance:
   at least one visible template at least 5% faster (more for templates whose timings are noisy); no template, visible or hidden, slower by more than 5% (again more for noisy ones); and the visible geomean not slower. A change that makes one kind of query clearly faster and nothing slower is accepted.

So the only changes that survive are ones that make the engine faster for a whole class of
queries. Read `.dbe/knowledge/rules.md` before you start; it is short.

## Working

- `.dbe/knowledge/` has a codebase map, a profiling guide and an optimization playbook.
  `.dbe/queries/` has the visible queries. `.dbe/profile.md` shows where time goes today.
- Shell access is limited to one command, `/home/shresth/dev/db_evolve/bin/dbe-tool`. Anything else (python, grep, find, cd, pipes,
  git) is blocked, so do not spend turns on it: search code with the Grep and Glob tools, read with
  Read, edit with Edit. Never run anything in the background: this is a non-interactive session
  and it ends as soon as you stop to wait.
  - `/home/shresth/dev/db_evolve/bin/dbe-tool build` builds your working tree incrementally and prints compiler errors. A rebuild
    after a header change can take 10 to 15 minutes. The command returns after about two minutes
    with `BUILD RUNNING`; call it again until it prints `BUILD OK` or `BUILD FAILED`.
  - `/home/shresth/dev/db_evolve/bin/dbe-tool bench [template ...]` checks results and times the visible queries, your build
    against the current best. Without arguments it runs all visible templates.
  - `/home/shresth/dev/db_evolve/bin/dbe-tool profile <instance>` prints the query plan with per-operator timings from your build
    (instance ids look like `q06.m0`; `/home/shresth/dev/db_evolve/bin/dbe-tool queries` lists them).
  - `/home/shresth/dev/db_evolve/bin/dbe-tool sql "<statement>"` runs one statement on your build against the benchmark database
    (read-only).
- Measure before and after. If the profile does not show the cost you expected, say so and stop
  rather than shipping a change with no effect: finish with status `abandon` and explain what you
  found. That is a useful result, and it is recorded.
- Keep the diff as small as the idea allows and follow the surrounding code's conventions. New
  source files must be added to the directory's `CMakeLists.txt`.
- Think about inputs the visible queries never exercise: NULLs, empty inputs, other types, values
  at the limits of what your fast path handles, out-of-memory spilling, parallel execution. The
  hidden checks do.
- Do not commit or revert; the harness commits your working tree when you finish, or saves it for
  the record and resets the tree if you abandon.
- Prefer changes to `.cpp` files over headers where the idea allows: they rebuild in a minute or
  two instead of ten or more.

## When you finish

Return `status` (`ready` if the tree builds and you want it judged, `abandon` otherwise),
`summary` (what you changed and the before/after numbers you measured), `generality` (the class of
queries this helps and the cases where it does not apply), and `notes` (anything the planner
should remember: dead ends, surprises, follow-up ideas).

## Budget

This session is capped at about $15.00 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
