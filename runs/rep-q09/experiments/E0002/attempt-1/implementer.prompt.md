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

### Bloom filter on first equality key of multi-condition hash joins

**Hypothesis.** Current best q09 plan (JSON profile of q09.m0): lineitem scan (59.99M rows, 2.95s CPU) probes HASH_JOIN with Conditions [l_partkey = p_partkey, l_suppkey = ps_suppkey] whose build side is part⋈partsupp (435,892 rows, ~109K distinct partkeys after contains() filter). The join outputs 3.27M rows (5.4%) but costs 2.84s CPU because all 60M rows are hashed on 2 keys and probed. The lineitem scan only gets min/max dynamic filters (l_partkey>=12 AND <=1999993, l_suppkey 1..100000), which prune nothing. No BF is pushed because JoinFilterPushdownInfo::CanUseBloomFilter (physical_hash_join.cpp:775) requires ht->conditions.size()==1, and JoinHashTable::Finalize (join_hashtable.cpp:775-796) feeds the BF the combined multi-column hash. A BF on l_partkey alone would drop ~94% of lineitem rows inside the scan (SelectivityOptionalFilter), shrinking the 2.84s probe to ~0.3s and skipping decode of the other 5 projected columns for dropped rows.

**Plan.** 1) join_hashtable.cpp JoinHashTable::Finalize: when bloom_filter.IsInitialized() and conditions.size() > 1, for each chunk gather key column 0 from the rows (data_collection->Gather(chunk_state.row_locations, *FlatVector::IncrementalSelectionVector(), count, 0 /*first key column*/, key_vec, *FlatVector::IncrementalSelectionVector(), nullptr) with key_vec typed as conditions[0].right->return_type), compute VectorOperations::Hash(key_vec, bf_hashes, count) and bloom_filter.InsertHashes(bf_hashes, count). In InsertHashes, skip the combined-hash BF insert when conditions.size() > 1 (pass a flag or move the BF insert into Finalize). For single-key joins behaviour is unchanged (combined hash == single-column hash). 2) physical_hash_join.cpp CanUseBloomFilter: replace `ht->conditions.size() == 1` with: the filter's condition is HT condition 0 (pass join_condition[filter_idx] from FinalizeFilters, require == 0) and cmp == COMPARE_EQUAL and ht->conditions[0].comparison == COMPARE_EQUAL. PushBloomFilter already uses conditions[0] for key name/type and NullValuesAreEqual(0). Verify ReorderConditions puts equalities first so condition 0 is an equality, and that the HT layout's column 0 is condition 0's key. 3) Keep the existing guards (build_side_has_filter, probe est > HT count, !has_cast, not perfect HT). Add a sqllogictest: 2-key join with filtered build side, check results incl. NULL keys in either column and a build where key0 matches but key1 doesn't.

**Target files.** src/execution/join_hashtable.cpp, src/include/duckdb/execution/join_hashtable.hpp, src/execution/operator/join/physical_hash_join.cpp, src/include/duckdb/execution/operator/join/join_filter_pushdown.hpp

**Expected gain.** q09: lineitem HJ 2.84s -> ~0.4s CPU, plus some scan savings; total query CPU ~8.7s -> ~6s, so roughly -20..-30% wall.

**Generality.** Any multi-column equi-join (composite FK, e.g. partsupp-style keys, multi-column joins in star schemas) where the build side is filtered and much smaller than the probe. SelectivityOptionalFilter self-disables when the BF is unselective, so the downside is the extra column gather+hash at HT finalize (proportional to build rows, small) and BF probe on the first few vectors.

**Risk.** Low-medium. Correctness depends on hashing exactly the same column/type the probe-side BFTableFilter hashes; a mismatch drops valid rows. Gather of key 0 for each build chunk must use the right row-location vector. NULL semantics follow existing single-key logic.



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
