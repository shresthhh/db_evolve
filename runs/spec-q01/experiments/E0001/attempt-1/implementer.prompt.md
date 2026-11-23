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

### Perfect-hash aggregate: per-group simple_update for few distinct groups per chunk

**Hypothesis.** In q01 PERFECT_HASH_GROUP_BY costs 1.72s CPU over 58.8M rows (~29ns/row for 8 aggregates), second only to the scan. PerfectAggregateHashTable::AddChunk (src/execution/perfect_aggregate_hashtable.cpp:117) computes a per-row state address and calls the scatter update (AggregateExecutor::UnaryScatterLoop) once per aggregate, then VectorOperations::AddInPlace on the address vector after each aggregate. With only a handful of groups, consecutive rows hit the same state address, so every aggregate's loop is a serial read-modify-write chain through memory (store-to-load forwarding latency, no register accumulation, no vectorisation), plus 8 extra passes over the address vector. The simple_update path (UnaryFlatUpdateLoop/UnaryUpdateLoop in src/include/duckdb/common/vector_operations/aggregate_executor.hpp) takes a single __restrict state pointer, letting the compiler keep the accumulator in registers.

**Plan.** In PerfectAggregateHashTable::AddChunk, after computing group indices (before converting to addresses), count rows per group index for this chunk. If the number of distinct groups present in the chunk is small (e.g. <= 8, and every aggregate has no filter and a non-null simple_update callback via aggregate.function.GetStateSimpleUpdateCallback()), do a stable counting-sort of row indices into one SelectionVector per present group (single pass, preserves input order within a group so order-sensitive aggregates such as first/list/string_agg and float sums give identical results). Set group_is_set for those groups. Then for each present group g and each aggregate: slice the aggregate's payload input vectors with the group's selection (Vector::Slice(vec, sel, cnt) into a temp vector, or DataChunk::Slice on a reference copy), and call simple_update(inputs, AggregateInputData(aggregate.GetFunctionData(), *aggregate_allocator), child_count, data + g*tuple_size + aggregate_offset, cnt). Count_star (child_count 0) passes nullptr inputs as UpdateStates does. Keep the bounds check / InvalidInputException for group >= total_groups. If the distinct count exceeds the threshold or any aggregate is filtered / lacks simple_update, fall back to the existing scatter path unchanged. Optionally special-case: if all rows of the chunk belong to one group, skip slicing entirely and call simple_update on the payload directly.

**Target files.** src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp

**Expected gain.** q01: aggregation CPU 1.72s -> maybe 0.8-1.0s, i.e. ~15-20% of total query CPU (~300ms -> ~250-300ms wall).

**Generality.** Any GROUP BY on low-cardinality integer/small-domain keys that the optimizer routes to the perfect hash aggregate (flags, status codes, booleans, small enums, years) with many sum/avg/count/min/max aggregates. Queries with many distinct groups per chunk see only the cost of a per-chunk distinct count (cheap) and take the old path.

**Risk.** Medium-low. Correctness risks: preserving order within groups (stable sort required), NULL handling (simple_update handles validity through the sliced vector's unified format), aggregates whose simple_update differs semantically from update (should not exist). Performance risk: dictionary slicing overhead per group per aggregate for chunks with ~8 groups; threshold limits it.



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
