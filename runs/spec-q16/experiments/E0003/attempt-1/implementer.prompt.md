You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q16` (instances are in `.dbe/queries/`). The only timing that
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

### Early tentative SkipLookups for near-unique radix aggregate sinks

**Hypothesis.** In q16 the count(DISTINCT) aggregate first sinks into a distinct radix table keyed on (brand, type, size, suppkey). Those keys are almost all unique. A plain GROUP BY on the same 4 keys returns 1,184,608 groups from 1,184,892 input rows, and its HASH_GROUP_BY alone takes 0.84 s CPU, more than the 0.67 s the whole distinct aggregate takes. Each of the 8 threads sees only about 150k rows. That is far below ADAPTIVITY_THRESHOLD = 1M, so DecideAdaptation (radix_partitioned_hashtable.cpp:424) never fires and the table never switches to SkipLookups, even though it has a hll_percentage > 0.95 rule written for exactly this case. So every row pays for the probe, key compare (on a VARCHAR key), HT insert and unpartitioned staging. Then about every 21845 rows the HT is Abandon()ed (32768 capacity), having deduplicated nothing. E0002 measured this sink at about 253 ms CPU for AddChunk, 40 ms for Abandon and 100-146 ms for MaybeRepartition/staging, about 400 ms of roughly 1.44 s total CPU. All of that dedup work is redone in the finalize Combine anyway. With SkipLookups the sink only hashes and appends straight to partitioned_data. That also bypasses the unpartitioned staging and repartition that E0002 found to be the VARCHAR-specific cost.

**Plan.** In src/execution/radix_partitioned_hashtable.cpp, RadixPartitionedHashTable::Sink, at the point where `ht.Abandon()` is called (more than 2 threads, not external), add an early, reversible adaptation while `!lstate.adapted`. Right after the Abandon, compute sink_count = ht.GetSinkCount(), hll = MinValue(ht.GetHLLUpperBound(), sink_count) and materialized = ht.GetMaterializedCount(). If hll/sink_count > 0.95 AND materialized/sink_count > 0.95, call ht.SkipLookups(). The second test is the HT's actual dedup, so data with real duplicates inside one HT fill never triggers. Otherwise, if lookups are currently skipped, turn them back on. Add `void GroupedAggregateHashTable::SetSkipLookups(bool)`, or `EnableLookups()`, in src/execution/aggregate_hashtable.cpp and src/include/duckdb/execution/aggregate_hashtable.hpp. Toggling right after Abandon is safe because the pointer table is cleared and count is 0. Keep the HLL enabled and leave `adapted` false, so the existing 1M-row DecideAdaptation still makes the final call. Optionally, when hll_pct exceeds 0.95 there, it keeps skip_lookups. When the data later turns duplicate-heavy, the re-check at the next abandon (each fill, about 21k rows) re-enables lookups. Do not touch the grow-strategy path (2 threads or fewer). Validate with q16, with a plain high-cardinality GROUP BY, and with a low-cardinality GROUP BY such as 25k groups over 10M rows, to confirm that one does not trigger. Using hash(p_type) in the query is a cheap way to bisect.

**Target files.** src/execution/radix_partitioned_hashtable.cpp, src/execution/aggregate_hashtable.cpp, src/include/duckdb/execution/aggregate_hashtable.hpp

**Expected gain.** q16 8-15%. It should remove most of the roughly 300-400 ms CPU of probe, abandon and staging work in the distinct-table sink. The finalize Combine sees the same row count as before, because the HT deduplicated nothing.

**Generality.** Any count(DISTINCT x) GROUP BY g, where (g, x) is near-unique, and any high-cardinality GROUP BY or DISTINCT with fewer than 1M rows per thread (about 8M total at 8 threads), the size where the existing adaptation never fires. Possible slowdowns: data whose first ~20k rows per thread are unique but which has many duplicates later. The per-fill HLL re-check bounds that to at most one fill of skipped dedup per transition.

**Risk.** Low to medium. SkipLookups is an existing, correctness-safe mode: the finalize always deduplicates. The main risk is a performance regression on data that is unique early and duplicated later, which the reversible check mitigates. HLL accuracy at about 20k rows is a few percent, so the 0.95 threshold has some margin.



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
