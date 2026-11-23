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

### Early HT capacity adaptation when groups slightly exceed initial sink capacity

**Hypothesis.** With >2 threads, RadixHTConfig::SinkCapacity() gives each thread a 32768-slot aggregate HT, so it resizes at ResizeThreshold = 21845 entries. DecideAdaptation(), the only thing that can grow the HT, runs only once a thread has sunk ADAPTIVITY_THRESHOLD = 1,048,576 rows. q16 puts ~1.18M rows into 27,839 groups (above 21845). In the distinct-finalize phase (HashAggregateDistinctFinalizeTask::AggregateDistinctGrouping, which sinks into grouping_data.table_data.Sink), each of the 8 tasks gets ~150k rows covering nearly all groups. No thread reaches 1M rows, so the HT never grows. It fills and is Abandon()ed about 7 times per thread, materialising many copies of each group, and RadixPartitionedHashTable finalize then has to combine several hundred thousand rows instead of ~27k per thread. Measured: the same join with a plain GROUP BY brand,type,size count() takes 178 ms, against 121 ms without the GROUP BY. That is ~60 ms for 1.18M rows into 27k groups, ~400 ns/row of CPU, which is pathological. count(DISTINCT) adds ~45 ms more through the same path.

**Plan.** In src/execution/radix_partitioned_hashtable.cpp, RadixPartitionedHashTable::Sink: just after the `if (ht.Count() + STANDARD_VECTOR_SIZE < ResizeThreshold(local_sink_capacity)) return;` early-out (the HT is full) and before the Abandon() call, add an early check that can only grow the HT. Conditions: !lstate.adapted && gstate.number_of_threads > GROW_STRATEGY_THREAD_THRESHOLD (so HLL is enabled) && !gstate.external && lstate.local_sink_capacity < ADAPTIVITY_THRESHOLD && ht.GetSinkCount() >= 2 * ResizeThreshold(local_sink_capacity), so there are enough samples. Compute deduplicated_count = ht.GetMaterializedCount(), hll_count = MinValue(ht.GetHLLUpperBound(), deduplicated_count) and the same percentages as DecideAdaptation. If deduplicated_pct / hll_pct > 2.0 (CAPACITY_INCREASE_DEDUPLICATION_RATE_THRESHOLD), set new_capacity = MinValue(GetCapacityForCount(hll_count), ADAPTIVITY_THRESHOLD). If new_capacity > local_sink_capacity, set lstate.local_sink_capacity = new_capacity, call ht.Abandon(); ht.Resize(new_capacity); and return. Do not set adapted, so the existing 1M-row DecideAdaptation still runs later, and do NOT take the SkipLookups branch early. Best done as a small helper next to DecideAdaptation, perhaps sharing the math. Memory per thread stays bounded by the existing ADAPTIVITY_THRESHOLD cap. Also check the MaybeRepartition path that follows, which must still run when no resize happens.

**Target files.** src/execution/radix_partitioned_hashtable.cpp

**Expected gain.** q16: 10-20% (the main-HT sink and finalize in count(DISTINCT) finalize, ~27k groups). Any hash GROUP BY with roughly 22k-700k groups and fewer than 1M rows per thread gains similarly.

**Generality.** Any parallel hash aggregation whose group count exceeds the initial 32k-slot capacity but whose per-thread input is below 1M rows. That is common for medium-cardinality GROUP BYs on joins or filtered scans, and in the count(DISTINCT) finalize phase. Possible slowdowns: inputs where the HLL early sample overestimates the dedup benefit (cost: a larger HT, at most the existing cap), and a slightly larger per-thread HT that falls out of L2.

**Risk.** Low. The change can only grow capacity, within existing caps, using the same mechanism DecideAdaptation already uses (Abandon + Resize), so correctness is unaffected. External/out-of-core mode is excluded. The 2-thread grow strategy is untouched.



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
