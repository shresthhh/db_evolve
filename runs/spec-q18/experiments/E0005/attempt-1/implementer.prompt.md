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

### Zonemap-prunable join key-set filter through compressed-materialization projections

**Hypothesis.** After the 15M-group subquery agg, q18 rescans lineitem (60M rows: scan 0.16s + probe HASH_JOIN 0.26s CPU) and orders (15M rows: scan 0.20s + SEMI join 0.11s CPU) only to keep ~111 order keys. Both tables are stored clustered on the join key, so a key-set filter could skip most row groups through zonemaps. Two things currently block this. (1) JoinFilterPushdownOptimizer::GetPushdownFilterTargets / PushdownJoinFilterExpression (src/optimizer/join_filter_pushdown_optimizer.cpp:23-56,144-160) stops at the `__internal_compress_integral_uinteger(#0, 1)` projection above each scan, because it accepts only BOUND_COLUMN_REF and integral BOUND_CAST. (2) JoinFilterPushdownInfo::CanUseInFilter (physical_hash_join.cpp:714) emits the zonemap-only IN filter only when ht->Count() <= dynamic_or_filter_threshold (default 50), and q18 builds about 111 keys. Measured with dbe-tool sql, full q18 LIMIT 1, alternating runs in one session with compressed_materialization disabled: threshold 50 gave 725 and 672 ms, threshold 1000 gave 604 and 574 ms (about -15%). EXPLAIN ANALYZE confirms 'optional: l_orderkey IN (...)' reaches the lineitem scan, and the lineitem probe join drops from 0.26s to 0.01s. With compression on, raising the threshold does nothing (590 vs 595), which confirms blocker (1). Disabling compression costs elsewhere, so the real fix must keep compression and push through it.

**Plan.** Step A, push through compress: add `Value storage_offset` (null by default) to JoinFilterPushdownColumn (src/include/duckdb/execution/operator/join/join_filter_pushdown.hpp:25). In PushdownJoinFilterExpression, accept ExpressionClass::BOUND_FUNCTION when function.name starts with "__internal_compress_integral_", children[1] is a BoundConstantExpression, children[0] is integral and <= 64-bit, and no offset is set yet. Store the constant as storage_offset and recurse into children[0]. In JoinFilterPushdownInfo::FinalizeFilters and PushInFilter (physical_hash_join.cpp:720-911), when storage_offset is set, map each build-side compressed value v to the storage domain: cast v and the offset to HUGEINT, add them, then DefaultTryCastAs(storage_type), and skip the filter if that fails. Always skip the bloom filter when an offset is set (the has_cast check already does this; make it explicit). Validate step A with `SET dynamic_or_filter_threshold=1000` in dbe-tool sql: q18 should beat 595 ms. Step B, respect the threshold but still prune: when ht->Count() > threshold but <= a cap (e.g. 64*threshold, so ScanKeyColumn stays cheap), sort the unique non-null keys, keep the (threshold-1) largest gaps as boundaries, and push OptionalFilter(ConjunctionOrFilter of ConjunctionAndFilter(>=lo, <=hi)) with at most `threshold` ranges. ConjunctionOrFilter::CheckStatistics already prunes through zonemaps (conjunction_filter.cpp:10). Keep IsDenseRange/ContainsNull bail-outs. Do not change the setting default (rules.md forbids it).

**Target files.** src/optimizer/join_filter_pushdown_optimizer.cpp, src/include/duckdb/execution/operator/join/join_filter_pushdown.hpp, src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** q18 -5..-12%: about 0.45s CPU on lineitem scan+probe and about 0.3s on orders scan+semi, of which most row groups become prunable.

**Generality.** Any selective hash join whose probe side is a scan clustered or sorted on the key (date and id joins, IN-subqueries over fact tables, star joins with filtered dimensions), now also through the compress projections that compressed materialization inserts on most large joins. Possible slowdowns: building and sorting up to a few thousand keys per join finalize, plus per-row-group checks of up to 50 ranges. Both are tiny, and the filter is optional (zonemap only), so it does no row-level work.

**Risk.** Medium-low. Correctness depends on the offset mapping (overflow is handled through HUGEINT and the try-cast bail-out), and the filter is optional, so a wrong prune is the only failure mode. Range bounds must be inclusive and computed in the storage type. NULL keys: keep the existing ContainsNull bail-out.



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
