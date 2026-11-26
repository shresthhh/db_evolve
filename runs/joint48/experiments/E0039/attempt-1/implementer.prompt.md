You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Huge pages for large join tables v2: HJ pointer table >=8MB + perfect-HJ slot arrays

**Hypothesis.** E0038 (THP-backed HJ pointer table for tables >=32MB) just missed acceptance. q09 came in at -7.0% against a noise threshold of 8.6%; implementer runs gave q09 -8.4/-15/-9.3%, q03 -3..-13% and q08 -8%, with nothing slower once free-time DONTNEED+NOHUGEPAGE was added. At 32MB the threshold left the second big random-access join in q09 on 4KB pages. That is the (ps_partkey,ps_suppkey) HJ: build 435K rows, 1M slots = 8MB pointer table, probed 3.27M times, 0.49s of q09's 2.65s CPU. An 8MB table is beyond the 4KB-page L2 TLB reach (~6MB), so every probe costs a TLB miss plus a page walk. The same applies to perfect-HJ slot_to_row/build_bits arrays sized to the key range (perfect_hash_join_executor.cpp:158/162). q13's RIGHT perfect HJ over 1.5M customers uses a 12MB slot_to_row array, and the sparse perfect HJs in q07/q02 behave the same way. Huge pages for every random-access join table of 8MB or more should push q09 well past its noise and add gains on q03/q08/q13.

**Plan.** 1) Re-apply E0038 in src/execution/join_hashtable.cpp as described in the ledger. Allocate through BufferAllocator with 2MB slack and align `entries` to 2MB. Call madvise(MADV_HUGEPAGE) before InitializePointerTable, only when /sys/kernel/mm/transparent_hugepage/enabled is [madvise] or [always]. PointerTableUsableSize() handles non-power-of-two padded sizes. On free, in the destructor, Reset() and the grow path, call MADV_DONTNEED then MADV_NOHUGEPAGE; this step is mandatory, or q02 gets 5-9% slower. 2) Lower the threshold from 32MB to 8MB (1M slots). 3) Factor the align+madvise+cleanup logic into a small static helper or RAII struct in join_hashtable.cpp, or a new common header. Use it in PerfectHashJoinExecutor (src/execution/operator/join/perfect_hash_join_executor.cpp:158-162, and slot_found_match at 297/418) when an array is >=8MB, in place of make_unsafe_uniq_array. 4) Measure q09, q16, q03 and q02 alone several times each before the full bench. Watch q16 in particular: its table is 8MB with 296K build rows, and it swung -14..+7% at a 4MB threshold. If q16 is slower beyond its noise, gate on build rows >= 400K instead.

**Target files.** src/execution/join_hashtable.cpp, src/execution/operator/join/perfect_hash_join_executor.cpp, src/include/duckdb/execution/join_hashtable.hpp

**Expected gain.** q09 -9..-14%, q03 -5..-10%, q08 -5..-8%, q13/q07 a few %. Geomean -2..-3%.

**Generality.** Any hash join whose build exceeds ~250K rows, or any perfect HJ over a key range of 1M or more. That covers FK joins against fact tables and large dimensions. Small joins are untouched. A query with a mid-size build that runs only once may pay THP fault/compaction cost.

**Risk.** Medium-low. Memory is tracked by the same allocator. The main hazard is huge-page state leaking into recycled jemalloc memory, which the free-time cleanup handles. q16 is borderline at the 8MB threshold.



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
