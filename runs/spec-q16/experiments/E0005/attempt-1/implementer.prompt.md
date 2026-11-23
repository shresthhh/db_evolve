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

### Partition count(DISTINCT) radix table on the group-key hash only

**Hypothesis.** Measured this round on a temp table t holding q16's join output (1.18M rows, 27.8k groups): count(DISTINCT x) GROUP BY G takes 102-145 ms wall, SELECT DISTINCT G,x takes 65 ms, and GROUP BY G count(*) takes 30 ms. So after the distinct table is built, about 40 ms of wall goes to re-aggregating the 1.18M distinct tuples into the main table (E0002/E0004 timers: main-HT sink ~180 ms CPU plus main finalize ~30 ms CPU). The distinct radix table partitions on hash(G,x), so every distinct partition holds tuples of every group. Each of the 8 distinct-finalize tasks (AggregateDistinctGrouping, physical_hash_aggregate.cpp:648) therefore feeds all 28k groups into its local main HT. That HT has capacity 32768 and a resize threshold of 21845, so it abandons repeatedly, and the main finalize then combines about 8x or more duplicate group rows. If the radix bits of the distinct table's stored hash come from hash(G) alone, each distinct partition holds complete groups. Then each task's main local HT only sees ~28k*(partitions handled)/(total partitions) groups: it stays small and cache-resident, never abandons, and the main combine/finalize handles ~1x the groups. Salt (top 16 bits) and slot bits (low bits) keep coming from the full hash(G,x), so probe quality in the distinct HT is unchanged.

**Plan.** 1) GroupedAggregateHashTable (src/execution/aggregate_hashtable.cpp + header): add an optional member `idx_t partition_key_count = 0` (0 = off) with a setter. Add a private helper `HashGroups(DataChunk &groups, Vector &hashes)`. It calls groups.Hash(hashes). When partition_key_count > 0 it also hashes only the first partition_key_count columns into a scratch HASH vector (DataChunk::Hash with a column subset, or VectorOperations::Hash/CombineHash over those columns in the same order DataChunk::Hash uses, so the values equal what the main table computes for G). It then splices: h = (h_full & ~RadixPartitioning::Mask(RadixPartitioning::MAX_RADIX_BITS)) | (h_G & Mask(MAX_RADIX_BITS)), i.e. bits [36,48) come from G. Use the helper at every place this HT hashes raw groups: AddChunk(groups,payload,filter) ~line 528, the dictionary/constant paths in TryAddCompressedGroups (~lines 428 and 480; simplest is to skip TryAddCompressedGroups when the option is on), and FindOrCreateGroups(groups, addresses, new_groups) ~line 830. Combine, Repartition and finalize reuse the stored hash column, so they stay consistent. 2) RadixPartitionedHashTable (src/execution/radix_partitioned_hashtable.cpp): add a field set at construction and pass it to the HT in CreateHT (line 71). 3) DistinctAggregateData constructor (src/execution/operator/aggregate/distinct_aggregate_data.cpp:75-115): when group_expressions is non-null and groups is non-empty, set partition_key_count = groups.size() on the radix table. grouping_set is an ordered set with the group indices (< group_by_size) first, so the first groups.size() HT columns are exactly G in the same order as the main table's grouping set. Optional gate: skip when the aggregate's estimated_cardinality is small (e.g. < 4096 estimated groups), where few groups would skew the distinct partitions. Check q16's estimate with EXPLAIN before choosing the threshold, so q16 is not gated off. 4) Verify: results of q16 plus count(DISTINCT) with GROUPING SETS/ROLLUP, multiple distinct aggregates on different columns, distinct with FILTER, a NULL group key, and spilling (memory_limit 100MB). Bench q16. If the gain is small, check that the main local HT really stops abandoning, e.g. with a temporary counter.

**Target files.** src/execution/aggregate_hashtable.cpp, src/include/duckdb/execution/aggregate_hashtable.hpp, src/execution/radix_partitioned_hashtable.cpp, src/include/duckdb/execution/radix_partitioned_hashtable.hpp, src/execution/operator/aggregate/distinct_aggregate_data.cpp

**Expected gain.** q16: 5-12%. It removes most of the ~210 ms CPU in the main re-sink and finalize (about 15-25 ms wall of ~180).

**Generality.** Any grouped DISTINCT aggregate (count/sum/avg DISTINCT ... GROUP BY) with many groups, such as TPC-H q16 and the 'distinct users per key' pattern. It could get slower when there are very few groups and many distinct values (e.g. GROUP BY a boolean): the distinct partitions become skewed and finalize parallelism drops. The estimated-cardinality gate limits that case. Ungrouped DISTINCT is untouched.

**Risk.** Medium-low. Correctness only needs every insert into the distinct HT to use the same hash function. The risk is missing a hash site, e.g. the dictionary fast path or FindOrCreateGroups overloads, which would produce duplicate distinct tuples and wrong counts. Needs careful audit plus tests with dictionary-encoded group columns. The HLL in FindOrCreateGroupsInternal sees a slightly less random hash, which has negligible effect on adaptivity.



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
