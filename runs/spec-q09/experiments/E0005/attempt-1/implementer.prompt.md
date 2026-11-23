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

### Bitpacking select: decode only the selected rows' blocks for filtered scans

**Hypothesis.** In q09 the lineitem scan applies the part BF on l_partkey (60M rows in, 3.27M out, about 5.5%) and then fetches 4 non-filter BitPacking columns: l_orderkey (DELTA_FOR), l_quantity, l_extendedprice, l_discount (all FOR). Bitpacking registers no `select` callback (bitpacking.cpp GetBitpackingFunction sets only scan/scan_partial/fetch_row/skip), so StandardColumnData::Select (standard_column_data.cpp:103) takes the ColumnData::Select fallback. That fallback decodes all 2048 values, applies FOR to all of them, and then Slices, which hands a dictionary vector to every downstream operator. Measured with 5-run batches: lineitem JOIN part (BF) with count(*) only is 21.5 ms/run. Adding sums over l_extendedprice, l_suppkey, l_orderkey, l_quantity and l_discount gives 44.5 ms/run, so the non-filter columns cost about 20 ms of q09's roughly 83 ms/run. (l_suppkey has a min/max dynamic filter, so it is decoded as a filter column either way.) A select that unpacks only the 32-value algorithm blocks that contain a selected row, writes only the selected values into a compact flat vector, and skips the Slice should remove a large part of that cost.

**Plan.** In src/storage/compression/bitpacking.cpp add `template <class T, class T_S = MakeSigned<T>::type, class T_U = ...> void BitpackingSelect(ColumnSegment &segment, ColumnScanState &state, idx_t vector_count, Vector &result, const SelectionVector &sel, idx_t sel_count)`, using the signature of RLESelect (rle.cpp:427) and DictFSSTSelect, and register it in GetBitpackingFunction with `bitpacking.select = BitpackingSelect<T>;`. Implementation: mirror the loop in BitpackingScanPartial (bitpacking.cpp:775), walking the vector_count positions through metadata groups (LoadNextGroup when current_group_offset == BITPACKING_METADATA_GROUP_SIZE) and 32-value algorithm groups, while keeping a cursor into sel. The sel indices are ascending; throw an InternalException if they are not, as RLE does. Per mode: CONSTANT writes current_constant for the selected indices in range. CONSTANT_DELTA writes constant*offset + FOR for the selected indices. FOR: if no selected index falls in this 32-block, only advance current_group_offset (no unpack); otherwise UnPackBlock into scan_state.decompression_buffer and write buffer[off]+FOR for each selected index in the block. DELTA_FOR: always unpack, ApplyFrameOfReference plus DeltaDecode into the decompression buffer (the delta chain needs every value), update current_delta_offset, and copy out the selected values. At the end the scan state must sit exactly vector_count positions further on, the same as after BitpackingScan. Set the result to FLAT_VECTOR with result_data[i] for i < sel_count. Validity is handled separately in StandardColumnData::Select (it already requires validity_has_select), so do not touch it. Test with dbe-tool sql: filtered scans comparing sum/min/max of FOR, DELTA_FOR and constant columns (e.g. sorted keys, low-cardinality ints, dates, decimals) against the same query with the filter wrapped so it is not pushed down. Use selectivities of 0.1%, 5%, 50% and 99%, and also run a query on a column that contains NULLs.

**Target files.** src/storage/compression/bitpacking.cpp

**Expected gain.** q09: about 5-12% (the measured 20 ms of non-filter column decode at 5.5% selectivity; about 16% of FOR blocks are skipped entirely, and the full-vector FOR pass, the 2048-wide writes and the dictionary Slice all go away).

**Generality.** Any scan of a BitPacking integer, date or decimal column (the default for most integer data) that has a selective pushed filter or a dynamic join filter (BF or min/max) on another column. At 1% selectivity about 72% of the blocks are skipped. This is common in star-schema fact scans. Downstream operators also get flat vectors instead of dictionary slices. Possible slowdown: near-100% selectivity adds a little per-index bookkeeping compared with a straight decode. The implementer may fall back to scan+copy when sel_count > about 0.75*vector_count.

**Risk.** Medium-low. It is an isolated new callback, but scan-state advancement must match Scan exactly. An off-by-one in group or offset handling would corrupt later vectors, especially at metadata-group boundaries (offset not aligned to 2048) and in DELTA_FOR. It only runs when StandardColumnData::Select sees a full-vector scan and a validity select exists.



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
