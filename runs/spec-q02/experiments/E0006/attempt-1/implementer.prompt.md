You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q02` (instances are in `.dbe/queries/`). The only timing that
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

### Rewrite correlated MIN/MAX scalar subquery over a subset of the outer join into a window aggregate

**Hypothesis.** Hot measurements (8 threads, SF10): the q02 outer 5-way join with its full projection and TopN takes about 30ms, and the full q02 takes about 47ms. So about 17-20ms goes to the decorrelated min() subquery: the LEFT_DELIM_JOIN materialises the outer result, the RHS rescans all 8M partsupp rows (with a BF from the DELIM_GET keys, which costs about 9ms like the outer partsupp scan), probes the supplier CTE again, hash-aggregates by p_partkey and joins back. I hand-wrote the window form, `SELECT * FROM (SELECT ..., min(ps_supplycost) OVER (PARTITION BY p_partkey) m FROM <outer join>) WHERE ps_supplycost = m ORDER BY ... LIMIT 100`. It returns the same result in about 36ms hot against 47ms, so the second partsupp scan, the delim machinery and the CTE barrier all go away. This is the classic WinMagic unnesting: when the subquery's FROM tables and predicates are a subset of the outer query's, and the extra outer tables are tied to that subset only through the correlated columns, then agg over the subquery equals agg OVER (PARTITION BY the correlated outer columns) over the outer rows. For MIN and MAX this holds even if extra-table rows duplicate the partition.

**Plan.** In Binder::PlanFilter (src/planner/binder/query_node/plan_select_node.cpp:11), before PlanSubqueries, call a new helper, e.g. TryRewriteSubqueryToWindow(condition, root), in a new file src/planner/subquery/subquery_to_window.cpp or in plan_subquery.cpp. Steps:
(1) Split the condition into AND conjuncts. Find exactly one conjunct `colref = BoundSubqueryExpression` (either side) with subquery_type SCALAR and IsCorrelated(). Every correlated column must have depth 1 (expr.binder->correlated_columns).
(2) Peel the subquery plan (expr.subquery.plan): optional LogicalProjections, then a LogicalAggregate with no groups and exactly one BoundAggregateExpression. That aggregate must be min or max, without DISTINCT, filter or ORDER BY, and its child must be a column ref. Below it: optional projections and LogicalFilter(s) over LOGICAL_CROSS_PRODUCT / LogicalGet leaves only. Bail on anything else: joins with conditions, subqueries in the subquery, limits.
(3) The outer root must likewise be a tree of cross products, gets and filters; collect its gets and its conjuncts (the outer WHERE conjuncts are in `condition`, since the FROM is unfiltered at this point).
(4) Match each subquery LogicalGet to a distinct outer LogicalGet on the same table (GetTable() pointer equal, both with empty table_filters, no dynamic filters or parameters). Build a binding map from subquery bindings to outer bindings via column_ids and the projection map; bail if a referenced column is missing in the outer get. Map correlated BoundColumnRef (depth 1) to the outer binding it names.
(5) Every remapped subquery conjunct must Equals() some outer conjunct. The unmatched outer conjuncts, other than the subquery conjunct, must reference only columns of unmatched (extra) outer gets. Every correlated column must belong to an extra get and must appear in a matched COMPARE_EQUAL conjunct, which rejects NULLs. Nothing may be volatile, and no other conjunct may hold a subquery.
(6) Rewrite: root = LogicalFilter(all conjuncts except the subquery one) over root. Then add LogicalWindow(new table index) with a BoundWindowExpression of type WINDOW_AGGREGATE, using the same aggregate function bound to the remapped argument, partitions = the outer correlated column refs, default frame (whole partition: no ORDER BY, so RANGE UNBOUNDED PRECEDING to UNBOUNDED FOLLOWING covers it). Replace the condition with `colref = BoundColumnRef(window output)`, keeping the original comparison orientation and any cast. Copy how window expressions are built in src/planner/binder/query_node/plan_select_node.cpp / bind_window_expression for LogicalWindow construction.
If any check fails, leave everything untouched (the existing decorrelation path). Test against the original by running q02 with different p_size/type/region values. Add a sqllogic-style check with a case where the extra table has duplicate keys (min is unaffected) and with NULL correlated keys.

**Target files.** src/planner/binder/query_node/plan_select_node.cpp, src/planner/binder/query_node/plan_subquery.cpp, src/include/duckdb/planner/binder.hpp, src/planner/subquery/CMakeLists.txt

**Expected gain.** q02: about -20% (47 to about 36-38ms hot, measured with a hand rewrite). Possibly more, since the CTE materialisation also disappears.

**Generality.** Any query with a correlated MIN/MAX scalar subquery whose FROM/WHERE is a subset of the outer query's join, for example 'rows achieving the per-group min/max' (argmin-style) patterns, TPC-H Q2-like supplier/price queries and latest-record lookups. Queries not matching the strict pattern are unchanged. A possible slowdown is a very large outer join result with a single huge partition, where the window (which materialises and partitions) could cost more than the delim plus hash aggregate. Mitigation: only MIN/MAX, and the outer result has to be built anyway.

**Risk.** Medium-high in correctness, low in performance. The pattern checks must be strict: the same tables, an exact conjunct subset after remapping, extra-table conjuncts only on extra tables, correlated columns NULL-rejected by an equality, MIN/MAX only. Binding remap bugs show up as wrong results, so validate with several parameterisations and with EXPLAIN. The implementation is moderately large (about 250-400 lines).



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
