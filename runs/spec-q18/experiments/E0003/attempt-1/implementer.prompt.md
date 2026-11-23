You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q18` (instances are in `.dbe/queries/`). The only timing that
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

### Skip unpartitioned staging for fixed-width group layouts in hash aggregate sink

**Hypothesis.** Most of the q18 subquery aggregate cost is in the sink. I measured `SELECT l_orderkey, sum(l_quantity) FROM lineitem GROUP BY l_orderkey LIMIT 1` at about 410 ms. LIMIT 1 finalizes only a few partitions, and the full aggregate takes about 440 ms, so finalize is roughly 30-50 ms. A plain scan of lineitem is about 57 ms. The aggregate scales almost linearly with threads (4 threads 870 ms, 8 threads 455 ms, 16 threads 350 ms), so it is CPU-bound, not limited by memory bandwidth. Allocator flush settings had no effect. In FindOrCreateGroupsInternal (aggregate_hashtable.cpp:756-757), new groups go to `unpartitioned_data` when radix_bits >= UNPARTITIONED_RADIX_BITS_THRESHOLD (3) and new_entry_count/partitions <= 4. On q18 that is about 512 new groups per chunk over 128 partitions, which is exactly 4, so every group takes the staging path. Every Abandon(), which happens every ~16K groups because sink capacity is 32768, then does FlushAppendState, Unpin and Repartition into partitioned_data. Repartition uses DESTROY_AFTER_DONE, and its append state is new each time, so each abandon pins and unpins 128 partitions and frees and reallocates the staging blocks. So each of the 15M groups is written twice and copied once in the sink. An earlier run, recorded in the user's auto-memory, got about -5% on q16 by removing staging for heap layouts. For fixed-width rows, a single direct scatter into the partitions should be cheaper than scatter, copy and repartition.

**Plan.** 1) Measure first. Add temporary steady_clock timers, removed before finishing, around the Repartition inside GroupedAggregateHashTable::Abandon (aggregate_hashtable.cpp:129-146) and around the AppendUnified call in FindOrCreateGroupsInternal (around :765). Report what share of sink time they take on `SELECT max(s) FROM (SELECT l_orderkey, sum(l_quantity) s FROM lineitem GROUP BY l_orderkey)`. 2) Change: in FindOrCreateGroupsInternal, take the unpartitioned path only when the layout is not all-constant, i.e. add `!layout_ptr->AllConstant()` to the condition at :756. Alternatively, lower the `<= 4` threshold for fixed-width layouts, e.g. to `< 2`; try both and keep the better one. Leave Abandon/AcquirePartitionedData unchanged: they already handle an empty unpartitioned_data. 3) Compare on and off with repeated `dbe-tool sql` runs (at least 5 warm runs each) of the isolated aggregate and of full q18, not only with bench against best.

**Target files.** src/execution/aggregate_hashtable.cpp

**Expected gain.** q18 0-6% (the sink is about 60% of q18 wall time). The step 1 timers tell us whether the staging copy matters at all.

**Generality.** High-cardinality GROUP BYs with fixed-width keys and states that run with many threads (>2) and reach 3+ radix bits: distinct-heavy group-bys, IN-subquery aggregates, and similar. Could get slower: aggregates with very few new groups per chunk spread over many partitions, where scattering into 128 partitions for a handful of rows has more per-partition overhead than the bulk repartition. Heap (VARCHAR) layouts are unchanged.

**Risk.** Low. A one-condition change on a path that already exists (the partitioned path is used whenever new_entry_count/partitions > 4). Correctness is unaffected, because both paths feed the same partitioned_data.



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
