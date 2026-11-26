You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Bundle: sparse perfect-HJ exact BF (E0028) + branch-free fixed 8-byte BitPacking per-value extract

**Hypothesis.** E0028 was a near-miss with no regressions. It got q07 -9.0% in the official run (-11.5/-12.9/-17.7% in the implementer's runs; it needed -13.1%), q02 -7..-22%, visible geomean -1.9% (-3.2% implementer), and hidden validation passed. Today's q07 profile shows why it helps: the lineitem scan feeds the l_suppkey=s_suppkey perfect HJ (0.24s CPU) with 18.2M rows that pass only min/max, and the HJ cuts them to 1.46M. With the slot-bitmap exact BF the scan emits about 1.46M rows. At that density (~8% < 1/4) the other lineitem columns (l_orderkey, l_extendedprice, l_discount, l_shipdate) go through the E0027 per-value BitPacking select. So in q07 the select path now carries most of the decode work, and the same is true for every BF-filtered scan (q05/q08/q09/q14/q19). The per-value extraction, BitpackingExtractValue (bitpacking.cpp:876), does memcpy(&bits, ptr, byte_count) with byte_count computed at runtime. That is a variable-length copy, usually an out-of-line memcpy call plus branches, done for every selected value. r11 measured ~26ns/value over count(*) at 5% pass, which is far above the ~1-2ns a shift-and-mask should cost. Loading a fixed 8 bytes (memcpy with a constant size of 8 compiles to one mov) removes the call. This is Part 2. It speeds up the path E0028 sends more rows into, and it gives a general gain on every sparse-select scan.

**Plan.** Part 1: re-apply E0028 exactly as described in the ledger, keeping all three of its pieces. (a) In physical_hash_join.cpp, JoinFilterPushdownInfo::FinalizeFilters / CanUseBloomFilter (~946): let a perfect HT through when count*4 <= range+1, accept the exact BF only (TrySetExactBloomFilter must succeed), and do not set SetBuildBloomFilter. (b) Add PerfectHashJoinExecutor::FillExactBloomFilter in perfect_hash_join_executor.cpp: InsertExact(build_min widened to 64 bits + slot) for each set bit of bitmap_build_idx, or for every slot if the build is dense. (c) Add a helper PushPerfectHashJoinBloomFilters, called after FinalizeFilters when use_perfect_hash is set, in both the serial PhysicalHashJoin::Finalize path (~1282-1300) and the parallel PerfectHashJoinBuildEvent::FinishEvent (~648, after FinishBuild). Part 2: in src/storage/compression/bitpacking.cpp, BitpackingSelect FOR branch (~930-940): when the 8-byte read stays inside the segment buffer, load uint64 with memcpy(&bits, p, 8), then shift and mask. Compute a per-call safe limit from the segment handle pointer + segment.SegmentSize() (or the block size), and fall back to the existing variable-length BitpackingExtractValue only for values whose byte offset + 8 exceeds it. Hoist the mask ((1<<width)-1) and the width out of the loop. Optionally also hoist the per-value `group_pos - idx_in_block` arithmetic: block_start = group_ptr + (group_pos/32)*4*width bytes. Test correctness on an ATTACHed file db with force_compression='bitpacking' + CHECKPOINT (TEMP tables are never compressed): compare sum() of a selectively filtered BIGINT/INTEGER column at widths 1..56 against the uncompressed table. Then run the E0028 correctness queries again (negative shifted keys, RIGHT join with a NULL build row, USMALLINT key, parallel sparse build).

**Target files.** src/execution/operator/join/physical_hash_join.cpp, src/execution/operator/join/perfect_hash_join_executor.cpp, src/include/duckdb/execution/operator/join/perfect_hash_join_executor.hpp, src/storage/compression/bitpacking.cpp

**Expected gain.** q07 -12..-18%, q02 -7..-20% (from E0028). Part 2 adds a few % on the sparse-select scans in q07/q05/q08/q09/q14/q19. Visible geomean -3..-5%.

**Generality.** Part 1: any FK join against a selectively filtered dimension whose key range is <=1M (or <=4M dense) and that the perfect HJ handles: the classic star-schema case. Part 2: every scan whose non-filter BitPacking columns are decoded through a sparse selection (all BF/zone-filtered scans). Possible slowdown: sparse perfect builds whose BF does not filter, but SelectivityOptionalFilter switches those off. Part 2 has no algorithmic change.

**Risk.** Low-medium. Part 1 already passed hidden validation once. In Part 2 an out-of-bounds read at the segment end is the only hazard, and the bounds guard handles it. A wrong shift or mask would show up in the width-sweep test.



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
