You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Exact BF for sparse perfect hash joins, filled from the perfect-HT slot bitmap

**Hypothesis.** In q07 (187ms, 6.2% of total) the lineitem scan emits 18.23M rows, and its only dynamic filter is `optional: l_suppkey>=3 AND <=99999`. The l_suppkey=s_suppkey HASH_JOIN then drops them to 1.46M (8%), costing 0.19s CPU plus a 0.025s projection (warm JSON profile, .dbe/scratch_q07.json). The build has 8016 supplier keys in a 100k range, so it takes the perfect HJ path (range <= MAX_BUILD_SIZE 1M). JoinFilterPushdownInfo::CanUseBloomFilter (physical_hash_join.cpp:946) returns false for every perfect hashtable, on the reasoning that 'with a perfect hashtable we expect good min/max pruning'. That only holds for dense builds. Region- or nation-filtered dimension tables (supplier, customer, part under 1M range) are sparse, so min/max prunes nothing. A prior run tried a BF on sparse perfect HJ (q21) and found that rows dropped 37.9M->2.7M but scan CPU rose. That was before two things landed: the exact bitmap BF for small ranges (E0022), whose probe costs about half a hashed one, and the per-value BitPacking select (E0027), which makes the non-filter columns (here l_orderkey, l_extendedprice, l_discount) cost proportional to selectivity. Until E0027 they were fully decoded and then sliced. The perfect HT already holds an exact bitmap of the build keys, bitmap_build_idx (slot = key - build_min), so filling the BF costs a word copy instead of a pass over the HT.

**Plan.** 1) In JoinFilterPushdownInfo::CanUseBloomFilter (physical_hash_join.cpp ~938), stop rejecting a perfect hashtable outright. Allow it when it is sparse: ht->Count() * 4 <= range + 1. Add a parameter, or let the caller compute it, using perfect_join_statistics.build_range or max-min. 2) In FinalizeFilters (~1163), for the perfect case on the no-cast, no-offset path: call TrySetExactBloomFilter(*ht, op, min_val, max_val). The range is < 1M, so the small-range floor always makes it exact. Then add the entry to deferred_bloom_filters as today, but do NOT call ht->SetBuildBloomFilter for the HT finalize, which never runs for a perfect HJ. If the BF did not become exact, skip it. 3) Add PerfectHashJoinExecutor::FillExactBloomFilter(BloomFilter &bf) in perfect_hash_join_executor.cpp/.hpp. It calls bf.Initialize(context, count). It needs exact_min == build_min widened the same way TrySetExactBloomFilter widens it (int64 for signed types) and exact_range == build_range; assert both. It then copies the bitmap_build_idx words into the bf words. Both use 64-bit LSB-first words with bit i == slot i, so bloom_filter.hpp needs an accessor or a friend for the raw word pointer. If bitmap_build_idx.AllValid() (no data pointer), set all bits, or just skip the BF because that case is dense. 4) Push the deferred BFs right after the perfect build is final, through PushBloomFilter. This happens in two places. The serial path is PhysicalHashJoin::Finalize after FinalizeFilters (~1299), when use_perfect_hash is true. The parallel path is PerfectHashJoinBuildEvent::FinishEvent (~656), after FinishBuild returns true. If use_perfect_hash turns out false (duplicates), keep today's behaviour: the regular HT finalize builds and pushes the BF. Make sure the deferred list is not pushed twice and that the BF is not left half-initialized for the fallback. 5) Verify. Check that the q07 lineitem scan shows `l_suppkey IN BF(s_suppkey)` and that its output cardinality drops from 18.2M to ~1.5M, and that results match. Run a micro A/B on q07 hot (3x each). Also check a RIGHT perfect join (q13 customer, dense) and confirm it still gets no BF, because of the density gate.

**Target files.** src/execution/operator/join/physical_hash_join.cpp, src/execution/operator/join/perfect_hash_join_executor.cpp, src/include/duckdb/execution/operator/join/perfect_hash_join_executor.hpp, src/include/duckdb/planner/filter/bloom_filter.hpp

**Expected gain.** q07 -8..-15%: about 0.2s CPU of ~1.5s saved in HJ probe and projection, offset by an exact BF probe on 18M rows. Possibly also q02 (ps_suppkey = region-filtered supplier) and q08 (supplier/customer sides). Hidden templates with nation- or region-filtered supplier/customer builds probing lineitem/orders/partsupp (q20, q21-like) should gain too.

**Generality.** Any equi-join whose build is a selective dimension subset with a key range under 1M (perfect HJ), probing a large fact table. This is very common: star joins with region/nation/category filters. Queries where the BF is unselective are protected by the 25% density gate and SelectivityOptionalFilter's runtime auto-disable. Possible slowdown: a probe scan whose BF check costs more than the perfect-HT probe it replaces, which can happen when there are few extra columns and selectivity is moderate (~20%).

**Risk.** Low-medium. The bitmap copy must use exactly the same min and widening as the BF lookup; a mismatch gives wrong results, so test with negative or offset key ranges (e.g. a join on s_suppkey - 50000) and compare against `+0` variants. The fallback-to-regular-HJ path (duplicates) must not push a BF that was never filled.



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
