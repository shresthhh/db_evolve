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

### Dictionary-level filter evaluation for Dictionary-compressed string segments

**Hypothesis.** The q19 lineitem TABLE_SCAN is still ~90% of the query (3.38s cumulative of 0.478s wall). l_shipinstruct and l_shipmode are stored with plain `Dictionary` compression and `Constant` validity (pragma_storage_info). An isolated `count(*) FROM lineitem WHERE l_shipinstruct='DELIVER IN PERSON'` costs 1.14s cumulative, about a third of the q19 scan. DictionaryCompressionFun::GetFunction (src/storage/compression/dictionary_compression.cpp:170) registers no `filter` callback. So StandardColumnData::Filter (standard_column_data.cpp:76) takes the fallback ColumnData::Filter: it emits a dictionary vector, then ColumnSegment::FilterSelection compares strings row by row through the dictionary sel (17-byte constant, so no inlined fast compare). DictFSST already has the fix (DictFSSTFilter, dict_fsst.cpp:180): evaluate the filter once on the dictionary entries (a handful per segment here), cache a bool per entry, then map each row via the dictionary sel. The Constant validity segment already has a filter (ConstantFilterValidity, numeric_constant.cpp:178), so once Dictionary has a filter the fast path will be taken.

**Plan.** 1. In src/include/duckdb/storage/compression/dictionary/decompression.hpp, add to CompressedStringScanState: `unsafe_unique_array<bool> filter_result;` and `bool null_filter_result_initialized = false;` (mirror the dict_fsst scan state).
2. In src/storage/compression/dictionary_compression.cpp, add `DictionaryCompressionStorage::StringFilter(ColumnSegment&, ColumnScanState&, idx_t vector_count, Vector &result, SelectionVector &sel, idx_t &sel_count, const TableFilter&, TableFilterState&)`, ported from DictFSSTFilter:
   - Only when vector_count == STANDARD_VECTOR_SIZE and the dictionary was initialised.
   - Lazily build filter_result[dictionary_size] by running ColumnSegment::FilterSelection on `Vector(dictionary->data, 1, dictionary_size)` (slot 0 is NULL).
   - Unpack the bitpacked selection into sel_vec exactly as ScanToDictionaryVector does (including the start_offset shift).
   - Loop over the incoming sel (sel_count rows): idx = sel_vec[row]; slot 0 → evaluate the NULL entry lazily as DictFSST does; keep the row if filter_result[idx].
   - Write a new sel only if some rows were dropped. Set `result.Dictionary(dictionary, *sel_vec)` so later columns and the output still see the dictionary vector.
   - Otherwise fall back to StringScan + FilterSelection.
3. Register the filter. The CompressionFunction constructor has trailing optional args, so set `res.filter = ...` after construction (as dict_fsst.cpp:295 does).
4. Correctness guard: cache filter_result only when the filter tree (recurse through CONJUNCTION_AND/OR and OPTIONAL children) has no DYNAMIC_FILTER, BLOOM_FILTER or other filter whose result can change during the scan. For those, re-evaluate on the dictionary every vector (still cheap, since the dictionary is small), or fall back.
5. Check that ConstantFun::FiltersNullValues (numeric_constant.cpp:110) does not throw for any filter type that can now reach it on VARCHAR columns. Its default case throws InternalException; add the missing cases if needed (e.g. DYNAMIC_FILTER → filters_nulls=true conservatively is wrong; use filters_nulls=false, filters_valid_values=false, which keeps everything and is safe because the data filter already ran).
Verify with EXPLAIN ANALYZE count(*) WHERE l_shipinstruct = const (expect well below 1.14s cumulative) and with bench q19.

**Target files.** src/storage/compression/dictionary_compression.cpp, src/include/duckdb/storage/compression/dictionary/decompression.hpp, src/include/duckdb/storage/compression/dictionary_compression.hpp, src/storage/compression/numeric_constant.cpp

**Expected gain.** q19 -15..-25%: the shipinstruct equality is about 1/3 of scan CPU, and the optional shipmode IN on the same storage type also gets cheaper.

**Generality.** Any scan with a pushed-down filter (equality, IN, range, LIKE-as-expression filter) on a low-cardinality VARCHAR column stored with plain Dictionary compression, which is very common in TPC-H/TPC-DS (flags, modes, statuses, categories). Regression case: a dictionary nearly as large as the vector (high-cardinality segment), where per-entry evaluation duplicates work. Bound it by taking the path only when dictionary_size <= vector_count, or let it be since it is amortised over the segment.

**Risk.** Medium. Storage filter path: needs correct NULL slot-0 handling, the bitpacking start_offset shift, no stale cache for dynamic filters, and FiltersNullValues coverage. The DictFSST implementation is a proven template.



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
