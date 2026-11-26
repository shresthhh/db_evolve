You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Parallel perfect-HJ build + dense INNER builds up to 4M range

**Hypothesis.** The perfect HJ build runs serially inside PhysicalHashJoin::Finalize (physical_hash_join.cpp:1202-1207 -> PerfectHashJoinExecutor::BuildPerfectHashTable -> FullScanHashTable: ScanKeyColumn over all rows, then one data_collection.Gather per payload column, all on one thread). The regular HJ finalize is parallel (ScheduleFinalize). Measured A/B, warm, 8 threads, on near-identical data: lineitem JOIN part with p_partkey<=1048000 (range under MAX_BUILD_SIZE, so perfect HJ) took 153-175ms. The same query with p_partkey<=1049000 (just over the limit, so regular HJ + BF) took 102-125ms, 4 alternating pairs. In JSON profiles the perfect variant has LOWER join CPU (0.20s vs 0.39s) but 57ms HIGHER latency (0.180 vs 0.123s). The serial build is pure wall-clock loss. So today the perfect HJ makes every 0.5M-1M-row dense build slower. That is also why CanDoPerfectHashJoin cannot be opened further: INNER joins with range >1M are rejected even when dense (line 120-121, `!PropagatesBuildSide(op.join_type) ||`). q14 builds part (2M dense keys p_partkey 1..2M, payload p_type VARCHAR) with a regular HJ: HASH_JOIN 0.58s operator time / 1.08s CPU vs a 773k-row probe. This is the biggest operator in q14 (171ms).

**Plan.** Step 1, parallel build: in PerfectHashJoinExecutor (perfect_hash_join_executor.cpp) keep the serial ScanKeyColumn + TemplatedFillSelectionVectorBuild (duplicate check, cheap int work). Time it first with a local timer to confirm the gather dominates. Then build a slot->tuple mapping and split the payload Gather (FullScanHashTable lines 190-199) into tasks over contiguous SLOT ranges aligned to 64. Validity words are written non-atomically by Gather, so tasks must never share a validity word. Schedule them from PhysicalHashJoin::Finalize the same way ScheduleFinalize / HashJoinFinalizeEvent (physical_hash_join.cpp ~line 528) schedules HashJoinFinalizeTask: e.g. a PerfectHashJoinFinalizeEvent whose tasks each call executor.GatherRange(begin,end). Keep the serial path when the build has fewer than ~64k rows. The duplicate/fallback decision stays serial and before scheduling, so the fallback to ScheduleFinalize is unchanged. Do the col_mask.Combine(bitmap_build_idx) per range as well (or keep it serial: it is word-wise and cheap). Step 2: in CanDoPerfectHashJoin, drop the `!PropagatesBuildSide(op.join_type) ||` term, so INNER joins also qualify for range <= MAX_DENSE_BUILD_SIZE (4M) when ht.Count()*2 >= range+1. Validate: rerun the p_partkey<=1048000 vs <=1049000 A/B (the perfect variant should now be at least as fast), then q14 and q13 (RIGHT perfect HJ on 1.5M customer) in the bench. Correctness: compare against SET disabled_optimizers / a variant with a hash-forcing extra condition, including NULL payloads and VARCHAR payloads, INNER and RIGHT.

**Target files.** src/execution/operator/join/perfect_hash_join_executor.cpp, src/include/duckdb/execution/operator/join/perfect_hash_join_executor.hpp, src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** q14 -15..-25% (2M dense part build becomes a parallel perfect HJ; join CPU roughly halves per the A/B). q13 a few % if its RIGHT perfect build is latency-bound. Any template with a 0.3-1M-row dense build (perfect today) gains up to ~50ms of latency. Geomean -1.5..-3%.

**Generality.** Every FK join against a dense-key dimension (part, customer, supplier, date dims, surrogate keys) at larger scale factors. It removes a serial phase that grows linearly with build size. Could get slower: dense builds whose probe side is tiny. A 4M-slot perfect table is allocated and gathered where the regular HJ would also build 4M entries, so the memory is similar. Sparse perfect HJ stays excluded by the 50% density gate (a prior 8M sparse attempt regressed).

**Risk.** Medium. Concurrent Gather into shared dictionary vectors must not race on validity words or string data, so use slot-range partitioning. Event scheduling in Finalize must keep the perfect/regular fallback logic intact. If the payload gather is not the dominant serial cost, step 1 gains little; the implementer should time it first.



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
