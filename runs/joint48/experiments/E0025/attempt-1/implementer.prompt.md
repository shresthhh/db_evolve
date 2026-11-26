You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Exact BF bitmap up to 2^27 bits when 1024 bits/key allows

**Hypothesis.** In q05 the lineitem scan is the hottest operator: 0.92s CPU out of about 1.7s total, 60M rows in and 2.03M out. Its join filter is a HASHED BF over 455k o_orderkey values spread across a 60M range. TrySetExactBloomFilter (physical_hash_join.cpp:1011) caps the exact bitmap at count*128 = 58.3M bits, so this range (59.99M) misses the cap by 3%. I ran a measured A/B with no code change: I widened the orders date window by about 2 weeks, giving ~500k keys, which is enough to cross the cap. The lineitem scan dropped 0.92s -> 0.48s CPU (-48%) even though more rows qualify, and false positives went away (1.99M -> exact 1.88M rows, where the hashed BF let ~10% extra rows through). q05-shaped wall time fell from 331/256/266ms to 244/229/208/230ms (~-15%). An exact bitmap probe costs one bit test with no hashing. The probe keys (lineitem l_orderkey) come in clustered order, so even a multi-MB bitmap stays cache-friendly. Note: an earlier memory entry said raising this cap was low value because it removed only ~10% of rows. That looked at rows only; the CPU saving comes from the cheaper probe.

**Plan.** In src/execution/operator/join/physical_hash_join.cpp, TrySetExactBloomFilter (lines ~1009-1016): keep the 128 bits/key rule and the EXACT_BF_SMALL_RANGE floor, and add a mid tier. The exact bitmap is also allowed if range < MinValue(EXACT_BF_MID_RANGE = 1<<27 bits (16MB), ht.Count() * 1024). In code: key_cap = MaxValue(key_cap, MinValue<idx_t>(EXACT_BF_MID_RANGE, ht.Count()*1024)). Keep the EXACT_BF_MAX_RANGE guard and update the comment that says memory is bounded by the pointer table. Check that the bitmap allocation and zeroing in SetExactRange (bloom filter class) works for 16MB, that the build-side insert for exact mode is thread-safe for the larger size (it is already used up to 2^32 ranges with dense keys), and that the E0021 offset path calls the same function. Validate with the q05 A/B above: o_orderdate < '1995-12-25' (hashed today) must become exact, and the lineitem scan CPU should drop to about 0.48s. Results must match the old build.

**Target files.** src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** q05 -10..-15% (scan CPU -48%). Possibly q03/q07/q08/q21/q18, where sparse orderkey/custkey/partkey BFs sit between 128 and 1024 bits/key over ranges up to 134M. Geomean maybe -1..-2%.

**Generality.** Any FK join where a filtered dimension or fact (orders by date, customers by segment) builds a BF on a key range of up to ~134M values at 0.1-1% density. This is very common for star/snowflake date-filtered joins. Queries that could get slower are those with random (unclustered) probe keys against a 4-16MB bitmap: L3 misses there instead of an L2-resident hashed BF. The 1024 bits/key bound limits that to at most 128 bytes of bitmap per build key. There is also a one-time zeroing cost of up to 16MB per join.

**Risk.** Low. This only changes a threshold on an existing, verified mechanism. The main risks are random-probe cache behaviour and memory per concurrent join.



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
