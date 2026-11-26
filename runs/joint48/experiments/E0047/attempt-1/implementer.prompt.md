You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### q18 clustered agg bundle: batched run-interval registration + template state init

**Hypothesis.** After E0045 the q18 HAVING subquery (60M rows, ~29K chunks, 15M runs) spends ~69ms CPU (summed over threads) in RegisterRunInterval (radix_partitioned_hashtable.cpp:813). It takes a global mutex and does a std::map insert per chunk, which is ~2.4us per chunk, so most of it is lock contention across 8 threads. It also spends 62-72ms in RowOperations::InitializeStates (row_aggregate.cpp:8), one indirect call per state for 15M states. E0046 (template-copy init alone) measured q18 ~-2%, inside the 5% noise. Batching the interval registration (one lock per 64 chunks) removes most of the contention. Combined with template init, that should take ~100ms CPU (~12ms wall of ~178ms) off q18, enough to clear noise.

**Plan.** 1) radix_partitioned_hashtable.cpp: give RadixHTLocalSinkState a small pending-interval buffer (vector<pair<uint64_t,uint64_t>>, cap 64). In SinkClustered (:934), instead of calling RegisterRunInterval per chunk, first check the local buffer for overlap with the new interval, then append it. When the buffer is full, and always in Combine/before finalize (wherever lstate.intervals and the run stores are handed to gstate), flush: take run_intervals_lock once, check and insert every pending interval (same lower_bound/prev logic), and set run_intervals_overlap on any conflict. Keep the exact open-interval endpoints: do NOT merge (a,b),(b,c) into (a,c), because another thread's interval starting at boundary key b would look like a false overlap. Required correctness check: overlap is now detected up to 64 chunks late, after those runs were already streamed. Confirm that the overlap path (run_intervals_overlap -> MergeRunStores ~:989 / run source :1554) already routes streamed run stores through the normal combine when overlap is set. Today an overlap found by RegisterRunInterval already happens after earlier intervals were streamed, so this should hold; if it does not, add the fallback. Every flush must finish before any finalize reads run_intervals_overlap. 2) Re-apply the E0046 template-copy init in row_aggregate.cpp RowOperations::InitializeStates: for layouts where no aggregate has a destructor, and init does not depend on the address, initialize one template state block once (cache it on the layout or the HT), then memcpy it to each row's aggregate offset. Keep the per-aggregate path otherwise. 3) Tests: the clustered-agg tests, plus a test where two threads' chunks overlap late (e.g. a union of two sorted ranges), checked against SET disabled clustered path / a shuffled copy. A/B q18 with .timer (sum of 8 subqueries).

**Target files.** src/execution/radix_partitioned_hashtable.cpp, src/common/row_operations/row_aggregate.cpp

**Expected gain.** q18 -4..-7% (~-0.5% geomean). Other GROUP BYs with many groups get a small gain from template init.

**Generality.** Any GROUP BY over input clustered on the first key (sorted/insert-ordered FK columns), and any hash aggregate creating many groups with destructor-free states (SUM/COUNT/MIN/MAX on numerics). Possible slowdown: input that overlaps late now streams up to 64 more chunks before it falls back.

**Risk.** Medium-low. The delayed overlap detection must be covered by the existing fallback, and the template memcpy must skip aggregates whose init is not a plain constant fill.



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
