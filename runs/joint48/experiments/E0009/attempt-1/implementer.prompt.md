You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Large perfect hash aggregate (up to 22 bits) with parallel combine and source

**Hypothesis.** In q13 (644ms, 16% of total) the inner HASH_GROUP_BY on c_custkey (1.5M dense groups, stats range 1..1.5M which is about 21 bits) takes 2.13s CPU, the largest operator in the plan. CanUsePerfectHashAggregate (plan_aggregate.cpp:127) rejects it because the total bits exceed perfect_ht_threshold, so it falls back to the radix HT with hashing, probing and partitioned finalize. A previous run on this codebase measured q13 -18.6% (706->576ms) and, re-implemented on top of the RIGHT perfect-HJ base, q13 -24.5% (646->488ms). In that run the larger threshold alone gave only -3.6%, because PerfectAggregateHashTable Combine and the PhysicalPerfectHashAggregate source were serial over 2M slots, which also made the downstream pipeline single-threaded. Both had to be parallelised.

**Plan.** 1) plan_aggregate.cpp CanUsePerfectHashAggregate: allow total bits up to 22 when (a) the estimated input cardinality >= slots/2 (dense enough), and (b) slots * tuple_size * (threads+1) <= max_memory/8. Otherwise keep the existing perfect_ht_threshold rule. 2) perfect_aggregate_hashtable.cpp Combine: let several threads combine their local tables into the global one at the same time, using striped locks over slot ranges (for example 64 stripes) instead of one global lock. Combine aggregate states using the source (local) arena allocator, then move it into the global table (TakeAllocator) under the global lock. 3) physical_perfecthash_aggregate.cpp source: make GetData parallel. Global source state hands out blocks of slots through an atomic cursor, each thread scans its block, and MaxThreads returns slots/block_size. Check that ScanAll can start at a given offset (or add a range scan). Keep the result order unspecified, as with hash agg.

**Target files.** src/execution/physical_plan/plan_aggregate.cpp, src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp, src/execution/operator/aggregate/physical_perfecthash_aggregate.cpp, src/include/duckdb/execution/operator/aggregate/physical_perfecthash_aggregate.hpp

**Expected gain.** q13 -18..-25% (about -1.5% geomean). Possibly other group-bys on dense integer keys with 2^16..2^22 range (custkey/partkey/suppkey-style keys).

**Generality.** Any GROUP BY on one or more integer columns whose combined stats range is up to 4M slots and dense relative to the input, such as FK-keyed aggregates after joins. Risk of slowdown: a sparse range with a small input, which the density guard prevents. Also many threads each allocating a 4M-slot local table, which the memory guard limits.

**Risk.** Medium. The parallel combine must be race-free (stripes must be disjoint slot ranges, and the allocator move must happen under the lock). The source change must cover every slot exactly once. Test against SET perfect_ht_threshold=0 / disabled perfect agg, and compare count/sum/min/max/string aggregates and NULL groups on TEMP tables with 1-4M dense keys.



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

This session is capped at about $15.00 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
