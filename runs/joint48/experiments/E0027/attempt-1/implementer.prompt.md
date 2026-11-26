You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Bundle: per-value BitPacking select for sparse filtered scans + exact BF up to 2^27 bits at 1024 bits/key

**Hypothesis.** (1) In filtered table scans, the non-filter columns are fully decoded even when few rows pass. BitPacking has no `select` callback, so StandardColumnData::Select (standard_column_data.cpp:103) falls back to ColumnData::Select: Scan the whole vector, then result.Slice. Measured hot on lineitem, where every column involved is BitPacking (pragma_storage_info): `max()` over 5 extra columns WHERE l_partkey<100000 (5% pass) takes 88-95ms, and WHERE l_partkey<10000 (0.5% pass) takes 94-95ms. The same filter with count(*) takes 26-28ms. So the ~65ms spent fetching the extra columns does not depend on selectivity at all. A prior-run attempt (auto-memory bitpacking-select-no-gain) decoded only the selected 32-value blocks. At 5% selectivity about 80% of blocks still hold a selected row (1-0.95^32), so it saved almost nothing and got 0%. That was a bad implementation of a good idea. Reading each selected value straight from the bitstream makes the cost scale with sel_count. q09's lineitem scan (60M rows -> 3.27M, 5 extra columns l_suppkey/l_orderkey/l_extendedprice/l_discount/l_quantity) and q05's lineitem scan (60M -> 2.03M, 3 extra columns) are exactly this case. (2) Re-land the E0025 tier, retired twice as a near-miss: q05 -9/-18/-20% and -13.5/-17.9/-17.4% against a -20.3% bar, with no regressions. Adding (1) on q05's own lineitem scan should push q05 past the bar.

**Plan.** Part 1, src/storage/compression/bitpacking.cpp: add `template <class T> void BitpackingSelect(ColumnSegment &segment, ColumnScanState &state, idx_t vector_count, Vector &result, const SelectionVector &sel, idx_t sel_count)` and register it in GetBitpackingFunction (line ~964) through the CompressionFunction constructor's select slot. Count the nullptr args against rle.cpp:592 / numeric_constant.cpp:221, which pass the select function in that position. Select contract: the result is FLAT and holds the sel_count selected values compacted (result_data[i] = value at sel.get_index(i)), and the scan state advances by vector_count. sel is ascending, as RLESelect assumes. Implementation: use BitpackingScanState (line 608) and walk metadata groups exactly as BitpackingScanPartial (line 775) does. When current_group_offset reaches BITPACKING_METADATA_GROUP_SIZE, call LoadNextGroup. Handle each mode within one metadata group as follows. CONSTANT: write the constant. CONSTANT_DELTA: frame_of_reference + delta*offset, copied from ScanPartial. FOR: per-value extraction, for T of 4 or 8 bytes only. The fastpforlib layout (third_party/fastpforlib/bitpacking.cpp Unroller, 32-bit words, LSB-first) makes each 32-value algorithm group a little-endian bitstream: value j sits at bit j*width from the block start, block start = current_group_ptr + (offset - offset%32)*width/8. Read ceil((bitoff%8 + width)/8) bytes with memcpy so nothing is read past the end, shift, mask, then add current_frame_of_reference with the same unsigned wrapping as the scan path. If width > 56 or T is 1/2/16 bytes, use the existing block unpack instead. DELTA_FOR (needs a prefix sum), or sel_count > vector_count/4: decode with the existing ScanPartial logic into a thread-local scratch buffer, then gather. Finally advance the state by the rows consumed, using the same bookkeeping as Skip/ScanPartial. Verify validity: for NOT NULL columns the validity is Constant, which already has select (numeric_constant.cpp ConstantSelect); ValiditySelect covers the uncompressed case. Correctness: in a debug or temporary check, compare against a full scan. Test via `dbe-tool sql` with TEMP tables of INT/BIGINT/DECIMAL columns containing NULLs, sorted data (DELTA_FOR), constant runs, widths 1..63, and selective filters at 0.1%, 5%, 30% and 90%. Compare with `SET disabled_optimizers` / filters written as `col+0` so the filter is not pushed. Part 2, src/execution/operator/join/physical_hash_join.cpp TrySetExactBloomFilter: add the exact-bitmap tier range < min(2^27, count*1024). Cap the multiplication at 2^27 for EVERY build size, not only count <= 2^17 (E0026 lesson). Keep the 128 bits/key rule, the 2^22 floor and the 2^32 guard. Measure with the warm JSON profile: lineitem scan CPU in q05 and q09 before/after.

**Target files.** src/storage/compression/bitpacking.cpp, src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** Micro: 5-col selective lineitem fetch 95ms -> ~40ms. q09 -5..-8% (5 extra cols at 5.4% pass), q05 -20..-25% (E0025 -17% plus select), q17/q19/q14 a few % (selective lineitem scans via BF or date filters). Geomean about -3..-4%.

**Generality.** Every filtered scan over BitPacking (the default integer/decimal compression) where the filters or join BFs pass under ~25% of rows: TPC-H q06/q12/q14/q15/q17/q19/q20-style scans, star-schema fact scans with BF. Dense filters (>25% pass) keep the current decode path through the threshold, so they should not slow down. DELTA_FOR columns (sorted keys) get no benefit. Part 2 only changes the BF representation for builds with range < 2^27.

**Risk.** Medium. Bit-level extraction must exactly match fastunpack layout and FOR wrap arithmetic; mitigated by restricting to 4/8-byte T with width<=56 and falling back otherwise, plus a randomized sql comparison. The scan state must advance correctly across metadata-group boundaries (mirror ScanPartial). Part 2 has passed hidden validation twice.



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
   at least one visible template at least 5% faster (more for templates whose timings are noisy); no template, visible or hidden, slower by more than 5% (again more for noisy ones); and the visible geomean not slower. A change that makes one kind of query clearly faster and nothing slower is accepted.

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
