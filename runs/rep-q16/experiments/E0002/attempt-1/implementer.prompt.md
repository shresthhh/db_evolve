You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q16` (instances are in `.dbe/queries/`). The only timing that
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

### Push constant IN-list as scan ExpressionFilter instead of MARK join

**Hypothesis.** In q16 the part scan has `p_size IN (8 constants)`. FilterCombiner::TryPushdownInFilter (filter_combiner.cpp:515-586) pushes a non-dense integral IN list only as an OptionalFilter(InFilter), which is zonemap-only, and returns PUSHED_DOWN_PARTIALLY. The full IN expression stays above the scan. InClauseRewriter (in_clause_rewriter.cpp:60, >=6 constants) then turns it into a MARK join against a COLUMN_DATA_SCAN plus FILTER. The profile shows the result: the part scan emits 1,856,009 rows (0.09s), the MARK join takes 0.03s, and FILTER IN(...) takes 0.02s to get down to 296,389 rows. That is all on the hash-join build pipeline, which has to finish before the 8M-row partsupp probe can start. PushdownGet (pushdown_get.cpp:105-128) only tries TryPushdownGenericExpression for NO_PUSHDOWN results, and it explicitly skips COMPARE_IN when CanThrow, so the partially pushed IN never becomes a real scan filter. Evaluating the IN as a scan ExpressionFilter applies the filter inside the scan's selection chain. That removes the 1.86M-row MARK join, the FILTER and the projection traffic, and gives the scan a real filter for cardinality estimation.

**Plan.** In src/optimizer/pushdown/pushdown_get.cpp PushdownGet, in the loop at lines 105-128: also handle filters whose result is PUSHED_DOWN_PARTIALLY when the expression is COMPARE_IN, children[0] is a BOUND_COLUMN_REF, every other child is a non-NULL BoundConstantExpression (the same conditions TryPushdownInFilter checks), !expr.IsVolatile() and !expr.CanThrow(). For those, call combiner.TryPushdownGenericExpression(get, expr). If it returns PUSHED_DOWN_FULLY, erase the filter from `filters` and `pushdown_results`, as is already done for NO_PUSHDOWN. The existing OptionalFilter(InFilter) stays for zonemap pruning, and PushFilter ANDs the two on the same column. Keep the generic pushdown gated on get.function.pushdown_expression; TryPushdownGenericExpression already checks it. Verify with EXPLAIN that q16's part scan shows the IN filter, has no MARK join or FILTER above it, and emits about 296k rows. Correctness checks: IN with NULL constant (not pushed), NOT IN (unchanged), IN on VARCHAR, IN with 6, 8 and 100 values, and a parquet scan.

**Target files.** src/optimizer/pushdown/pushdown_get.cpp

**Expected gain.** q16 -4..-8%. It removes about 0.05s CPU of MARK join plus FILTER, shrinks the part-scan output 6x on the HJ build pipeline, and makes the build-side estimate more accurate.

**Generality.** Any query with `col IN (>=6 non-dense constants)` directly on a base-table column (TPC-H q16/q19/q22-style IN lists, dashboard filters). The scan evaluates the IN early and skips the MARK join. A very long IN list (thousands of values) is evaluated by ExpressionExecutor as N equality passes, which can be slower than a hash MARK join. Cap it, for example at <=64 constants.

**Risk.** Low-medium. The optimizer change is small. Changed cardinality estimates can shift join orders on hidden queries. The scan ExpressionFilter path is already used for other generic expressions, so execution correctness risk is low.



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
