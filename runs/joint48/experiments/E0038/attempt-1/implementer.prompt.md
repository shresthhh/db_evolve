You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Huge-page backed hash-join pointer table for large builds

**Hypothesis.** Large in-memory HJ builds cost ~100-200ns per build row, and more than half of that is not the input scan. Build-only micro (hot, 8 threads; lineitem 1995 = 9.1M build rows, 0 probe rows, forced with SET disabled_optimizers='join_order,build_side_probe_side'): HJ query 1.34s user + 0.42s SYS vs 0.40s user / 0 sys for the bare scan. That leaves about 0.95s user, ~104ns per row, plus 0.4s of kernel time. BF fill is only ~0.1s of it (join_filter_pushdown off: 1.21-1.24s). In hot q07 the middle HJ builds 1.46M lineitem rows and probes 100K orders: 0.287s CPU (~196ns per build row). q09's o_orderkey HJ (3.27M build) takes 0.80s and q03's (1.45M build) 0.38s. E0037 showed that partition-local slots do not shrink the working set. The pointer table is NextPowerOfTwo(count*2) 8-byte entries (join_hashtable.hpp:417): 32MB for 1.45M rows and 256MB for 9.1M. It comes from buffer_manager.GetBufferAllocator().Allocate (join_hashtable.cpp:804/812). jemalloc runs with oversize_threshold 256MB, so the biggest tables are fresh mmaps every query, and the faults and zeroing show up as sys time. Each insert in InsertHashes and each probe in GetRowPointers touches a random 8-byte slot. With 4KB pages a 32-256MB table covers 8K-65K pages, far beyond the L2 TLB (~1.5K entries), so nearly every slot access is a TLB miss plus a page walk on top of the cache miss. With 2MB pages the same table is 16-128 pages, so walks mostly disappear and faults drop 512x.

**Plan.** Step 0 (cheap gate): Read /sys/kernel/mm/transparent_hugepage/enabled and defrag. If enabled is [never], abandon. If [always], the table may already be THP-backed: then check whether the allocation is 2MB-aligned and whether jemalloc's opt_thp or the decay settings defeat it, and measure before coding. Step 1: In src/execution/join_hashtable.cpp JoinHashTable::AllocatePointerTable, when capacity*sizeof(ht_entry_t) >= 4MB (Linux only, #ifdef __linux__), allocate the table so that it is 2MB-aligned and call madvise(ptr, size, MADV_HUGEPAGE) before the first touch. The first touch is InitializePointerTable's std::fill_n, which runs in the parallel finalize tasks. Simplest way: over-allocate by 2MB through the same BufferAllocator (memory accounting unchanged), keep the AllocatedData, and set `entries` to the 2MB-aligned address inside it. Keep hash_map.GetSize() consistent, or keep the usable capacity in a separate member: the reuse branch at :801 divides GetSize() by the entry size and the D_ASSERT at :815 compares sizes, so both need adjusting. Alternatively add a small helper next to the block_allocator.cpp madvise code (src/storage/block_allocator.cpp:72-77) that mmaps 2MB-aligned memory with MADV_HUGEPAGE, freed by munmap through a custom PrivateAllocatorData. Step 2: rerun the build-only micro above, the q07 query and q09, and compare user and sys time with the madvise on and off (a temporary env var or setting is fine during testing; remove it before landing). Optionally apply the same helper to the GroupedAggregateHashTable entries array only if it is the same few lines; otherwise leave it for a follow-up.

**Target files.** src/execution/join_hashtable.cpp, src/include/duckdb/execution/join_hashtable.hpp

**Expected gain.** HJ build and probe CPU on large builds -20..-40% when TLB misses dominate: q09 (0.80s HJ), q07 (0.29s), q03 (0.38s), q05/q08 (similar lineitem-orders joins), q18 outer joins. Roughly -3..-6% geomean if the TLB hypothesis holds; also removes ~0.4s sys per 9M-row build.

**Generality.** Every hash join with more than ~250K build rows (pointer table >= 4MB) on Linux, which is every big fact-to-fact or fact-to-dimension join. Small joins are unchanged, below the threshold. Possible slowdowns: THP compaction stalls when memory is fragmented (defrag setting), and an extra 2MB of slack per large table.

**Risk.** Low-medium. The change is contained to allocation, with no change to hashing semantics. The risks are pointer-alignment bookkeeping with the reuse path in AllocatePointerTable and environment dependence on the THP mode (step 0 gates it). Gain may be small if the kernel already backs these mappings with THP.



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
