You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Distinct HT partitioned on group hash

**Hypothesis.** q16 does count(DISTINCT ps_suppkey) GROUP BY brand,type,size, with about 64K estimated groups. The distinct radix HT partitions on hash(G,x), so every distinct partition holds pieces of every group. Distinct finalize then re-sinks each partition into the main HT, and each task touches nearly all groups. That is a large re-aggregation plus a combine. A prior run on this codebase spliced hash(G) into the radix bits [36,48) of the distinct HT hash and measured q16 -12..-13% twice, and -11% on a later re-implementation.

**Plan.** In radix_partitioned_hashtable.cpp/.hpp add a member (e.g. partition_prefix_count = number of leading group columns) on RadixPartitionedHashTable. In Sink, when it is set, hash the full key, compute hash(first prefix cols), and replace bits [36,48) (the RadixPartitioning MAX_RADIX_BITS mask region) with those bits of the group hash. Call a pre-hashed AddChunk overload and keep the sink_count update inside it, so the adaptivity logic still fires. In physical_hash_aggregate.cpp, when distinct radix tables are built for a grouped aggregate with estimated_cardinality >= 4096, set the prefix count to the number of main group columns, and skip TryAddCompressedGroups in that mode. Distinct finalize is unchanged: each partition now holds whole groups.

**Target files.** src/execution/radix_partitioned_hashtable.cpp, src/include/duckdb/execution/radix_partitioned_hashtable.hpp, src/execution/operator/aggregate/physical_hash_aggregate.cpp

**Expected gain.** q16 -10..-13%. Other count(DISTINCT) GROUP BY templates gain a few %.

**Generality.** Any grouped aggregate with DISTINCT aggregates over many groups. Ungrouped DISTINCT is unaffected (gated). A skewed group could unbalance partitions, and low-group-count queries are gated off by the estimate.

**Risk.** Medium-low. The hash only affects partitioning, so correctness holds as long as the same hash is used consistently for equality probing in the distinct HT: the full hash still decides the slot, only the radix bits are replaced. Test spilling with a low memory_limit.

## Feedback on your previous attempt

Your earlier changes are still in the working tree. Fix the following and finish again.

**Failed: independent review.**

- src/execution/radix_partitioned_hashtable.cpp Sink (new block ~l.573-593): all 12 radix bits [36,48) are replaced by hash(group prefix). Every row of a given group then lands in one partition at every radix-bit count, so external repartitioning (SetRadixBitsToExternal / Repartition) can no longer split a heavy group.
- Finalize memory: radix_partitioned_hashtable.cpp:692-706 sets the minimum reservation to max_partition_size. Example: `SELECT g, count(DISTINCT x) FROM t GROUP BY g` with ~5000 g values (estimate >= 4096, so the gate fires) where one g value or NULL holds 90% of 1B distinct-x rows, under a low memory_limit. One distinct partition now holds ~90% of the data, giving a huge reservation or an OOM failure where the old hash(G,x) partitioning spread it out. Distinct finalize also collapses to roughly one task.
- physical_hash_aggregate.cpp: the estimated_cardinality >= 4096 gate does not protect against skew, or against estimates of >= 4096 when the true group count is small (common after joins). The spill test used 300K uniform groups, which cannot expose this.
- Correctness is otherwise fine: distinct grouping_set is an ordered std::set with main groups first, and stored hashes are reused consistently for resize, combine and repartition. The sink_count move does not double count. HLL effect is negligible.
- Measured benefit is weak: q16 -2.6%/-7.1%/-10.8% across runs, full-bench geomean 0.0%.
- Required: Do not take every radix bit from the group hash. Take only the top k radix bits (e.g. bits [48-k,48) with k around 4-6, matching the initial sink partitioning) from hash(groups), and keep the lower radix bits from the full hash so skewed groups can still be split by external repartitioning. Results do not require each partition to hold whole groups, because distinct finalize re-aggregates into the main HT.
- Required: Add a spilling check with one dominant group (e.g. 90% of rows in one group, high-cardinality distinct column, low memory_limit) and show it neither fails nor regresses badly against the baseline.

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
