You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q01` (instances are in `.dbe/queries/`). The only timing that
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

### avg on int32/int64/decimal(int64): int64 sum state when stats prove no overflow

**Hypothesis.** PERFECT_HASH_GROUP_BY is 1.41s CPU on q01 (second-largest operator after the 2.06s scan). 3 of its 8 aggregates are avg over DECIMAL(15,2) (int64 physical). These use AvgState<hugeint_t> with AddToHugeint::AddValue (extension/core_functions/include/core_functions/aggregate/sum_helpers.hpp:109), which costs a 128-bit add, an overflow compare and a branch per row, plus a 32-byte state instead of 16 bytes. The 4 sums are already rewritten to sum_no_overflow (int64 state) by SumPropagateStats (sum.cpp:126) when |min|,|max| * max_cardinality fits int64, but avg has no such statistics callback. The same rewrite for avg turns 3 of 8 scatter loops into plain int64 adds and makes the state tuple smaller (better cache use, cheaper replicas from E0003).

**Plan.** In extension/core_functions/aggregate/algebraic/avg.cpp: (1) add `struct IntegerAverageOperationInt64 : BaseSumOperation<AverageSetOperation, RegularAdd>` whose Finalize is bit-identical to IntegerAverageOperationHugeint: `long double divident = GetAverageDivident<long double>(count, bind_data); target = Hugeint::Cast<long double>(hugeint_t(state.value)) / divident;` (go through hugeint_t so the rounding matches exactly on every platform). (2) add `AvgPropagateStats(ClientContext&, BoundAggregateExpression &expr, AggregateStatisticsInput &input)` modelled on SumPropagateStats: require input.node_stats->has_max_cardinality and NumericStats::HasMinMax(child_stats[0]); internal type INT32 or INT64 only; compute max/min * max_cardinality in hugeint; if both are strictly inside int64 bounds, build `AggregateFunction::UnaryAggregate<AvgState<int64_t>, INPUT, double, IntegerAverageOperationInt64>(arg_type, DOUBLE)` and copy name, arguments, return type, bind callback (keep expr.bind_info untouched — the decimal scale stays), and set NOT_ORDER_DEPENDENT; clear its statistics callback; assign to expr.function. Return nullptr. (3) attach the callback (SetStatisticsCallback) to the INT32 and INT64 variants in GetAverageAggregateInternal, which also covers BindDecimalAvg for decimals with int32/int64 storage. Leave INT16 (already int64 state), INT128, interval, time types untouched. Check that a plan serialised after the rewrite (if any) still deserialises: keeping name 'avg' + bind re-run yields the hugeint version, which gives the same results.

**Target files.** extension/core_functions/aggregate/algebraic/avg.cpp

**Expected gain.** q01: 3-7% (3 of 8 aggregates in the 1.41s perfect-HT operator get cheaper; state tuple shrinks by ~48 bytes).

**Generality.** Any avg over INTEGER/BIGINT/DECIMAL(<=18) columns with min/max stats (most scans of base tables), in perfect HT, hash aggregate and ungrouped aggregate. Nothing should get slower; when stats are missing or too wide, the hugeint path is kept.

**Risk.** Low-medium. Correctness depends on the bound check (copy the sum one exactly) and on the finalize being bit-identical (use the hugeint cast). Make sure the swapped function keeps the bind data and the result type DOUBLE.



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
