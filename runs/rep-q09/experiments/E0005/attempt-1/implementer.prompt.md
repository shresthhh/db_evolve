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

### Exact-bitmap join filter through CM integral compress projections (offset-shifted, no hashed BF)

**Hypothesis.** Hot JSON profile of q09.m0 (505ms wall, ~3.4s CPU): HASH_JOIN o_orderkey=l_orderkey costs 1.39s CPU, the biggest operator (lineitem scan 0.77, lineitem HJ 0.51, agg 0.20). Its build side is 3.27M rows, so the pointer table is ~8M entries / 64MB. The probe side is all 15M orders rows, because the orders scan gets NO dynamic filter: scan -> PROJECTION(__internal_compress_integral_uinteger(o_orderkey,1)) -> HJ, and PushdownJoinFilterExpression (join_filter_pushdown_optimizer.cpp:23) only passes colrefs and integral casts. About 80% of those probes miss, and each miss is a random cache miss into the 64MB table. E0003 already pushed min/max plus a HASHED BF through the compress projection. The orders rows fell 15M->2.96M, but bench was +4.7% (local -8.2%), because hashing 15M keys and doing random lookups into a ~5MB hashed BF cost about what it saved. What is different now: E0004 added exact-bitmap mode. Here the build keys span about 60M values with 3.27M keys, about 18 bits/key, under the 128 cap and under 2^31. So the orders scan filter becomes: subtract a constant, then do one bit test. There is no hashing, and because the probe-side keys arrive clustered or sorted (PK order), the walk through the 7.5MB bitmap is nearly sequential. It is also exact, so the HJ receives exactly the 3.27M matching rows.

**Plan.** 1) Optimizer: in PushdownJoinFilterExpression (src/optimizer/join_filter_pushdown_optimizer.cpp:23), accept a BOUND_FUNCTION whose name starts with __internal_compress_integral_ (see src/function/scalar/compressed_materialization/). Conditions: child 1 is a non-NULL constant castable to BIGINT, and child 0 is integral, at most 64 bits, and not UBIGINT. Recurse into child 0, then record `Value offset` on JoinFilterPushdownColumn (src/include/duckdb/execution/operator/join/join_filter_pushdown.hpp), and copy it wherever columns are rewritten (UNION children). TopN and RowGroupPruner also call GetPushdownFilterTargets: they must bail out when a target has an offset. 2) In JoinFilterPushdownInfo::FinalizeFilters (physical_hash_join.cpp:870), when an offset is present: cast min/max to HUGEINT, add the offset, then cast to storage_type (skip the column if a cast fails); skip the IN filter. Compute has_cast against the decompressed storage type, so it does not by itself block the BF. 3) BF only in exact mode when there is an offset. Call TrySetExactBloomFilterRange (:845) with the build-side compressed min/max, unchanged. Its build_type==probe_type check must be relaxed for the offset case, because probe storage is BIGINT and the build is UINTEGER. If the HT BloomFilter is not exact after that call, do NOT push a hashed BF for an offset column (min/max only). 4) BFTableFilter (src/planner/filter/bloom_filter.cpp plus its header): add an int64 key_offset/has_key_offset and serialize it as optional fields. In exact-mode Filter/FilterValue/CheckStatistics, test bit ((v - key_offset) - min) on the probe vector's own physical type. The existing out-of-range rejection must happen after the shift. If has_key_offset is set and the filter is not exact, the probe must never run (assert). 5) PushBloomFilter (:788) passes the offset of the pushdown column. Test: compare joins on real tables against `+0` versions (no pushdown), for example a count/sum of orders⋈lineitem with a lineitem-side filter. Confirm with EXPLAIN ANALYZE that the orders scan shows `IN BF` and that its cardinality drops.

**Target files.** src/optimizer/join_filter_pushdown_optimizer.cpp, src/include/duckdb/execution/operator/join/join_filter_pushdown.hpp, src/execution/operator/join/physical_hash_join.cpp, src/planner/filter/bloom_filter.cpp, src/include/duckdb/planner/filter/bloom_filter.hpp, src/optimizer/topn_optimizer.cpp, src/optimizer/row_group_pruner.cpp

**Expected gain.** q09: orders HJ 1.39s CPU -> ~0.5-0.7s, orders scan +~0.05s, so about -12..-20% wall. If bench shows <5%, the orders HJ is build-dominated (3.27M random inserts), and the next step would target the build rather than the probe.

**Generality.** Any hash join whose probe-side integer key is CM-compressed before the join (common: CM compresses integer keys with known stats on both sides) and whose build keys are dense enough for the exact bitmap. Typical case: PK/FK joins where the fact-derived side is the build and the dimension or PK table is the probe. A query could get slower if the bitmap filter passes almost everything; SelectivityOptionalFilter pauses it then. Hashed BF behaviour is unchanged.

**Risk.** Medium. The offset arithmetic must match the CM projection exactly: probe value v maps to (v - offset) and must equal the build's compressed key. Using the wrong offset or the wrong sign gives wrong results, so test with keys whose min is non-zero. TopN and RowGroupPruner must reject offset targets. Use only the probe-side offset from the compress expression on that side.



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
