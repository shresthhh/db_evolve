You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Lower cardinality estimate for substring-match table filters

**Hypothesis.** Every non-equality table filter is costed with a flat DEFAULT_SELECTIVITY=0.2 (relation_statistics_helper.cpp:146-151; same constant in relation_manager.cpp:199/258/276/293/374 for filters left in a LogicalFilter). A predicate that requires a literal substring (contains(col,'lit'), col LIKE '%lit%', LIKE '%a%b%') is usually far more selective than a range comparison. Evidence from q09: p_name LIKE '%ghost%' is actually about 5% selective. EXPLAIN estimates 1,256,266 rows for lineitem⋈part⋈orders and 5,057,324 for the top join, but EXPLAIN ANALYZE shows 324,507 rows, a 4-15x overestimate. Because of that the optimizer builds hash tables on orders (1.5M rows) and on partsupp⋈supplier⋈nation (800k rows), and each of those two joins costs about 0.22-0.23s CPU, while the real probe side is only 324k rows. With a better estimate the join order and build sides can put the small filtered side on the build side.

**Plan.** In RelationStatisticsHelper::ExtractGetStats (src/optimizer/join_order/relation_statistics_helper.cpp, around lines 119-155), when no equality filter fired, check whether any non-optional table filter is an ExpressionFilter whose expression is a positive substring-containment test: a BoundFunctionExpression named 'contains', or '~~' / 'like_escape' whose constant pattern starts with '%' and contains at least one non-wildcard character, possibly nested under CONJUNCTION_AND. Do not match negations (!~~, NOT). If one is found, use base_cardinality * SUBSTRING_MATCH_SELECTIVITY, defined as DEFAULT_SELECTIVITY*DEFAULT_SELECTIVITY (0.04) in relation_statistics_helper.hpp, instead of 0.2. Apply the same classification in relation_manager.cpp where a LogicalFilter's expressions fall back to DEFAULT_SELECTIVITY: add a small static helper IsSubstringMatchPredicate(const Expression&) to RelationStatisticsHelper and reuse it in both places. Before and after the change, check with EXPLAIN on q09/q16 that the estimates move and that the join order changes. Run the full visible bench, since plans may change elsewhere.

**Target files.** src/optimizer/join_order/relation_statistics_helper.cpp, src/include/duckdb/optimizer/join_order/relation_statistics_helper.hpp, src/optimizer/join_order/relation_manager.cpp

**Expected gain.** q09 (18% of total): possibly 20-40% if the orders/partsupp builds shrink or the join order changes. Smaller effects possible on q16 (s_comment LIKE '%..%..%' under NOT IN) and on other templates with LIKE '%x%' on a dimension table. Roughly 3-8% on the visible geomean if q09 moves.

**Generality.** Any star or snowflake join where a dimension is filtered by a substring/contains predicate (text search on names or comments) now gets a realistic, smaller cardinality, so it is placed on the build side and joined early. Possible regressions: substring predicates that are actually unselective (for example '%a%') will be underestimated, which could put a big relation on the build side. That risk is bounded because the build-side flip and the hash join still work correctly, only slower.

**Risk.** Medium. The change only affects cost estimates, so results stay correct, but plans for other templates may change, possibly for the worse. The selectivity constant is a heuristic derived from DEFAULT_SELECTIVITY, not tuned to the data. If the bench shows a mixed result, try applying it only when the literal has at least 3 characters before giving up.



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
