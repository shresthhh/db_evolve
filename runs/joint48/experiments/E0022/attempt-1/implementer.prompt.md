You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Exact BF bitmap for small absolute key ranges

**Hypothesis.** q17 hot profile (JSON profiling, warm run): two lineitem scans take 0.77s and 0.68s CPU out of ~1.7s total. Each reads 60M rows and emits 368,435 rows through 'l_partkey IN BF(p_partkey)', but only 59,686 rows join, so about 85% of the emitted rows are false positives from the hashed BF. The build has 2,001 keys over range 32..1,999,954, which is about 1,000 bits per key. TrySetExactBloomFilter (physical_hash_join.cpp:893-941) caps exact mode at EXACT_BF_MAX_BITS_PER_KEY=128 bits per key, so the filter stays hashed even though an exact bitmap would be only 256KB. In q21 the exact mode cut BF scan CPU 0.83->0.38s (auto-memory exact-bitmap-bf-q21). The 128 cap existed to bound memory for large ranges, not because small bitmaps are slow.

**Plan.** In src/execution/operator/join/physical_hash_join.cpp, TrySetExactBloomFilter: add `static constexpr idx_t EXACT_BF_SMALL_RANGE = idx_t(1) << 22;` (512KB bitmap). Change the cap to key_cap = max(current key_cap, EXACT_BF_SMALL_RANGE), still bounded by EXACT_BF_MAX_RANGE. Keep everything else unchanged. Check that SetExactRange/bitmap allocation in bloom_filter.cpp/.hpp handles a range much larger than the key count: one shared allocation and memset, not per thread. Verify via JSON profile (SET enable_profiling='json'; SET profiling_output='<worktree>/.dbe/scratch.json'; warm the query 2-3 times first) that the q17 lineitem scans emit ~60k rows and scan CPU drops. If the ToString does not show the mode, compare scan output cardinality. Also check q08 (the part p_type filter, ~13k keys over 2M) and q02/q14/q19 plans for changed BF modes. Correctness: compare q17/q08 results and a sparse-key test (e.g. a 3-key build over a 4M range) against SET disabled_optimizers='join_filter_pushdown'.

**Target files.** src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** q17 -15..-30% (both lineitem scans, plus 6x fewer rows into two HJ probes); q08 possibly -5..-10% if its part-key BF is currently hashed; small gains on any query with a selective filter on a dimension whose key range is under 4M.

**Generality.** Any join with a small selective build side (filtered part/supplier/customer/date dims, DELIM_GET correlation keys) on integer keys with a moderate absolute range. This is common in star and snowflake queries. Possible slowdown: a 512KB bitmap probed randomly can miss L1/L2 where a tiny hashed BF fits in L1, so a scan that hits the BF with very few keys could see slightly higher probe cost. False positives drop to zero, which usually dominates.

**Risk.** Low. A two-line threshold change in already-landed, verified exact-BF code. Memory per BF is at most 512KB.



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
