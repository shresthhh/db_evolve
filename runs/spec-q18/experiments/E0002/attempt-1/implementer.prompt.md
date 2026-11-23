You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q18` (instances are in `.dbe/queries/`). The only timing that
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

### In-place finalize: combine radix partitions without re-materializing first-seen groups

**Hypothesis.** The q18 subquery HASH_GROUP_BY (4.6-5.0s CPU, ~95% of the query) is bound by a fixed cost per group, not per input row. SQL experiments on the current build: orders GROUP BY o_orderkey (15M rows, 15M groups) takes 5.43s CPU, while lineitem GROUP BY l_orderkey (60M rows, 15M groups) takes 5.0s. 1.5M groups takes 0.48s, so ~320ns/group whatever the size, which means it is not about cache size. Removing the aggregate drops it to 3.17s and count(*) gives 4.29s, so the cost grows with row width. That points at row materialization and copying, not at probing (E0001 cut probes 4x and gained only ~1-3% wall). With 8 threads, every surviving group is materialized twice. Once in the sink (thread-local HT abandoned into partitioned TupleData). Then again in RadixHTLocalSourceState::Finalize, which calls ht->Combine(*partition.data): FlushMoveState scans and gathers the groups, FindOrCreateGroups appends a brand-new row (scatter plus InitializeStates) for every group first seen in the partition, then CombineStates. Later Scan gathers it again. For high-cardinality aggregates most groups are first-seen in finalize, so the second append, init and combine is pure copying. An in-place finalize would build only a pointer table over the existing partition rows. A first-seen row is used as the target directly, with no copy. A duplicate row gets its states combined into the target and is dropped. The scan then gathers from the list of live row pointers.

**Plan.** 1) In src/execution/aggregate_hashtable.cpp (and its header), add GroupedAggregateHashTable::CombineInPlace(TupleDataCollection &data, vector<data_ptr_t> &live_rows). Scan `data` with TupleDataPinProperties::KEEP_EVERYTHING_PINNED, gathering the group columns and the hash as FlushMoveState does. Probe the ht_entry_t table using the same salt and linear-probing logic as FindOrCreateGroupsInternal. When a slot is empty, store the source row pointer itself with entry.SetPointer(source_row) and push it to live_rows; do not append. When the salt matches, compare with row_matcher.Match against the pointed-to rows. On a match, call RowOperations::CombineStates(source -> target). Simplest path: factor the probe loop so it returns an 'is new' selection plus target addresses without appending. 2) In src/execution/radix_partitioned_hashtable.cpp, in RadixHTLocalSourceState::Finalize, use CombineInPlace only when !sink.external, !layout.HasDestructor() and sink.scan_pin_properties == DESTROY_AFTER_DONE (no multi-scan). Keep partition.data alive and pinned, and store live_rows in the AggregatePartition. Otherwise use the existing path. 3) In RadixHTLocalSourceState::Scan, when the partition has live_rows, take slices of up to STANDARD_VECTOR_SIZE pointers into a row_locations Vector. Use data_collection.Gather(row_locations, sel, count, column_ids, scan_chunk, ...) for the group columns, then the existing FinalizeStates on those addresses. Reset the collection at the end. The HT pointer table can be freed right after finalize. Size the pointer table with GetCapacityForCount(partition.data->Count()), as is done today.

**Target files.** src/execution/radix_partitioned_hashtable.cpp, src/execution/aggregate_hashtable.cpp, src/include/duckdb/execution/aggregate_hashtable.hpp

**Expected gain.** q18: the subquery aggregate drops one full row materialization (scatter, init, combine and the extra blocks) for ~all 15M groups. Estimate 15-25% of aggregate CPU, so roughly -10..-20% on q18 wall.

**Generality.** Any multi-threaded hash aggregate with many groups, where groups mostly survive the thread-local HT uniquely: high-cardinality GROUP BY, DISTINCT, and the sub-aggregates in TPC-H q18/q10/q13-like shapes and in dedup queries. Low-cardinality aggregates have tiny partitions, so they see no change. Possible slowdowns: the scan gathers through random pointers instead of sequentially, so scan locality is a little worse. Pinning the whole partition while finalizing is the same as today's KEEP pin during combine.

**Risk.** Medium. Correctness rests on (a) never destroying states of rows that are still live (restricted to layouts without destructors), (b) heap pointers for VARCHAR keys staying valid (KEEP_EVERYTHING_PINNED, non-external only), (c) multi-scan and external paths falling back. The bench verifies results on hidden shapes, so the fallback gates must be conservative.



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
