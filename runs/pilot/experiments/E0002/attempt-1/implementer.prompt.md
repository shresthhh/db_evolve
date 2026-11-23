You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Substring-match scan selectivity (minimal, finish E0001)

**Hypothesis.** q09 (123.8ms, slowest template) builds hash joins on orders (1.5M) and partsupp (800k) while the real probe side is about 324k rows. The cause is that the part scan filter contains(p_name,'ghost'), pushed down from LIKE '%ghost%', is estimated at DEFAULT_SELECTIVITY 0.2 (about 40k rows), but only about 5% of rows pass. EXPLAIN shows estimates of about 1.26M rows for lineitem⋈part⋈orders and 5.06M for the top join. E0001 did not fail as an idea: the implementer ran out of time while building, and it was never benchmarked. If the part estimate drops to about 8k, the join-order optimizer should make the filtered part/lineitem side the build side.

**Plan.** Keep the diff small and out of the header, so the rebuild stays short. In src/optimizer/join_order/relation_statistics_helper.cpp, add a file-local static helper IsSubstringMatchFilter(const TableFilter&). It returns true for an ExpressionFilter whose expression is contains(col, non-empty VARCHAR constant), or ~~/like_escape with a constant pattern that starts with '%' and contains a literal character. It recurses into ConjunctionAndFilter children. It never matches OR, NOT or !~~. In ExtractGetStats (around lines 146-151), when no equality filter applied and some non-optional table filter matches, use selectivity 0.04 (a file-local constexpr) instead of DEFAULT_SELECTIVITY. Leave relation_manager.cpp unchanged in this experiment. Then: build in the background, EXPLAIN q09.m0 and confirm the part estimate falls to about 8k and the join order changes, then run the full bench.

**Target files.** src/optimizer/join_order/relation_statistics_helper.cpp

**Expected gain.** q09: 20-40% if the build sides flip. Other templates with LIKE '%x%' filters on a dimension table (q13-like, q16, q14 variants) may change their plans. Geomean: 1-3%.

**Generality.** Any query with a substring LIKE or contains filter on a table that is joined. Substring filters are usually much more selective than 0.2. A query whose substring filter matches most rows could get a worse join order, since the estimate would be about 5x too low.

**Risk.** Low-medium. Only estimates change, so results stay correct. Plan changes on hidden templates could regress some. Mitigation if results are mixed: apply the lower selectivity only when the literal is at least 3 characters.



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
6. Timing. Interleaved runs against the current best. The bar was fixed in advance: at least
   2.7% faster on the visible geomean, no visible template slower by more than
   10%, and no slowdown on the hidden templates.

So the only changes that survive are ones that make the engine faster for a whole class of
queries. Read `.dbe/knowledge/rules.md` before you start; it is short.

## Working

- `.dbe/knowledge/` has a codebase map, a profiling guide and an optimization playbook.
  `.dbe/queries/` has the visible queries. `.dbe/profile.md` shows where time goes today.
- Shell access is limited to one tool:
  - `/home/shresth/dev/db_evolve/bin/dbe-tool build` builds your working tree incrementally and prints compiler errors.
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
- Do not commit; the harness commits your working tree when you finish.

## When you finish

Return `status` (`ready` if the tree builds and you want it judged, `abandon` otherwise),
`summary` (what you changed and the before/after numbers you measured), `generality` (the class of
queries this helps and the cases where it does not apply), and `notes` (anything the planner
should remember: dead ends, surprises, follow-up ideas).

## Budget

This session is capped at about $12.00 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
