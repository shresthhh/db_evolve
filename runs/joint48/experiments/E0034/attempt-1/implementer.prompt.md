You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Partition-staged sink for large perfect hash aggregate

**Hypothesis.** The large perfect hash aggregate (is_large, 13-22 bits) is limited by cache misses. Each thread keeps a private table: q13's c_custkey has 2M slots × 8B, plus a 2MB is_set array, about 18MB per thread and about 144MB for 8 threads. Every input row then does a random read-modify-write that misses L2/L3. Evidence: q13 PERFECT_HASH_GROUP_BY takes 0.85s CPU (about 28% of the 377ms wall time). A micro test, `SELECT o_custkey, count(o_orderkey) FROM orders GROUP BY o_custkey` (15M rows, 1M groups), shows the cost per row:
- At 8 threads it runs 117ms wall with HA CPU 0.94s, about 62ns/row. The plain scan is 9ms.
- On 1 thread it takes 241-337ms. The same query grouped by o_orderdate (a 2.4K-slot table) takes 92ms on 1 thread.
- Time is roughly linear in input rows (1.87M rows: 30ms; 3.75M: 55ms; 15M: 117ms), so fixed costs such as allocation, page faults and combine are small (about 15ms).

Staging rows by slot stripe before updating should fix this. Each flush then touches only one stripe of about 512KB, which stays in L2, so most misses become L2 hits. The staging writes are sequential per stripe.

**Plan.** Code: src/execution/perfect_aggregate_hashtable.cpp (AddChunkLazy, around line 213) and its header. physical_perfecthash_aggregate.cpp (Sink around line 138, Combine around line 187) needs only a call to the new flush.

1. Gate. Enable staging only when lazy_init is set, total_groups * (tuple_size + 1) > 2MB, and all payload types are fixed-width (no VARCHAR/LIST). Aggregate filters may be allowed if their boolean filter column is staged like any other payload column; otherwise gate them off.
2. Add a local staging structure to PerfectAggregateHashTable. It has P partitions, one per stripe of LARGE_PERFECT_HT_STRIPE_SIZE (2^16) slots; move that constant into the header or pass it in. Each partition has a DataChunk with STANDARD_VECTOR_SIZE capacity, holding the payload types plus one UBIGINT column for the slot index. Allocate partitions lazily on first use.
3. New AddChunkStaged(groups, payload):
   - Compute the slot indices with ComputeGroupLocation and the existing bounds check.
   - Counting-sort row indices into one SelectionVector per stripe (stripe = slot >> 16).
   - For each non-empty stripe, flush first if its chunk would overflow. Then VectorOperations::Copy each payload column with that sel into the partition chunk at offset size (this keeps validity), write the slot indices, and SetCardinality.
4. FlushPartition(p) reuses the AddChunkLazy body, but takes the slot indices from the staged UBIGINT column instead of recomputing them: addresses = data + slot * tuple_size, lazy is_set initialization, then UpdateStates / UpdateFilteredStates on the staged payload chunk. Reset the chunk afterwards.
5. Add FlushAll(). Call it from PhysicalPerfectHashAggregate::Combine before the striped CombineRange; it is done per thread, on the local table.
6. When the gate is false, Sink keeps calling AddChunkLazy unchanged.

Correctness checks: compare against `SET perfect_ht_threshold=8` (radix path) on these queries:
- count/sum/min/max with NULL payloads (the q13 LEFT JOIN count(o_orderkey))
- NULL group keys (slot 0)
- multi-column groups
- FILTER clauses
- avg over DOUBLE, where only last-digit float differences are acceptable

Then time the micro query above on 1 and 8 threads.

**Target files.** src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp, src/execution/operator/aggregate/physical_perfecthash_aggregate.cpp

**Expected gain.** q13: if HA CPU drops from 0.85s to about 0.35s, that is about 60ms wall, or -12..-18%. Other visible templates use large perfect HA little, so expect about 0 for them. Visible geomean about -1..-1.5%. The micro query should go from 117ms to about 60ms.

**Generality.** Any GROUP BY on dense integer keys with 2^18-2^22 distinct groups (customer/part/supplier keys, dates × small dims) whose input is not clustered on the key. These get faster whenever the per-thread table is bigger than L2. Workloads that could get slower:
- Inputs already clustered on the key, where the old path hits cache anyway; staging then adds about 3-5ns/row of copying.
- Very small inputs, which pay for allocating the staging chunks.

The 2MB table-size gate limits both cases. Small perfect HAs are untouched.

**Risk.** Medium.
- Correctness: validity must be copied through staging. Filters and the payload_idx bookkeeping must match AddChunkLazy. A flush missed before Combine silently loses rows. Each of these is caught by the A/B against perfect_ht_threshold=8.
- Performance: the per-stripe VectorOperations::Copy overhead (32 stripes × columns per chunk) could eat the gain when there are many payload columns. A fallback is to gate on payload column count ≤ 4.



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
