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

### Length-aware selectivity for substring contains() scan filters

**Hypothesis.** In q09 the scan filter on part is `contains(p_name,'<word>')` (LIKE '%x%' rewritten), stored as an ExpressionFilter. RelationStatisticsHelper::InspectTableFilter (relation_statistics_helper.cpp:446) ignores EXPRESSION_FILTER, so ExtractGetStats falls back to DEFAULT_SELECTIVITY=0.2: part est 400K (actual 109K, 5.4%), so lineitem⋈part is estimated at 12M when it is 3.27M. Because of this the probe pipeline ends up probing two large build sides: orders (15M rows, HASH_JOIN 2.9s CPU) and partsupp⋈supplier⋈nation (8M rows, HASH_JOIN 2.65s CPU). These are the two biggest operators after the lineitem scan (5.0s). Building a 15M/8M-row HT is mostly random memory writes. I forced the flipped plans (disabled_optimizers='join_order,build_side_probe_side' with an explicit join tree) so that lineitem⋈part (3.27M) is the build side and orders/partsupp are probed. Measured operator CPU: orders HJ 2.9s -> 2.0-2.2s, ps HJ 2.65s -> 1.67s. That is before any BF reaches those probe scans; see the other two issues. BuildProbeSideOptimizer::GetBuildSize/TryFlipJoinChildren needs the left estimate below about 10M rows to flip the orders join (narrow 2-col right side, 1.15 right-deep penalty), and below about 4.8M rows to flip the 8M partsupp join (the left side is wider). So the part selectivity estimate has to drop to about 0.06-0.08.

**Plan.** In src/optimizer/join_order/relation_statistics_helper.cpp InspectTableFilter, add `case TableFilterType::EXPRESSION_FILTER`: cast to ExpressionFilter. If `expr` is a BoundFunctionExpression whose function name is `contains` (also accept `like`/`~~` patterns that are '%lit%' with no other wildcards, if they survive to here), with child[0] a column ref (or BoundReferenceExpression) and child[1] a non-NULL VARCHAR BoundConstantExpression with literal length L>=1, return cardinality * clamp(0.2 * 0.75^L, 0.01, 0.2), rounded up, minimum 1. Do NOT match NOT(...) or OR expressions; anything else keeps returning the input cardinality, so the existing default-0.2 path is unchanged. Because ExtractGetStats treats any reduction as 'has_equality_filter', the 0.2 fallback is then skipped for this table. Also check the CONJUNCTION_AND path, since contains may be ANDed with other filters on the same column. Check EXPLAIN on all 4 q09 instances (dark/deep/ghost/aquamarine, L=4..10): lineitem⋈part should become the build side of both the orders join and the partsupp join. Report which flips happened. Then run bench.

**Target files.** src/optimizer/join_order/relation_statistics_helper.cpp

**Expected gain.** q09: -8..-15% (orders and ps joins together save about 1.5-2s CPU of about 14s in forced-plan tests). It is also the enabler for the BF-on-flipped-probe issues, which could bring q09 to about -30%.

**Generality.** Any query with a positive substring predicate (LIKE '%x%', contains) on a dimension table that is joined to a fact table. Today such filters are all estimated at a flat 20%, which hides how selective they are. Longer literals are more selective, the same principle PostgreSQL's like selectivity uses. Plans can change for hidden templates that have positive contains filters. NOT LIKE (q13/q16 style) is excluded and unchanged.

**Risk.** Medium-low. It is estimation only, so correctness is unaffected. A plan regression is possible if the true selectivity of a long literal is much higher than estimated (for example a common word). The 0.01 floor limits how far the estimate can drop.



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
