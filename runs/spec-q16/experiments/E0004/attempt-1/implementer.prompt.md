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

### Cut non-inlined VARCHAR group-key overhead in the radix aggregate (measure per phase, fix the largest delta)

**Hypothesis.** In the q16 count(DISTINCT) aggregate, a non-inlined VARCHAR group key (p_type, 25 chars, which CompressedMaterialization cannot pack because it is longer than 16 bytes) roughly doubles the aggregate's cost. Planner A/B on a temp table of the q16 join output (1.18M rows), 8 threads, warm: `SELECT hb, h, p_size, count(DISTINCT ps_suppkey) ... GROUP BY ALL` with h = hash(p_type) BIGINT gives HASH_GROUP_BY 0.10 s CPU and 45-48 ms wall. The same query with p_type VARCHAR gives 0.22 s CPU and 82-87 ms wall. The scan is 0.01 s in both, so the difference is inside the aggregate. Weaker evidence: SELECT DISTINCT on the 4 keys is 46-59 ms with p_type vs 35-37 ms with h, and a plain GROUP BY count(*) over 28k groups is 34-46 ms vs 20 ms. In q16 the aggregate is about 90 of the ~155 ms wall (the join-only query is 62 ms warm), so removing most of this ~100 ns/row string penalty is worth ~25-40 ms. Rows carrying a non-inlined string go through several stages: distinct-HT AppendUnified, which computes heap sizes and scatters into the heap; abandon/repartition, which copies the heap and recomputes pointers (TupleDataAllocator::RecomputeHeapPointers); the distinct finalize GroupedAggregateHashTable::Combine, which gathers via FlushMoveState and re-scatters new groups with another heap copy; then a re-hash and re-sink into the main HT, and the main finalize Combine. Earlier sink-side tweaks (E0001-E0003) never isolated the string cost.

**Plan.** Step 1, measure (cheap). Add temporary timers following the E0002 pattern: Printer::RawPrint from gstate destructors. Time these phases: RadixPartitionedHashTable::Sink (FindOrCreateGroups / AppendUnified), MaybeRepartition, RadixHTLocalSourceState::Finalize -> GroupedAggregateHashTable::Combine (src/execution/aggregate_hashtable.cpp:883), the re-sink in HashAggregateDistinctFinalizeTask::AggregateDistinctGrouping (physical_hash_aggregate.cpp:648-754), and the main finalize. Run the temp-table A/B twice: `CREATE TEMP TABLE t AS SELECT p_brand, p_type, p_size, ps_suppkey, hash(p_type) h, hash(p_brand) hb FROM <q16 join>`, then compare GROUP BY hb,h,p_size against hb,p_type,p_size with count(DISTINCT ps_suppkey). Find the phase with the largest VARCHAR-vs-BIGINT delta. Inside it, look at per-chunk heap work in src/common/types/row/ (tuple_data_collection.cpp, tuple_data_allocator.cpp, tuple_data_scatter_gather.cpp): ComputeHeapSizes, Build, RecomputeHeapPointers or FindHeapPointers on scan or pin, and chunk-part splitting when 300-row input chunks each open new heap parts. Step 2: fix that one mechanism. Candidate fixes, depending on the evidence: (a) skip RecomputeHeapPointers or the heap-pointer search when the heap blocks have not moved (in-memory, still pinned); (b) in Combine and Repartition of heap layouts, copy row and heap data in bulk per chunk part instead of per row; (c) avoid creating many small heap chunk parts for small input chunks. Keep the diff to one mechanism.

**Target files.** src/common/types/row/tuple_data_allocator.cpp, src/common/types/row/tuple_data_collection.cpp, src/execution/aggregate_hashtable.cpp, src/execution/radix_partitioned_hashtable.cpp

**Expected gain.** q16 10-25%. The aggregate is ~90 of ~155 ms, and the string penalty measured on the same data is ~40 ms wall.

**Generality.** Any hash aggregate, DISTINCT, or count(DISTINCT) grouped by strings longer than 12 bytes (names, types, comments, URLs). These are very common in analytical workloads. Joins and sorts also benefit if the fix lands in shared TupleData code. Risk of slowdown: little, if the change only removes redundant work. Spilling (external) aggregates must keep the pointer recomputation that unpin/repin needs.

**Risk.** Medium. TupleData heap-pointer invariants are subtle; skipping a recompute when blocks did move corrupts strings. Must test the external/spill path (e.g. SET memory_limit low with a large VARCHAR GROUP BY), plus lists/structs in group keys. Correctness is checked on hidden shapes.



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
