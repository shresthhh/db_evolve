You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q09` (instances are in `.dbe/queries/`). The only timing that
counts is on these visible templates. Other kinds of queries may
get slower, but every query must still return correct results, and it is checked on many query
shapes you cannot see.

The code must stay general in what it refers to. Specialise to the *shape* of the query (its
operators, join structure, kinds of predicates and aggregates, data types, cardinalities), never to
names: no table or column names, no literal values from the queries, no knowledge of this dataset
(row counts, value distributions), and no caching of results across executions. A condition that
only this shape of query meets is fine here; a condition that names this query is not. Parameter
values change between runs and the data size changes, so anything tied to either will fail.


## The issue

### Lower cardinality estimate for substring/LIKE table filters

**Hypothesis.** In q09 the scan on the filtered dimension table (contains(name,'word'), from LIKE '%word%') gets DEFAULT_SELECTIVITY 0.2 in RelationStatisticsHelper::ExtractGetStats. The real selectivity is about 5% (est 400K rows, actual 109K). That inflates every estimate above it: fact⋈dim is estimated at 12M (actual 3.27M) and the top 2-key join at 47.9M (actual 3.27M). As a result BuildProbeSideOptimizer builds hash tables on the big sides: 15M orders (HASH_JOIN 2.49s cumulative) and 8M partsupp⋈supplier⋈nation (2.29s), each probed with only 3.27M rows. I set disabled_optimizers='join_order,build_side_probe_side' and wrote the joins by hand so that the small intermediate is the build side of both joins: EXPLAIN ANALYZE total went from 1.40s to 0.725s on the same tool. Substring matching on free text is selective in general, and Postgres-style estimators give LIKE patterns much lower selectivity than plain range filters.

**Plan.** In src/optimizer/join_order/relation_statistics_helper.cpp, ExtractGetStats, lines 119-155: when a non-optional table filter is an ExpressionFilter (TableFilterType::EXPRESSION_FILTER, possibly inside a ConjunctionAndFilter) whose expression is a BoundFunctionExpression named contains / like / ~~ / ilike / ~~* / regexp_matches / suffix (with a constant pattern argument), apply a lower selectivity, e.g. a new constant STRING_PATTERN_SELECTIVITY = 0.05 in relation_statistics_helper.hpp, instead of DEFAULT_SELECTIVITY. Keep the existing rule that an equality filter estimate wins (MinValue). If the expression is anything else, behaviour stays exactly as it is now. Then check the q09 EXPLAIN: the part-side estimate should be about 100K and the orders/partsupp joins should flip or be reordered. If the partsupp join still builds on the 8M side because the 2-key join estimate counts only one key, record that in the ledger as a follow-up; don't widen this diff.

**Target files.** src/optimizer/join_order/relation_statistics_helper.cpp, src/include/duckdb/optimizer/join_order/relation_statistics_helper.hpp

**Expected gain.** q09: 20-45% if both big builds flip (the hand-written plan measured 1.40s down to 0.73s); about 15-20% if only the orders join flips.

**Generality.** Any star or snowflake join where a dimension is filtered by LIKE '%x%', contains, or a suffix/regex filter: the join order and build side improve. Could get slower: queries whose substring filter is not selective (e.g. LIKE '%a%'), where a big table might now be chosen as the build side by mistake. Results stay correct because only plan choice changes.

**Risk.** Low for correctness, since this only changes estimates. Medium for performance on unseen queries that have unselective LIKE filters. Plan changes can also shift other templates in either direction.



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
   at least one visible template at least 5% faster (more if its timings are noisy), no visible template slower beyond its noise, and the visible geomean not slower. Templates you cannot see are not timed in this run; they only have to stay correct.

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
