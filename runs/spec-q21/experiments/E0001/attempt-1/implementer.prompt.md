You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q21` (instances are in `.dbe/queries/`). The only timing that
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

### Bloom filter for joins with one equality key plus non-equality conditions

**Hypothesis.** In q21, the two subquery joins `lineitem l2/l3 ⋈ DELIM_SCAN ON l_orderkey = l_orderkey AND l_suppkey != l_suppkey` (profile: HASH_JOIN 1.10s producing 1.85M rows, plus the sibling join producing 2.93M rows) probe the whole lineitem table against a build side of about 708K distinct (orderkey, suppkey) pairs. No bloom filter gets pushed into the lineitem scan. The reason is in `JoinFilterPushdownInfo::CanUseBloomFilter` (`src/execution/operator/join/physical_hash_join.cpp`:775), which requires `ht->conditions.size() == 1`, and these joins have two conditions. The join hash table only hashes the equality columns (`equality_predicate_columns`, join_hashtable.cpp:43-60), and `InsertHashes` feeds those same hashes into the bloom filter (join_hashtable.cpp:720). So with exactly one equality condition, the filter is a valid membership test on that key alone, whatever non-equality conditions are also present. A second gate also blocks it: when the build side is a `LOGICAL_DELIM_GET`, `build_side_has_filter` is computed as `IsFiltering(join.children[0])`, i.e. on the probe side (join_filter_pushdown_optimizer.cpp:304-305). The l2 lineitem scan has no filter, so its join never gets a bloom filter. A delim build side is a de-duplicated set of keys from the outer query. Here it covers about 5% of order keys, so a bloom filter would cut about 60M probe rows to about 3M per subquery scan.

**Plan.** 1) In `CanUseBloomFilter` (physical_hash_join.cpp ~775), replace `ht->conditions.size() == 1` with `ht->equality_predicate_columns.size() == 1` (or count the conditions that are COMPARE_EQUAL / NOT_DISTINCT_FROM), keeping `cmp == COMPARE_EQUAL`. Check that the filter column / condition index pushed is the equality one (conditions are reordered so equalities come first, `ReorderConditions` in `GenerateJoinFilters`), and that `PushBloomFilter`'s use of `ht.conditions[0]` and `NullValuesAreEqual(0)` points at that equality condition. 2) In `JoinFilterPushdownOptimizer::GenerateJoinFilters` (join_filter_pushdown_optimizer.cpp:303-308), when the rhs is a `LOGICAL_DELIM_GET`, set `build_side_has_filter = true`, or `IsFiltering(children[0]) || <the delim side is a distinct set>`. The existing `probe_larger_then_build` check (estimated probe cardinality > HT count) still prevents wasted builds. Make sure min/max filters for non-equality conditions behave as before. Run `bench q21` and check in `profile` that the lineitem scans under the delim joins show `BF(l_orderkey)` and far fewer rows.

**Target files.** src/execution/operator/join/physical_hash_join.cpp, src/optimizer/join_filter_pushdown_optimizer.cpp

**Expected gain.** q21: the two lineitem subquery scans and their probes (about 1.1s + ~0.5s operator time) should shrink sharply. I expect 20-40% lower latency.

**Generality.** Helps any hash join with one equality key plus extra inequality/range conditions (common in rewritten correlated EXISTS/NOT EXISTS subqueries, e.g. TPC-H q21/q22-like and other correlated subqueries with residual predicates), and any correlated subquery decorrelated into a join with a DELIM_GET build side over an unfiltered probe table. It could be slightly slower where the bloom filter rejects little, but the existing SelectivityOptionalFilter turns the filter off adaptively when it doesn't help, and the probe>build check still applies.

**Risk.** Low-medium. Correctness depends on the bloom filter hashing exactly the single equality key in the same way as `BFTableFilter::HashInternal` (both use VectorOperations::Hash on one column). With NOT DISTINCT FROM as the only equality, cmp != EQUAL keeps it excluded. Any mismatch in condition index → wrong results, so verify on queries with mixed conditions.



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
