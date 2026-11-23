You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q09` (instances are in `.dbe/queries/`). The only timing that
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

### Offset-aware join filter pushdown through CM integral compress projections (min/max + BF)

**Hypothesis.** In the current best q09 plan (profile after E0002), the most expensive operator is the o_orderkey = l_orderkey HASH_JOIN at 2.22s CPU. orders (15M rows) probes a 3.27M-row build side, but only about 20% of the orders rows can match. The orders TABLE_SCAN has no dynamic filters at all because there is a PROJECTION __internal_compress_integral_uinteger(#0, 1) between the scan and the join. PushdownJoinFilterExpression (src/optimizer/join_filter_pushdown_optimizer.cpp:23) only passes BOUND_COLUMN_REF and integral BOUND_CAST, so GetPushdownFilterTargets bails out at that projection. Both join sides are compressed with the same offset (the build-side projection is also __internal_compress_integral_uinteger(#0/#4, 1)), so the HT keys and BF hashes are compressed uint32 values c = key - min. Hash<uint32>(c) = MurmurHash64(uint64(c)) and Hash<int64>(k) = MurmurHash64(uint64(k)) (common/types/hash.hpp:36-60), so a probe key k matches a BF entry exactly when hash(k - offset) is used. A BF on o_orderkey should cut the orders probe from 15M to about 3M rows. That removes about 12M random probes into a hash table larger than 64MB (~1.2s CPU), and the BF itself costs about 0.15s CPU.

**Plan.** 1) join_filter_pushdown.hpp: add to JoinFilterPushdownColumn an `bool has_offset=false; hugeint_t offset=0;` (or Value).
2) join_filter_pushdown_optimizer.cpp PushdownJoinFilterExpression: add case BOUND_FUNCTION. If the function name starts with "__internal_compress_integral_", it has exactly 2 children, children[1] is a non-NULL BoundConstantExpression, filter.has_offset is false (only one level allowed), and child[0]'s type is integral with size <= 8 bytes, then set filter.offset = constant cast to HUGEINT and has_offset = true, and recurse into children[0]. Otherwise return false.
3) physical_hash_join.cpp JoinFilterPushdownInfo::FinalizeFilters (~line 832): if pushdown_column.has_offset, cast min_val and max_val to HUGEINT, add the offset, then DefaultTryCastAs(storage_type), and `continue` on failure. Skip PushInFilter when has_offset, or add the offset to each value. For the BF (line 898-901), when has_offset, treat has_cast as false if storage_type is an integral type of at most 64 bits (excluding UBIGINT/UHUGEINT) and the condition type is integral. Pass the offset into PushBloomFilter, which needs a new optional int64 offset param.
4) bloom_filter.hpp/.cpp BFTableFilter: add an `int64_t key_offset` plus a `bool has_key_offset`, kept through the constructor, Copy and Serialize (optional property). In HashInternal, when has_key_offset is set, cast the (sliced) keys to a BIGINT state vector, subtract the offset (BinaryExecutor or a simple loop, preserving validity), then call VectorOperations::Hash on that vector. FilterValue: subtract too. CheckStatistics MUST return NO_PRUNING_POSSIBLE when has_key_offset, or else apply the offset in TemplatedCheckStatistics; otherwise zone-map pruning would be wrong.
5) Check that the deferred BF path (physical_hash_join.cpp:588 PushBloomFilter at finalize) carries the offset.
Tests: join a large table against a filtered table on an integer key whose min is non-zero (e.g. keys starting at 1000), with CM active (default). Compare results to the same query with `k+0` keys. Include NULL keys and negative-min keys.

**Target files.** src/optimizer/join_filter_pushdown_optimizer.cpp, src/include/duckdb/execution/operator/join/join_filter_pushdown.hpp, src/execution/operator/join/physical_hash_join.cpp, src/planner/filter/bloom_filter.cpp, src/include/duckdb/planner/filter/bloom_filter.hpp

**Expected gain.** q09: -12..-25%. The orders HJ (2.22s CPU of about 4.4s hot CPU) loses about 80% of its probe rows, and fewer rows flow through the orders compress projection.

**Generality.** This applies to any hash join where CM compresses integer keys on the probe side before the join. That is common for FK joins on integer keys with known statistics ranges, for example TPC-H/DS fact-dimension joins where the probe side is not the bottom of a pipeline under a compress projection. Min/max dynamic filters through compress projections also enable zone-map pruning. A query could get slightly slower when the BF is unselective, but the SelectivityOptionalFilter self-disables in that case.

**Risk.** Medium. The offset arithmetic and casts must be exact. CheckStatistics on a BF with an offset must not prune. Mixing signed and unsigned values: restrict to storage types up to int64/uint32. A wrong offset gives wrong results, which needs tests with a non-zero min and negative values.



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
