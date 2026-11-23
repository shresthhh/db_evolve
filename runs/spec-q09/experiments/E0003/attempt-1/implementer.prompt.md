You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## Specialisation run (this overrides the general goal below where they differ)

This run specialises the engine for ONE query shape: the visible template `q09` (instances are in `.dbe/queries/`). The only timing that
counts is on these visible templates. Other kinds of queries may
get slower, but every query must still return correct results, and it is checked on many query
shapes you cannot see.

The code must stay general in what it refers to. Specialise to the *shape* of the query (its
operators, join structure, kinds of predicates and aggregates, data types, cardinalities), never to
names: no table or column names, no literal values from the queries, no knowledge of this dataset
(row counts, value distributions), and no caching of results across executions. A condition that
only this shape of query meets is fine here; a condition that names this query is not. Parameter
values change between runs and the data size changes, so anything tied to either will fail.


## The issue

### Software prefetch of hash-table entries and rows in hash join probe

**Hypothesis.** In q09.m0 the largest operator is HASH_JOIN o_orderkey=l_orderkey at 1.77-1.87s cumulative. It makes 15M probes against a hash table built on 3.27M lineitem rows: the pointer table is about 8M entries (64MB) and the row data is over 100MB, both far larger than the caches. Probing ~15M rows costs about 120ns per row, which is a DRAM miss per probe. ProbeForPointersInternal (join_hashtable.cpp:188) loads entries[hash & bitmask] one row at a time with no prefetch, and row_matcher_build.Match then dereferences each row pointer, which is a second random miss. The codebase has no __builtin_prefetch anywhere. I checked whether a bloom filter on the orders side would avoid this. Disabling compressed_materialization lets the BF reach the orders scan (it then emits 2.96M rows instead of 15M), but wall time did not improve (533 vs 509 ms), because the scan cost rose by as much as the join saved. Hiding the miss latency inside the probe is the remaining lever.

**Plan.** In src/execution/join_hashtable.cpp: (1) In ProbeForPointersInternal<USE_SALTS,HAS_SEL>, before the main loop, add a pass over hashes_dense[0..count) that issues __builtin_prefetch(&entries[hashes_dense[i] & ht.bitmask]). Guard it with #if defined(__GNUC__) || defined(__clang__) and run it only when the table is large (ht.capacity * sizeof(ht_entry_t) above a fixed constant such as 1MB, an L2-scale constant, not tied to data). With USE_SALTS each entry fits one cache line, so the main loop then hits cache. (2) In GetRowPointersInternal, after ProbeForPointers returns keys_to_compare_count and before row_matcher_build.Match, prefetch the row pointers for keys_to_compare_sel[0..keys_to_compare_count) from pointers_result_v (data_ptr_t), under the same size guard. Make no logic changes: prefetch is only a hint, so results are identical. Optionally apply the same entry prefetch in the build insert loop (InsertRowToEntry caller, ~line 584/671) only if it is trivial; otherwise leave it out.

**Target files.** src/execution/join_hashtable.cpp

**Expected gain.** q09: the orders join (~1.8s of ~6s cumulative) could drop by 30-50%, and the 2-key lineitem join (0.67s) a little. Roughly 8-15% on q09 wall time.

**Generality.** Every hash join whose hash table exceeds the cache (large build sides: fact-to-fact joins, joins of large dimension tables, and large intermediates). Small hash tables are unaffected because of the size guard. A small regression is possible when probes are mostly sequential and cache-friendly, where the extra pass costs a loop over 2048 hashes per vector (negligible).

**Risk.** Low. No semantic change, and the prefetch is guarded to GCC/Clang. The main risk is no measurable gain, if the hardware already overlaps the misses through out-of-order execution.



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
   at least one visible template at least 5% faster (more if its timings are noisy), no visible template slower beyond its noise, and the visible geomean not slower. Templates you cannot see are not timed in this run; they only have to stay correct.

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
