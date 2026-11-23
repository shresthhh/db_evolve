You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q19` (instances are in `.dbe/queries/`). The only timing that
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

### Skip all-optional ConjunctionAnd table filters in the scan filter loop

**Hypothesis.** In q19 the lineitem scan (3.44s cumulative, about 85% of the query) carries a shipmode filter `optional: IN(..) AND optional: IN(..)`. Two optional pushdowns (filter_combiner.cpp:581 IN, and :659 OR-of-equals) on the same column get merged by TableFilterSet::PushFilter into a CONJUNCTION_AND. RowGroup::CheckZonemap (row_group.cpp:626) marks a filter always-true only when its top-level type is OPTIONAL_FILTER. So this AND stays active, and every 2048-row vector runs the column through ColumnData::Filter: a full decode of the shipmode Dictionary column, followed by FilterSelection calls on OptionalFilter children that do nothing. If the filter were skipped, the column would be fetched with Select on the few surviving rows (about 3 per vector in q19). Same-build A/B with `count WHERE l_quantity<2 AND l_shipinstruct=c AND l_shipmode IN(a,b)`, with and without an extra `(l_shipmode=a OR l_shipmode=b)` that produces the AND-of-optionals: scan 3.47s vs 3.03s, then 2.74s vs 2.25s cumulative (-13..-18%), with the same result rows. The upper FILTER operator re-checks the predicate anyway, so skipping it per row is correct.

**Plan.** In src/storage/table/row_group.cpp RowGroup::CheckZonemap: keep the existing prune check (CheckStatistics on the AND still prunes row groups). Add a static helper IsPurelyOptional(const TableFilter&). It returns true for a filter_type==OPTIONAL_FILTER that is NOT a SelectivityOptionalFilter (check with dynamic_cast<const SelectivityOptionalFilter*> == nullptr; that class can actually filter, e.g. the BF and min/max dynamic filters), and for a CONJUNCTION_AND whose children are all IsPurelyOptional (recursive). Leave the existing top-level OPTIONAL_FILTER branch unchanged. Add `else if (filter.filter_type == CONJUNCTION_AND && IsPurelyOptional(filter)) filters.SetFilterAlwaysTrue(i);`. SetFilterAlwaysTrue already clears column_has_filter, so the column is then fetched via Select (scan_state.cpp:101). Include duckdb/planner/filter/selectivity_optional_filter.hpp and conjunction_filter.hpp. Optionally also make TableFilterSet::PushFilter (src/planner/table_filter.cpp) skip pushing an OptionalFilter whose child equals an existing optional child, to dedupe; keep that secondary. Verify with EXPLAIN ANALYZE of q19 (the lineitem scan should drop clearly) and with bench.

**Target files.** src/storage/table/row_group.cpp

**Expected gain.** q19 -8..-15% (lineitem scan is about 85% of time; the microbench shows -13..-18% scan time)

**Generality.** Any scan where two or more optional (zonemap-only) pushdowns land on the same column: IN lists combined with OR-of-equals, IN plus top-N filters, or derived OR filters from JoinDependentFilterRule. Today these needlessly force a full decode of the column per vector. No query should get slower: the skipped filter was a no-op per row. SelectivityOptionalFilter (BF/min-max dynamic filters) is excluded, so selective dynamic filtering is untouched.

**Risk.** Low. One branch in CheckZonemap. The main hazard is accidentally treating a SelectivityOptionalFilter as purely optional, which would disable BF filtering (performance only, still correct because the join re-checks). Correctness is preserved because optional filters are always re-evaluated by the FILTER above the scan.



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
