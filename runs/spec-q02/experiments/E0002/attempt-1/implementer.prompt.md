You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q02` (instances are in `.dbe/queries/`). The only timing that
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

### Sparse Select for BitPacking segments (decode only selected rows)

**Hypothesis.** In q02 the partsupp probe scan is the largest single cost: 0.30s CPU summed over threads (about 37ms per thread at 8 threads, out of 71ms total). I measured its parts in isolation, hot: a plain 8M-row ps_partkey scan costs 0.02s; ps_partkey with the BF filter costs 0.08s (the BF hash+probe is about 7ns/row, already tight in bloom_filter.cpp); adding the two payload columns ps_suppkey and ps_supplycost raises it to 0.30s. Only about 1% of rows survive the BF (73k of 8M, about 18 rows per 2048-row vector), yet the payload columns cost about as much as a full 3-column scan (0.14s). The cause is in StandardColumnData::Select (src/storage/table/standard_column_data.cpp:103). It uses a specialised segment select only when the compression function has `select`. Only dict_fsst and constant implement it. BitPacking (src/storage/compression/bitpacking.cpp, GetBitpackingFunction) does not, so ColumnData::Select falls back to Scan (decode all 2048 values) plus Slice. Both payload columns are BitPacking with Constant validity, and Constant validity already has ConstantSelectValidity. So adding a bitpacking select is the only missing piece for the fast path.

**Plan.** In src/storage/compression/bitpacking.cpp add template<class T> BitpackingSelect(ColumnSegment&, ColumnScanState&, idx_t vector_count, Vector &result, const SelectionVector &sel, idx_t sel_count), modelled on FSSTStorage::Select (fsst.cpp:713). It writes result_data[i] = value at row sel.get_index(i) for i < sel_count (flat result). It must leave the BitpackingScanState advanced by exactly vector_count rows, as a scan would. (1) Dense case (sel_count * 4 > vector_count), or the current metadata group is DELTA_FOR: decode the vector with BitpackingScanPartial<T> into a scratch buffer of STANDARD_VECTOR_SIZE T held lazily in the scan state, then gather through sel. This costs the same as today, so it cannot regress. (2) Sparse case: walk the selected indices in ascending order (sel is ascending in scans) and keep a cursor `pos`. For each idx call scan_state.Skip(segment, idx - pos). Skip is O(1) for CONSTANT, CONSTANT_DELTA and FOR, crossing metadata groups by pointer arithmetic. Then read the single value the way BitpackingFetchRow does. Handle the case current_group_offset == BITPACKING_METADATA_GROUP_SIZE by calling LoadNextGroup first, as BitpackingScanPartial does. Cache the last unpacked 32-value algorithm group pointer so that neighbouring rows are not unpacked twice. For a DELTA_FOR group, Skip decodes and keeps current_delta_offset, so it stays correct, just not faster; the value is decoded the same way Skip's loop does. At the end call Skip(vector_count - pos). Register it in GetBitpackingFunction by setting `bitpacking.select = BitpackingSelect<T>;`, the same way dict_fsst.cpp:294 sets `res.select`. Check that the select function pointer signature matches compression_function.hpp. Run the bitpacking tests under test/sql/storage/compression/bitpacking/, plus selective-filter queries on persisted tables.

**Target files.** src/storage/compression/bitpacking.cpp

**Expected gain.** q02: payload-column cost in the partsupp scan drops from about 0.22s to about 0.03s CPU, so the scan goes from 0.30s to about 0.11s. That is roughly 15-25% of q02 wall time, because this scan is the critical path of the probe pipeline.

**Generality.** Any persisted-table scan where a pushed filter (constant comparison, bloom-filter/IN join filter, LIKE) keeps a small fraction of each vector and the projected columns are bitpacked integers, decimals or dates. That is very common: selective joins into fact tables, TPC-H/TPC-DS-style payload columns. Dense selections use the old decode-then-gather path, so the only possible slowdown is the extra branch per vector.

**Risk.** Medium-low. The bitpacking scan state must end up exactly where a full Scan would have left it, including metadata-group crossing and DELTA_FOR's current_delta_offset. A mistake gives wrong values for later vectors, but the bitpacking test suite and the hidden result checks should catch that. Falling back for DELTA_FOR and dense selections keeps the new code to the simple random-access modes.



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
