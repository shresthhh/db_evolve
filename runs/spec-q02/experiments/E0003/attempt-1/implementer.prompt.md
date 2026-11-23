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

### Compact sparse filtered scan output into fuller chunks within a morsel

**Hypothesis.** In q02 the partsupp scan with the pushed bloom filter emits 73,008 rows out of 8M, which is about 18 rows per 2048-row vector. TableScanFunc (table_scan.cpp:316) returns every non-empty vector as its own DataChunk, so about 3,900 tiny chunks go through the pipeline. The first hash-join probe (p_partkey) shows 0.02-0.03s cumulative for only 73k probe rows. That is per-chunk overhead (hashing setup, ScanStructure init, operator dispatch), not per-row work. Measured with threads=8 hot: the 1-column BF scan is 0.06s and the HJ probe 0.01-0.02s, while a full unfiltered 3-column scan of partsupp takes only 1.6ms wall. Downstream joins are CachingPhysicalOperators and already coalesce their outputs, so the first operator after a selective scan is the one that pays. E0002 (a faster BitPacking select) showed no official gain, which suggests decode is not the bottleneck. Per-chunk overhead is the next suspect.

**Plan.** In the parallel DuckTableScanState::TableScanFunc (src/function/table/table_scan.cpp, around line 316), when the scan has table filters and storage.Scan returns a chunk with 0 < size < STANDARD_VECTOR_SIZE/8, do not return it straight away. Copy it into a per-local-state buffer DataChunk of the output types (add a `DataChunk compact_buffer` to TableScanLocalState, initialised lazily with output.GetTypes()). Keep calling storage.Scan for the same morsel only (do NOT call NextParallelScan while the buffer is non-empty, so batch-index and insertion-order semantics are kept). Append each result with DataChunk::Append. Stop when the buffer holds >= STANDARD_VECTOR_SIZE/2 rows, when the next chunk would overflow STANDARD_VECTOR_SIZE (in that case emit the buffer and keep the pending chunk for the next call, or simply stop before appending a chunk that does not fit), or when the morsel is exhausted (Scan returns 0). Then output.Move/Reference the buffer. If a chunk of size >= STANDARD_VECTOR_SIZE/8 arrives while the buffer is empty, return it unchanged (fast path, no copy). Handle the CanRemoveFilterColumns path by compacting after ReferenceColumns, and skip compaction for is_create_index. Keep the TASK_EXECUTOR async return logic unchanged: only return HAVE_MORE_OUTPUT/FINISHED after the buffer has been flushed. Verify that row-id/virtual columns come through Append correctly, and that the DataTable scan state lifetimes stay valid: strings are deep-copied by Append into the buffer's own heap.

**Target files.** src/function/table/table_scan.cpp

**Expected gain.** q02: about 0.02-0.03s cumulative CPU on the first probe after the partsupp scan, plus less pipeline dispatch overhead. Estimated 4-8% wall. Also helps the supplier and part scans when they are selective (part: 8,061 of 2M rows).

**Generality.** Any query whose table scan has a selective pushed filter (static predicates, bloom/IN join filters, LIKE) feeding joins, aggregates or projections. That is common in star-schema and TPC-H/DS style workloads. Queries could get slower when filters keep roughly 5-12% of rows (the copy cost of Append, including string deep-copies, without much overhead saved). The 1/8-vector trigger limits this. Scans without filters are unaffected.

**Risk.** Medium-low. Correctness depends on not crossing morsel boundaries (batch index/order preservation) and on properly flushing the buffer at the end of the morsel and the scan. Wrong async-mode handling could drop or duplicate rows. The copy of string columns adds some cost.



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
