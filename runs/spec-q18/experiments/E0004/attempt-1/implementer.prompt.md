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

### Ablation-timed breakdown of radix agg sink per-group cost, then fix the top component

**Hypothesis.** New R4 measurements (dbe-tool sql, hot, 8 threads): SELECT max(s) FROM (SELECT l_orderkey k, sum(l_quantity) s FROM lineitem GROUP BY k) = 455 ms (15M groups). The same with k = l_orderkey//64 (~230K groups, same 60M rows, same clustering) = 220 ms, and //4 (~3.75M groups) = 284 ms. A plain scan with the //64 expression = 115 ms. So the per-row agg path costs ~105 ms wall, and the per-GROUP cost is ~235 ms wall at 15M groups (~125 ns CPU/group, linear in group count). Single-threaded: //64 1.33 s vs full 5.18 s => ~257 ns/group. Three blind attempts at parts of this cost found nothing: E0001 probes (-13% CPU, ~0 wall), E0002 finalize re-materialization (0), E0003 unpartitioned staging (0). We are guessing component by component at 1 round each. One ablation round that times each sink sub-step on the 15M-group query will show which component holds the ~125 ns/group, and then allow a targeted fix in the same round.

**Plan.** Step 1 (measurement, temporary code, never committed): in a scratch build, time the isolated query above (3+ hot runs each via dbe-tool sql; results may be wrong during ablation, which is fine because only timing matters) with each of these removed in turn: (a) RowOperations::InitializeStates in FindOrCreateGroupsInternal (aggregate_hashtable.cpp ~:766); (b) the UpdateAggregates call in GroupedAggregateHashTable::AddChunk (aggregate_hashtable.cpp ~:519 onward); (c) the Abandon()+MaybeRepartition block in RadixPartitionedHashTable::Sink (radix_partitioned_hashtable.cpp :578-600), by forcing one big local HT instead (e.g. local_sink_capacity = 1<<22 after adaptation), which also tests 'fewer abandons'; (d) the hll.Update path (enable_hll), which only runs for the first 1M rows, as a sanity check; (e) the RadixHTLocalSourceState::Finalize/Scan work, by making GetData emit nothing once Finalize is done. Also compare with skip_lookups forced on (pure append, no probe) to separate probe from materialization. Record wall per variant in the ledger notes. Step 2 (real change): if (c) gives >=8%, implement a generality-safe capacity rule in DecideAdaptation (radix_partitioned_hashtable.cpp:424): when dedup is already near the HLL estimate (potential_increase_rate ~1) and the cardinality is high, grow local_sink_capacity up to an L2/L3-sized bound to cut abandon and repartition frequency. If (a) or (b) dominates, look for a per-call overhead fix in RowOperations::InitializeStates or AggregateExecutor scatter (e.g. a fast path for a single fixed-size state with a trivial initialize). If (e) dominates, revisit the source scan/finalize path. If nothing exceeds 8%, stop after step 1 and report the full table. Either result is useful.

**Target files.** src/execution/aggregate_hashtable.cpp, src/execution/radix_partitioned_hashtable.cpp, src/common/row_operations/row_aggregate.cpp

**Expected gain.** q18: 0-15%. The measurement alone decides rounds 5-6. A step-2 fix that targets the dominant per-group component could reach 10-15% because the per-group cost is ~50% of the subquery aggregate.

**Generality.** Every high-cardinality parallel hash aggregate (GROUP BY on a near-unique key, DISTINCT, IN/EXISTS subqueries with GROUP BY HAVING). A capacity-rule change could hurt low-dedup random-key aggregates if the HT outgrows cache, so bound it by L2/L3 size and gate it on the measured dedup ratio.

**Risk.** Low for step 1 (temporary). Medium for step 2, depending on which fix. The memory interplay with external aggregation must be kept: never grow capacity when gstate.external.



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
