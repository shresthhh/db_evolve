You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Bundle: fallback block reuse cache + large perfect HA v3

**Hypothesis.** Two mechanisms that were each retired on acceptance alone, not on correctness. (1) The r14 fallback block cache: a bounded 64MB queue of freed 256KB blocks in BlockAllocator when block_allocator_memory=0. It fixed the warm-state slowdown of the big radix agg in-process (agg 550-714 -> 460-475ms, q18 warm 630-720 -> 500-518ms). In the bench, join templates gained (q04 -5..-12%, q07 -9% in 2 of 3 runs, q03 -12%, q05 -6..-9%), but no single template cleared its noise threshold. (2) E0013 large perfect HA (22 bits, striped combine, parallel source, lazy init, DELIM guard, buffer-allocator tables) gave q13 -17..-23% in 10 of 10 runs, clearing q13's 14% threshold. It was retired only because q18 was +8.7% in full-bench runs, and that +8.7% matches the warm-state jemalloc churn that (1) removes: q18 after q09 was ~620ms in both builds, and the slowdown was not reproducible in subsets. Together: q13 clears its threshold, the cache neutralizes the q18 artifact, and the join templates add geomean.

**Plan.** (a) Re-apply the r14 change in src/storage/block_allocator.cpp plus its header. When the pool is unused, keep a bounded 64MB queue of freed block_size allocations in AllocateData/FreeData. Drain it in ThreadFlush, FlushAll and ~BlockAllocator. (b) Re-apply E0013 as recorded in the ledger. plan_aggregate.cpp CanUsePerfectHashAggregate accepts up to 22 bits when perfect_ht_threshold >= 12, with guards: density est_input >= slots/2, memory slots*(state+1)*(threads+1) <= max_memory/8, and no DELIM_SCAN in the input subtree. Set the is_large flag. In physical_perfecthash_aggregate.cpp, large mode only: lazy per-slot InitializeStates, striped-lock Combine, block-parallel source, tables from the buffer allocator. Non-large paths stay byte-identical. Before the bench, check in one dbe-tool sql process: q09; q13; q18 x3, then the same with SET perfect_ht_threshold=11. q18 must not regress.

**Target files.** src/storage/block_allocator.cpp, src/include/duckdb/storage/block_allocator.hpp, src/execution/physical_plan/plan_aggregate.cpp, src/execution/operator/aggregate/physical_perfecthash_aggregate.cpp, src/include/duckdb/execution/operator/aggregate/physical_perfecthash_aggregate.hpp

**Expected gain.** q13 -17..-23%. q04/q05/q07/q03 -5..-10% (noisy). q18 neutral or slightly faster. Geomean about -3..-4%.

**Generality.** The block cache helps any query that churns 256KB buffer blocks (HJ builds, aggs, sorts) while many base-table blocks are resident, which is typical for long-lived processes. Large perfect HA helps GROUP BY on dense integer FK keys up to a 4M range with many rows per group. Risk of slowdown: sparse inputs with overestimated cardinality, measured +60% on a 1.8M-row/2M-slot case. The cache holds up to 64MB more memory.

**Risk.** Medium. Large perfect HA regressed q18 twice before, but that matches the artifact the cache fixes. The cache must be drained on memory pressure, which FlushAll does.



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
