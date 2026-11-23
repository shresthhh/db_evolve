You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q13` (instances are in `.dbe/queries/`). The only timing that
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

### Parallel combine and parallel source for large perfect hash aggregate (re-land E0001)

**Hypothesis.** E0001 cut q13's inner aggregate operator CPU from 3.14s to 0.53s, but wall time improved only 3.6%. I re-checked this round with SET perfect_ht_threshold=22: the PERFECT_HASH_GROUP_BY takes 0.45s, HASH_JOIN 1.59s and the scan about 2.4s, so about 4.4s of CPU in total, which is about 0.55s if spread over 8 threads. Wall time is still about 0.72-0.86s, the same as the radix-HA baseline (whose CPU of about 6.8s divided by 8 matches its wall time). So about 0.25s of the plan is serial. The code shows where. (1) PhysicalPerfectHashAggregate::Combine (physical_perfecthash_aggregate.cpp:164) takes one global mutex and calls PerfectAggregateHashTable::Combine (perfect_aggregate_hashtable.cpp:163), which walks all 2^bits slots of each local table. With 8 threads and 2M slots that is 16M slot visits, one table at a time. (2) PerfectHashAggregateState (source, line 178) has one shared ht_scan_position and no parallel source support. So the scan of 2M slots, FinalizeStates, and everything downstream (decompress projection, outer HASH_GROUP_BY over 1.5M rows) run on one thread. The radix HA baseline has a parallel source, so switching to the perfect HA made the downstream pipeline serial. That cancelled E0001's CPU win.

**Plan.** (a) Re-land E0001's CanUsePerfectHashAggregate extension in src/execution/physical_plan/plan_aggregate.cpp (around line 127) with the same three guards: total bits at most max(threshold, 22); density, meaning estimated_cardinality >= 2^bits/4; and memory, meaning threads * 2^bits * (aligned state size + 1) <= max_memory/8. Keep the existing threshold path unchanged. (b) Add PerfectAggregateHashTable::CombineRange(other, begin, end, ArenaAllocator &alloc). It is Combine restricted to slots [begin,end), using a RowOperationsState built on the caller-provided arena. Moving other's aggregate_allocator into stored_allocators becomes a separate step done under the global lock. (c) In PerfectHashAggregateGlobalState, add a fixed array of stripe mutexes (for example 64 stripes, each a multiple of STANDARD_VECTOR_SIZE slots) and an atomic start counter. Use the striped path only when total_groups >= 2^16. Small tables keep the existing single-lock path, so behaviour is unchanged for default-threshold queries. In Combine, each thread starts at stripe (atomic++ % S), visits every stripe in rotation, locks it and runs CombineRange into the global table with its own local ArenaAllocator. Afterwards, under the global lock, it pushes that arena and the local table's arena into stored_allocators. (d) Make the source parallel. Override MaxThreads in the global source state (ceil(total_groups / block) for large tables, 1 for small). Hand out blocks of slots (for example 2048*8) through an atomic counter. Add a per-thread LocalSourceState holding the current block range and its own ArenaAllocator for FinalizeStates. Add a PerfectAggregateHashTable::Scan overload that takes an end position. Check whether PhysicalPerfectHashAggregate already declares ParallelSource/GetLocalSourceState and set them as needed. Output order is not guaranteed for hash aggregates, so a parallel source is semantically fine.

**Target files.** src/execution/operator/aggregate/physical_perfecthash_aggregate.cpp, src/include/duckdb/execution/operator/aggregate/physical_perfecthash_aggregate.hpp, src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp, src/execution/physical_plan/plan_aggregate.cpp

**Expected gain.** q13: 10-20%. It removes about 0.15-0.25s of serial combine and source work while keeping E0001's 2.6s CPU saving.

**Generality.** Any GROUP BY on dense integer keys with a large range (surrogate ids, dates, keys compressed to uinteger), for example per-customer and per-order counts or sums. Small perfect HAs (the default threshold of 12 bits or fewer) keep the exact old code path. Possible slowdowns: sparse key ranges that pass the density estimate wrongly. These are bounded by the density and memory guards.

**Risk.** Medium. The arena allocator must never be shared between threads, so each combine and scan thread gets its own arena that is stored afterwards. Aggregates with destructors (Destroy loop) must still see each state exactly once. Stripe bounds must cover every slot. Results must be checked on aggregates beyond count (sum, min/max on strings, list) through hidden validation.



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
