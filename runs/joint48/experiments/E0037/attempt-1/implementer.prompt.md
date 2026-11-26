You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Partition-local slot addressing for in-memory HJ finalize

**Hypothesis.** Hash-join builds over 1M rows are expensive per row, even with no probe. q03's o_orderkey HJ costs 0.20s CPU when the probe side is empty: count(*) with l_shipdate > 1998-11-30 gives 0 probe rows, and the build has 1.45M rows, so that is about 137ns per build row. Payload width does not matter: count(*) costs the same as the full q03 payload. In hot q03 the HJ is 0.38s of 1.08s user. In hot q09 the o_orderkey=l_orderkey HJ (3.27M-row build) is 0.80s of 2.65s user, the largest operator. The pointer table is NextPowerOfTwo(count*load_factor) entries, i.e. 4M x 8B = 32MB for q03. InsertHashesLoop (join_hashtable.cpp:591) linear-probes at slot = hash & bitmask, the LOW hash bits. The sink, however, radix-partitions on HIGH bits: RadixPartitioning::Shift/Mask, the bits just below the 16-bit salt. Each finalize task's chunk range therefore scatters inserts over the whole 32MB table, roughly one cache/TLB miss per row. If the slot index is the top log2(capacity) bits below the salt, i.e. slot = (hash >> (48 - log2cap)) & bitmask, the slot's top bits equal the radix partition bits. Every partition then owns a contiguous capacity/2^radix_bits region (2MB for q03), and a finalize task working inside one partition writes L2/L3-resident memory.

**Plan.** 1) First verify cheaply with a temporary timer or a perf breakdown that the finalize insert dominates the build CPU on the q03 build-only micro (shown in memory). If sink append dominates instead, stop and report. 2) In JoinHashTable (src/include/duckdb/execution/join_hashtable.hpp and src/execution/join_hashtable.cpp), add a member `slot_shift`, set in InitializePointerTable/AllocatePointerTable (~line 787-817). For the in-memory single-round path, use 48 - log2(capacity), clamped at >= 0. For the external/partitioned-round path (PrepareExternalFinalize, physical_hash_join.cpp ~1244 sets EXTERNAL_LOAD_FACTOR), keep 0, i.e. today's low bits. A round holds only a subset of partitions, so high-bit slots would cluster there. 3) Apply the shift everywhere a slot is derived: ApplyBitmaskAndGetSaltBuild, the probe-side bitmask application (~line 151-161, GetRowPointers and the salt/offset code), and any other `& bitmask` use (grep it). Linear-probe wrap-around stays `& bitmask`. The salt stays the top 16 bits. 4) Make the finalize tasks (physical_hash_join.cpp, the parallel finalize with chunks_per_task) iterate chunks in partition order. Check that data_collection is combined partition by partition. If it is not, combine it that way, or give each task a single partition's chunk range. 5) Correctness checks: INNER/LEFT/RIGHT/FULL/SEMI/ANTI/MARK joins, NULL keys, a forced external join (small memory_limit), duplicate-heavy keys, and both sides of PARALLEL_CONSTRUCT_THRESHOLD.

**Target files.** src/execution/join_hashtable.cpp, src/include/duckdb/execution/join_hashtable.hpp, src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** Builds over 1M rows. q03 HJ 0.38s→~0.25s (-5..-10%); q09 orderkey HJ 0.80s (-5..-8%); smaller gains on q05/q07/q08/q18/q21-like plans. Estimated geomean -2..-4% if the finalize-insert share is as large as the miss model predicts.

**Generality.** Any in-memory hash join whose pointer table is larger than L2/L3 (>~500K build rows), which covers most fact-to-dimension and fact-to-fact joins. Small builds are unchanged, since their table fits in cache either way. The external path is left as is.

**Risk.** Medium-high. Slot addressing must be identical on build and probe, or rows will be missed: test every join type and the external path. A poor hash high-bit distribution could lengthen probe chains, but DuckDB hashes are murmur-mixed. If the finalize share is small, the gain is too, so step 1 gates the work.



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
