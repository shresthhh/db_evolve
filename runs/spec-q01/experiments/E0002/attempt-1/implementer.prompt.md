You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q01` (instances are in `.dbe/queries/`). The only timing that
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

### Bitpacking select: produce flat compacted vectors for filtered scans

**Hypothesis.** In q01 the l_shipdate filter keeps about 98% of rows, but nearly every 2048-row vector loses a few. In RowGroup::Scan (src/storage/table/row_group.cpp:809-819), every non-filter column then goes through StandardColumnData::Select. Bitpacking (all 4 decimal columns: l_quantity, l_extendedprice, l_discount, l_tax) has no `select` callback; only constant, RLE and dict_fsst have one. So it falls back to ColumnData::Select, which scans the full vector and calls result.Slice(sel), so every payload column reaches the projections and the aggregate as a DICTIONARY vector. Downstream, the decimal multiplies and the aggregate scatter then take the generic sel-indirected paths instead of the flat ones. Measured with dbe-tool sql: Q1 with the filter is about 680ms. Without the filter, still scanning l_shipdate through an added max(l_shipdate), it is about 555ms, even though that version processes 2% more rows and runs an extra aggregate. Without the filter and without max it is about 480ms. So the filtered path costs at least about 18%, part of it from dictionary-sliced vectors.

**Plan.** In src/storage/compression/bitpacking.cpp add `template <class T> void BitpackingSelect(ColumnSegment &segment, ColumnScanState &state, idx_t vector_count, Vector &result, const SelectionVector &sel, idx_t sel_count)`, matching compression_select_t in compression_function.hpp:182. It decompresses vector_count values with the existing BitpackingScanPartial<T> logic into a per-scan-state scratch buffer of STANDARD_VECTOR_SIZE T values. Add that buffer to BitpackingScanState<T> and allocate it lazily. It then gathers result_data[i] = scratch[sel.get_index(i)] for i < sel_count and leaves result as FLAT_VECTOR. Use a scratch buffer, not in-place compaction, so correctness never depends on the sel being sorted. Simplest route: call BitpackingScanPartial into a temporary Vector that wraps the scratch buffer (FlatVector::SetData), or refactor the partial scan to take a T* target. In GetBitpackingFunction set `bitpacking.select = BitpackingSelect<T>;`, keeping the ctor args unchanged, as done for get_segment_info. StandardColumnData::Select (standard_column_data.cpp:103) already routes through SelectVector when compression->select, the validity select and SCAN_ENTIRE_VECTOR are all present. Check that the validity segments of these columns (constant or uncompressed validity) have select callbacks: ConstantSelectValidity and ValiditySelect both exist. Also check that ColumnData::SelectVector's offset bookkeeping (offset_in_column += target_count) matches the bitpacking scan-state advance, which happens inside the partial scan by vector_count. Run the test/sql/storage compression tests for bitpacking.

**Target files.** src/storage/compression/bitpacking.cpp

**Expected gain.** q01 5-12%: projections and the perfect-hash aggregate get flat inputs. The scan pays one gather of about 2000 values per column per vector instead of creating a dictionary slice.

**Generality.** Any filtered table scan over bitpacked integer, decimal or date columns (the default compression for most numeric data) where non-filter columns are projected, which is very common in TPC-H/DS-like workloads. Very selective filters pay a negligible gather of sel_count values. The full vector is still decompressed, as today.

**Risk.** Low-medium. This is a storage-layer change, so correctness is the main risk: DELTA_FOR state continuity (current_delta_offset must advance over all vector_count rows, not sel_count), CONSTANT mode, hugeint/uhugeint T, and segment boundaries. The SCAN_ENTIRE_VECTOR precondition guarantees the vector lies inside one segment.



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
