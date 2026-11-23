You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Deliminator: drop the delim join for SEMI/ANTI subqueries without blocking operators even when the LHS has a selection

**Hypothesis.** q04 (319ms, 4th slowest) runs EXISTS as a RIGHT_DELIM_JOIN (0.30s) + INNER join lineitem x DELIM_SCAN (0.17s) + RIGHT_SEMI join (0.17s) + a dedup HASH_GROUP_BY on the delim side. Deliminator::Optimize (src/optimizer/deliminator.cpp:66) deliberately keeps the deepest join with the DelimGet when HasSelection(delim_join) is true (orders has a date filter). The idea is that the delim set reduces expensive RHS work. For a plain EXISTS/NOT EXISTS whose RHS is only scans, filters and projections, that reduction buys nothing a single hash semi/anti join does not already do. MANUAL REWRITE TEST: q04 written as `orders SEMI JOIN (SELECT l_orderkey FROM lineitem WHERE l_commitdate<l_receiptdate)` gives the same result in 283/220/210ms hot, against 303/~300ms for the EXISTS form. A q22-style NOT EXISTS (customer with a filter, anti join to orders) went from 89ms to 61/63ms with the same count of 27085.

**Plan.** In Deliminator::Optimize (deliminator.cpp:58-71), compute `keep_deepest = !candidate.joins.empty() && HasSelection(delim_join)` as now, then add an exception. Set keep_deepest = false when (a) delim_join.join_type is JoinType::SEMI or JoinType::ANTI, and (b) the RHS subtree delim_join.children[1] contains no LOGICAL_AGGREGATE_AND_GROUP_BY, LOGICAL_WINDOW, LOGICAL_LIMIT, LOGICAL_ORDER_BY, LOGICAL_TOP_N, LOGICAL_DISTINCT or nested LOGICAL_DELIM_JOIN. Write (b) as a file-local static recursive helper, not a header change. In those cases the delim provides no pruning before a blocking operator. Keep everything else unchanged, so scalar or aggregate subqueries (q02, q17, q20) still keep the deepest join. Validate: EXPLAIN q04 should show a single HASH_JOIN SEMI/RIGHT_SEMI between orders and lineitem with no RIGHT_DELIM_JOIN. Check that the condition is plain equality, or that IS NOT DISTINCT FROM does not block the BF or perfect HT, and whether a join BF/min-max filter reaches the lineitem scan. Compare results for q04, q21 and q22 with the old build. Also try EXISTS with an extra correlated inequality, and NOT EXISTS with NULL keys (check that the IS NOT NULL filter handling at :217-225 stays correct for ANTI). Then bench.

**Target files.** src/optimizer/deliminator.cpp

**Expected gain.** q04 about -25% (300 -> about 215ms), and q22 if its NOT EXISTS has this shape (ANTI test -30%). About -2 to -3% visible geomean. Hidden EXISTS/NOT EXISTS/IN-without-aggregate templates (q21-like, q16 NOT IN maybe) also stand to gain.

**Generality.** Any correlated EXISTS / NOT EXISTS / IN subquery with simple equality correlation and a filtered outer table. This is a very common analytical pattern. Could get slower: cases where the RHS is a multi-join chain, because the preserved inner join with the delim set acted as an early filter for joins higher in the RHS. Join BFs and dynamic filters should mostly cover that, which is why condition (b) excludes blocking operators but allows joins. If a regression shows up, tighten (b) to also forbid joins in the RHS.

**Risk.** Low-medium. It is a one-file optimizer heuristic change that reuses the existing removal path, which is already exercised whenever the LHS has no selection, so correctness risk is small (the main checks are ANTI and NULL semantics). Performance risk is limited to the multi-join-RHS case described above.



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

This session is capped at about $5.68 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
