You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Coalesce sparse filtered scan chunks before emitting

**Hypothesis.** After a selective table filter or join BF, the table scan emits one DataChunk per 2048-row storage vector, even when only a few rows pass. Every operator downstream then pays its fixed per-chunk overhead on tiny chunks. Hot evidence: in q08 (127ms, 0.77s CPU), HASH_JOIN l_partkey=p_partkey takes 0.405s CPU (52% of the query) for only 403K probe rows. Those rows arrive as about 29K chunks of about 14 rows each, because the exact BF from part passes 0.67% of lineitem's 60M rows. Isolated micro `SELECT count(*) FROM lineitem, part WHERE p_partkey=l_partkey AND p_type='PROMO BURNISHED TIN'`: HJ 0.112s for 403K sparse probe rows, which is 277ns/row. The same join with join_filter_pushdown disabled and dense input (l_orderkey<1600000, 1.6M probe rows) takes 0.039s, which is 25ns/row. That leaves about 3.5us of fixed cost per chunk (the probe key executor, Probe/ScanStructure init, two ExecuteInternal calls per chunk, CachingOperator, and the sink downstream). If the scan fills output chunks to at least about 1K rows, that per-chunk cost is paid about 70x fewer times. Note: memory.md lists 'compacting sparse scan chunks' as refuted, but there is no ledger record of it. This measurement is new, direct evidence that the cost is per chunk and not per row.

**Plan.** In src/function/table/table_scan.cpp, DuckTableScanState::TableScanFunc (~line 316): after storage.Scan returns a non-empty chunk with output.size() < COALESCE_MIN (e.g. STANDARD_VECTOR_SIZE/4 = 512), and the scan is not is_create_index, keep calling storage.Scan into a per-local-state scratch DataChunk (TableScanLocalState, initialized with the output types). Stop when the accumulated size reaches the target, or when storage.Scan returns 0 rows (the assigned parallel range is exhausted, so the batch/row-group boundary and batch index are preserved). Append each scratch result into output with DataChunk::Append, which flattens dictionary/FSST/constant vectors. Only the few selected rows get copied, so decoding them is cheap. If a scratch chunk would overflow STANDARD_VECTOR_SIZE, keep it as a pending chunk in local state and emit it first on the next call (output.Reference/Move or Append into the empty output). Handle both the CanRemoveFilterColumns path (scan into all_columns, then ReferenceColumns projection_ids; coalesce after projection, or coalesce all_columns before projecting) and the direct path. Only coalesce when the scan has table filters or dynamic filters (input.filters non-empty), so unfiltered scans stay zero-copy. Do not advance NextParallelScan inside the coalesce loop. Verify on q08 that HJ l_partkey time drops in the JSON profile, and check q13 (FSST orders scan with NOT LIKE, about 98% selectivity, so it is never below threshold) for no regression.

**Target files.** src/function/table/table_scan.cpp

**Expected gain.** q08 -20..-35% (HJ 0.405s of 0.77s CPU). Also selective-BF lineitem scans in q17 (0.1% pass), q05 (3%), q07, q09, q19, q02, q14. Geomean maybe -3..-6%.

**Generality.** Any scan with a selective filter (pushed predicate, zone-map-surviving range, or join BF/min-max) feeding joins, projections or aggregates. This is very common in star-schema queries. Could be slower: scans at 10-25% selectivity, where the copy cost approaches the saved overhead (hence the low threshold), and LIMIT queries that read slightly more vectors before stopping.

**Risk.** Medium. It touches the core scan path. Pending-chunk carry-over and the CanRemoveFilterColumns projection must be correct. Row-id columns and batch indexes must stay within one parallel range. Order is preserved because coalescing is sequential within one thread's range.



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
