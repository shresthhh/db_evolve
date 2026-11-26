You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Bundle: fused integer hashed-BF probe + exact BF up to 2^27 bits at 1024 bits/key

**Hypothesis.** In r9, A/B on q05 showed the hashed BF probe costs about 2x the exact-bitmap probe: lineitem scan 0.92s vs 0.48s CPU, wall -15%. The false-positive rows hardly mattered. The extra cost is the probe pipeline in BFTableFilter::Filter (src/planner/filter/bloom_filter.cpp:171). HashInternal slices the key vector into a dictionary vector, VectorOperations::Hash writes a hashes vector, Flatten runs, LookupHashes makes a second pass, and a third pass translates the selection. For integer keys a single fused loop can do all of it: read data[sel[i]], call duckdb::Hash<T>(v) (MurmurHash64, the same hash the build side uses), and do the bf word load and mask test. Part 2 re-lands E0025 unchanged (TrySetExactBloomFilter in physical_hash_join.cpp, middle tier range < min(2^27, count*1024)). It gave q05 -9/-18/-20% with no regressions, but missed the -20.3% bar by itself. The fused probe speeds up every BF that stays hashed: ranges above the caps, more than 1024 bits/key, and hidden templates. The exact tier covers q05.

**Plan.** 1) bloom_filter.cpp, BFTableFilter::Filter, non-exact branch: if keys_v is a FLAT_VECTOR (or DICTIONARY, via ToUnifiedFormat) of an integer physical type (INT8..INT64, UINT8..UINT64), use a new template TemplatedLookupHashed<T>. Model its loop on TemplatedLookupExact (row_sel handling, validity), but compute filter.LookupOne(Hash(static_cast<T>(data[idx]))). The hash must match what VectorOperations::Hash produces for that type. Check this in src/common/vector_operations/vector_hash.cpp: for each T, HashOp uses duckdb::Hash<T>. NULLs: copy the exact path's handling, so an invalid row is not found only when the old path would also have dropped it. The old path hashes NULL to a constant hash, so either keep that behaviour or treat NULL as found (the join filters it anyway). Decide by reading HashOp's null handling. Every other type keeps the existing HashInternal path. 2) physical_hash_join.cpp TrySetExactBloomFilter: re-apply E0025. Add a tier where range < min(1<<27, count*1024), and only multiply when count <= 2^17. Correctness: use temp tables with BIGINT and INTEGER keys plus NULLs, and a build range larger than 2^27 so the filter stays hashed. Compare results against SET disabled_optimizers='join_filter_pushdown'. Use the warm JSON profile trick to check q05 lineitem scan CPU.

**Target files.** src/planner/filter/bloom_filter.cpp, src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** q05 -15..-20%, carried over from E0025. Any template whose BF stays hashed (sparse integer keys over a wide range) gets a 20-40% cheaper BF probe, probably q07/q08/q18/q21-like hidden joins. Visible geomean -1.5..-2.5%.

**Generality.** All runtime join BFs on integer keys, the most common join key type. The fused loop does the same work in fewer passes, so I expect no slowdowns. The 2^27 tier allocates up to 16MB per filter, only for builds of at most 128k keys at 1024 bits/key. Probes with poor locality over 16MB could miss L2 more often, but E0025 showed no regressions.

**Risk.** Low-medium. The probe hash must match the build hash bit for bit, or rows are dropped. That would show up as wrong results, which the correctness checks above catch. Read vector_hash.cpp for each type before relying on Hash<T>.



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
