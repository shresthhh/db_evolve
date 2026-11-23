You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Cardinality-aware perfect hash aggregation above the bit threshold

**Hypothesis.** q13 (the second-slowest template, about 97ms) spends 0.20s CPU in HASH_GROUP_BY on a single integer key (c_custkey, stats [1,150000], 18 bits) over 1.53M rows into 150k groups. The radix hash table gets little benefit from thread-local pre-aggregation here, because each thread sees most of the groups. CanUsePerfectHashAggregate (src/execution/physical_plan/plan_aggregate.cpp:127) refuses perfect hashing because 18 bits is more than perfect_ht_threshold (12). I measured this directly with `SET perfect_ht_threshold=20`: the plan becomes PERFECT_HASH_GROUP_BY at 0.04s CPU, and the hot wall time of the q13 inner query falls from about 107ms to about 73ms (-30%). Counter-evidence that makes a guard necessary: the q18-style `GROUP BY l_orderkey HAVING sum(l_quantity)>300` over lineitem (23 bits, 1.5M groups, 6M rows) goes from 76ms to 800-1040ms with threshold 24. Each thread allocates and initialises a 2^bits table, and the global Combine and the scan are O(2^bits) and serial. So perfect hashing pays off only when the dense table is small compared with the input.

**Plan.** In plan_aggregate.cpp only, with no header changes and the setting's default unchanged: keep the existing check (perfect_hash_bits <= perfect_ht_threshold, which accepts as today). When that check fails, accept anyway if all of the following hold: (1) perfect_hash_bits <= a file-local constexpr cap of 20 bits (1M slots); (2) the aggregate child's estimated_cardinality is known and (1 << perfect_hash_bits) * number_of_threads <= 2 * estimated_cardinality (the per-thread tables are no larger than about twice the input, so allocation, initialisation and combine stay proportional to the input); (3) every other existing condition holds (no grouping sets, no DISTINCT, combine callback present). CanUsePerfectHashAggregate needs the estimate passed in from CreatePlan(LogicalAggregate&) via op.children[0]->estimated_cardinality, and the thread count from TaskScheduler::GetScheduler(context).NumberOfThreads(). If the user set perfect_ht_threshold above the default, the existing check already covers it. Steps: build in the background; EXPLAIN q13.m0 and confirm PERFECT_HASH_GROUP_BY; EXPLAIN q18.m0 and confirm its large GROUP BY stays HASH_GROUP_BY; then run the full bench. If q13 improves but the estimate is too far off in other cases, tighten the factor of 2 to 1.

**Target files.** src/execution/physical_plan/plan_aggregate.cpp

**Expected gain.** q13 about 25-30% (about 97ms → about 70ms), roughly a 2% geomean gain from one template. Any template with GROUP BY on a 13-20 bit dense integer key over many more rows (q18-style per-key aggregates with smaller key ranges, per-customer or per-supplier aggregates) also benefits.

**Generality.** GROUP BY on one or more integer keys with min/max stats whose dense range (2^13 to 2^20) is small compared with the input row count: per-entity aggregates over fact tables after joins to dimension keys. Queries whose estimates are badly wrong (estimate high, actual input small) could get slower from allocating 1M-slot tables per thread. The cap of 20 bits bounds that cost to a few MB per thread.

**Risk.** Low-medium. The diff is one file and planner-only, and it reuses an existing, tested operator, so the risk to correctness is low. The performance risk comes from overestimated cardinality; measured, a 23-bit case was 10x slower, which is why the hard cap and the guard on the ratio to input size exist. The reviewer may ask whether this circumvents the setting. The argument is that the setting is still honoured as the unconditional threshold, and the new rule only adds a cost-based acceptance.



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
6. Timing. Interleaved runs against the current best. The bar was fixed in advance: at least
   2.7% faster on the visible geomean, no visible template slower by more than
   10%, and no slowdown on the hidden templates.

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

This session is capped at about $12.00 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
