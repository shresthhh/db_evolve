You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Lazy-initialised perfect hash aggregate table with a bounded bit extension

**Hypothesis.** E0003 showed that perfect hashing q13's inner aggregate (18 bits, 1.53M rows, 150k groups) saves about 25% wall time (115->90ms, agg CPU 0.20s->0.04s). It also showed that estimate-based acceptance fails: q13 is underestimated 5x and q17 overestimated 1000x. q17 regressed because PerfectAggregateHashTable's constructor (perfect_aggregate_hashtable.cpp:28-48) eagerly calls InitializeStates on all 2^bits slots in every thread, and Combine (:163) and Destroy (:289) walk all 2^bits slots. If states are initialised only on first touch, a perfect table on a near-empty input costs one uninitialised malloc and a memset of 2^bits bool flags, so a cardinality-independent bit cap becomes safe for small inputs.

**Plan.** 1) perfect_aggregate_hashtable.cpp constructor: keep the uninitialised data allocation and the group_is_set memset, and remove the InitializeStates loop. 2) AddChunk (:132-142): when group_is_set[group] is false, set it to true and append the slot address to a new-groups address vector, then call RowOperations::InitializeStates once for those new slots before UpdateStates. Flag first, so a duplicate in the same chunk is not initialised twice. 3) Combine: when the target slot is not set, InitializeStates the target first (batch new targets the same way), then CombineStates. Add a touched-groups counter as a member in perfect_aggregate_hashtable.hpp, incremented on first touch. If other.touched == 0, return early (still move the allocator). Otherwise scan group_is_set 8 bytes at a time (memcpy into uint64_t and skip zero words). 4) Destroy: call destructors only on slots with group_is_set (only those are initialised). 5) Scan: the same word-skip over group_is_set. 6) plan_aggregate.cpp CanUsePerfectHashAggregate (:230): keep the PerfectHtThresholdSetting check, but also accept when total bits <= 18 and 2^bits * an estimated row width stays below about 8MB per thread. Use a file-local constexpr. Do NOT change the setting's default. Build in the background, check with EXPLAIN ANALYZE that q13's inner aggregate becomes PERFECT_HASH_GROUP_BY, then run the full bench and look closely at q17, q14 and q18.

**Target files.** src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp, src/execution/physical_plan/plan_aggregate.cpp

**Expected gain.** q13 about -20% (measured with a forced SET in E0003). Small gains on other GROUP BYs over dense integer keys with 13-18 bits (E0003 quick bench hinted at q02, q03, q07). Geomean maybe 2-3%.

**Generality.** Any GROUP BY on integer keys with a stats range of 4k-262k values (customer, part, supplier and date keys), which is common in analytics. Lazy init also helps existing <=12-bit perfect aggregates on tiny inputs. Could get slower: aggregates with a wide stats range but very sparse actual groups and large inputs (random access over a table up to 8MB instead of a compact HT), and plans with many tiny overestimated aggregates (each pays a 262KB memset per thread).

**Risk.** Medium. Correctness: every state must be initialised before Update, Combine or Finalize, and Destroy must skip uninitialised slots (aggregates with destructors, e.g. list or string min/max). The header change rebuilds a moderate number of files. The 18-bit cap must hold, because 23 bits was measured 10x slower.

## Feedback on your previous attempt

Your earlier changes are still in the working tree. Fix the following and finish again.

**Failed: independent review.**

- src/execution/physical_plan/plan_aggregate.cpp CanUsePerfectHashAggregate: the bit check becomes `perfect_hash_bits > MaxValue(PerfectHtThresholdSetting, 18)`, and the later size check accepts any table of up to 4MB. So `perfect_ht_threshold` no longer limits or disables perfect hashing; it only adds to the built-in 18-bit/4MB allowance. A user who sets `PRAGMA perfect_ht_threshold=0` (the documented way to turn it off, and the workaround for corrupt statistics that triggers the 'exceeded total groups' exception) still gets PERFECT_HASH_GROUP_BY for every key that fits in 18 bits/4MB.
- Concrete break: test/optimizer/perfect_ht.test lines 17-33 set perfect_ht_threshold=0 and then 1, and expect the plan for `SELECT year, SUM(val), COUNT(val), COUNT(*) FROM timeseries GROUP BY year` NOT to contain PERFECT_HASH_GROUP_BY. With this patch the year key (a few bits, tiny state) passes the 4MB check, so these assertions should fail. test/sql/filter/test_filter_clause.test_slow:428 also relies on threshold=0 to force the regular hash path. This overrides what the user configured.
- The lazy-initialisation part of perfect_aggregate_hashtable.cpp looks correct. AddChunk flags each group before initialising it, so a group repeated in one chunk is initialised once; the error path initialises the slots already flagged; Combine initialises new target slots before combining them; Destroy and Scan visit only set slots; NextSetGroup handles the tail of the flag array when its length is not a multiple of 8. I see no correctness issue in this file.
- Required: Keep perfect_ht_threshold as a strict upper bound that the user controls. Either add the 18-bit/4MB extension only when the user has not changed the setting (it is at its default), or never let the extension go above an explicitly configured value. In both cases perfect_ht_threshold=0 or 1 must still disable perfect hashing as test/optimizer/perfect_ht.test expects.
- Required: Run test/optimizer/perfect_ht.test, test/sql/aggregate/aggregates/test_perfect_ht.test and test/sql/filter/test_filter_clause.test_slow and confirm they pass unmodified.

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
