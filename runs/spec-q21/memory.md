## Planner memory (q21 specialisation run)

## Tooling facts
- dbe-tool profile / sql output is truncated (~150 lines / by width). Prefer Read/Grep.
- **Every `dbe-tool sql` call is a FRESH PROCESS with a cold buffer pool.** Warm up in the same call first.
- Full warm profile recipe (works): one sql call with `CREATE TEMP TABLE w AS <q>; CREATE OR REPLACE TEMP TABLE w AS <q>; PRAGMA enable_profiling='json';
  SET profiling_output='/home/shresth/dev/db_evolve/work/slots/slot0/.dbe/p.json'; CREATE OR REPLACE TEMP TABLE w AS <q>; PRAGMA disable_profiling;`
  Then a second call: `SELECT string_agg(trim(line),' ') FROM (SELECT unnest(string_split(content, chr(10))) line FROM read_text('<path>')) WHERE line SIMILAR TO
  '.*(operator_name|operator_timing|operator_cardinality|"latency|Filters|Join Type|Conditions|Table).*'` (one row, so no truncation).
- Shell variables and `$(...)` are blocked. `EXPLAIN (FORMAT json)` times out. Operator timings are summed CPU across threads; latency is wall time.

## Warm facts, CURRENT BEST (verified round 5, SF10, 8 threads)
- Latency ~1.03s, ~7s summed CPU, so q21 is CPU-bound.
- Operator CPU: l1 scan 0.35 + FILTER 0.125 + suppkey join 0.28; orders scan 0.34 (BF on l_orderkey); orders⋈l1 0.37; RIGHT_DELIM 0.25; LEFT_DELIM 0.12;
  **l2 INNER join 1.79s** (60M probe → 2.93M), l2 scan 0.33 (min/max only); RIGHT_SEMI 0.41; **l3 INNER join 1.09s** (37.9M → 1.85M), l3 scan 0.35; ANTI 0.35.
- lineitem is clustered by l_orderkey (~4 rows/key). lineitem cols are BitPacking.
- Why l2/l3 joins are expensive: ~56M of 60M probe rows MISS. Each miss = hash + random load into a multi-MB pointer table
  (ProbeForPointersInternal join_hashtable.cpp:188). Repeated keys hit cache, so the cost is ~15M distinct DRAM misses. Hash-probe run-dedupe would NOT fix that (low value).

## Codebase facts
- Optimizer order: BUILD_SIDE_PROBE_SIDE (optimizer.cpp:247) before JOIN_FILTER_PUSHDOWN (:320).
- GenerateJoinFilters: build_side_has_filter at join_filter_pushdown_optimizer.cpp:302-309; skips LEFT/OUTER/ANTI/RIGHT_ANTI/RIGHT_SEMI/MARK/SINGLE.
  The q21 subquery joins are INNER (lineitem probe ⋈ DELIM_SCAN build, ok= AND sk<>).
- BF gate: CanUseBloomFilter physical_hash_join.cpp:761. PushBloomFilter :787 wraps the BF in SelectivityOptionalFilter (BF_THRESHOLD).
  Deferred BFs are pushed in HashJoinFinalizeEvent::FinishEvent (:584) after the parallel finalize. BF is filled from hashes in JoinHashTable::InsertHashes (:717),
  initialized in AllocatePointerTable (:741). BF impl: src/planner/filter/bloom_filter.cpp (Filter :96, CheckStatistics :173).
- Optional min/max filters are zonemap-only. Perfect HJ: perfect_hash_join_executor.cpp, MAX_BUILD_SIZE 1,048,576.

## History
- E0001 RETIRED (+1%): BF for 1 eq + non-eq conds, DELIM_GET build.
- E0002 RETIRED: BF for sparse perfect HJ (l1 suppkey): BF hashing cost > savings on cheap scan.
- E0003 RETIRED (0%): BF on l2/l3 scans: rows 60M→3.5M, but scan CPU +0.6-0.9s each.
- E0004 RETIRED: BF run-dedupe alone; no BF target in the current best (stale premise).
- E0005 RETIRED (-4%, needs -5%): E0003 + run-dedupe BF probe. Joins -2.2s CPU, scans +0.7s CPU. Wall gain smaller than the CPU math predicts.
- Round 6: dispatched exact key-bitmap mode for the BF (bit test at key-min for dense integer build keys) + E0005 pushdown.
  Rationale: cut the BF scan overhead (random hashed sector access) to a sequential bit test for clustered probe keys.
  If this also lands at ~-4%, the scan-side filter route is exhausted. Next would be restructuring the subqueries (below).

## Ideas for later
- Big/risky: rewrite EXISTS/NOT EXISTS (k= AND s<>) as per-key aggregates (count distinct suppkey per orderkey, min/max suppkey trick); share the l2/l3 scans.
- Investigate why the wall gain is << CPU saving (pipeline critical path / SMT on the WSL 8-thread box) before more CPU-shaving work.
- Hash-probe run-dedupe (old backlog issue): low value given the miss analysis above.
