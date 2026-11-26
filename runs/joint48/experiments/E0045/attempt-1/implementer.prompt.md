You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Leaner streamed-run store for clustered-key radix agg (q18 subquery)

**Hypothesis.** q18 (236ms, 12% of total) is dominated by the IN-subquery `SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 312`. The EXPLAIN ANALYZE of this subquery alone gives HASH_GROUP_BY 1.33s CPU over 60M rows into 15M groups, and FILTER 0.06s on 15M rows. Hot-run micro timings (.timer, r13): sum(l_orderkey),sum(l_quantity) scan only 39ms; `select distinct l_orderkey` 133ms; count(l_quantity) group by 165ms; sum(l_quantity) group by 185-195ms; the HAVING version 191-217ms. So about 95ms of wall time is group handling for 15M streamed runs that have no aggregate at all, i.e. about 50ns CPU per group. The aggregate update is only about 20-30ms. E0036 sends interior runs through SinkInteriorRuns (radix_partitioned_hashtable.cpp:718). For every input chunk it allocates one arena block of states per run, fills a 2048-entry address vector, calls RowOperations::InitializeStates and UpdateStates per aggregate plus AddInPlace, Slices the keys by run heads (a dictionary vector), and Appends (key, row-pointer) to a ColumnDataCollection, which copies. The source side (around :1554-1585) then scans the CDC, gathers the states through the pointers in FinalizeStates, and Outputs 15M rows. These are several passes and copies for each group, which is where the per-group cost goes.

**Plan.** Measure first (about 30 min). Add temporary timers, or use perf if available, around the parts of SinkInteriorRuns (FindRunHeads, state allocation and address fill, InitializeStates, UpdateStates, CDC Append) and around the run-store source path (Scan, FinalizeStates, Output), using the distinct and the sum micro queries above. Then fix the dominant part with one mechanism. Preferred: replace the per-local-state ColumnDataCollection run store with a plain append-only list of fixed-size blocks per thread. Each block holds a column of run keys (memcpy of the head keys, no dictionary slice and no CDC) and the aggregate states for those runs, contiguous and in the same order, so that no row-pointer column is needed and the states are addressed by index. Initialize the states of a whole block in one InitializeStates call. In the source, finalize a block's states in vector-sized slices straight into the output chunk, using a row-pointer vector computed arithmetically rather than stored. Keep the MergeRunStores fallback (used when intervals overlap) working on the new blocks. Do not change when streaming is used. If the measurement shows the cost is downstream (Output plus the decompress projection and FILTER over 15M rows) rather than in the store, report that and stop rather than guess. Abandon if the q18 micro does not improve by at least 8%.

**Target files.** src/execution/radix_partitioned_hashtable.cpp, src/include/duckdb/execution/radix_partitioned_hashtable.hpp

**Expected gain.** q18 -5..-12% (cutting the ~95ms of group handling by a third or more on a ~195ms subquery); geomean about -0.5..-1%

**Generality.** Any GROUP BY whose first key is clustered in storage order with many small groups: order-level rollups of line tables, GROUP BY on a sort or insert key, time-series per-id aggregation. Queries whose keys are not clustered never take this path. Possible slowdown: the fallback merge when intervals overlap (q03-like) must stay as cheap as now.

**Risk.** Medium. State lifetime and destructors for non-trivial aggregate states (lists, strings) must still run once; the fallback merge must see the same states. Test with string_agg/list aggregates on clustered keys, with overlapping intervals (unsorted input), and with HAVING.



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
