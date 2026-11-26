You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Stop compressing hash-join keys in compressed materialization

**Hypothesis.** Compressed materialization (CM) compresses both join-key columns of a single-condition comparison join. CompressComparisonJoin puts the probe key in probe_compress_bindings, which inserts __internal_compress_integral_* projections on the probe side. Those projections block the Bloom-filter pushdown into the probe scan. E0006 only plumbed min/max and key-set ranges through them, and E0008, which pushed the BF through, was retired. They also add decompress/compress pairs (q13: a 0.21s CPU decompress projection on 15M rows, then a compress). Measured on the current best with SET disabled_optimizers='compressed_materialization', JSON profile of raw q09: latency 542→335ms, CPU 3.69→2.21s. The o_orderkey=l_orderkey join drops from 1.60s to 0.73s because the orders probe scan now gets the BF and emits 2.94M rows instead of 15M. The lineitem/part join also drops from 0.54s to 0.41s, and the 0.12s compress projection disappears. Alternating warm runs of the raw query: q09 ~484→~418ms (-14%), q03 ~204→~179ms (-12%). q13, q18 and q05 were unchanged within noise. That is the whole-CM upper bound; join keys are the part that blocks the BF.

**Plan.** In src/optimizer/compressed_materialization/compress_comparison_join.cpp, CompressedMaterialization::CompressComparisonJoin: remove (or gate off) the block at lines ~57-85 that compresses both join-condition columns generically and adds lhs_colref.binding to probe_compress_bindings. Every condition then goes through GetReferencedBindings, so key columns are never compressed. Build-side payload columns are still compressed, and the probe side is still left alone. UpdateComparisonJoinStats then has nothing to update for the keys, which is fine. Step 1: measure raw q09 and q03, not wrapped in count(*), because the wrapper changes the plan. Alternate runs with and without the change. Discard the first 2-3 runs of each dbe-tool sql process, because warm-up made a false -30% on q05. Step 2: if the key-only variant gets clearly less than SET disabled_optimizers='compressed_materialization' gives on q09/q03, try variant B: return early from CompressComparisonJoin (no join CM at all; aggregate/order/distinct CM unchanged). Keep whichever is faster across the full bench. Check that EXPLAIN for q09 shows the BF on the orders scan and that q13 still uses the perfect RIGHT hash join (its keys become BIGINT instead of UINTEGER).

**Target files.** src/optimizer/compressed_materialization/compress_comparison_join.cpp

**Expected gain.** q09 -10..-14%, q03 -8..-12%; possibly q05/q07/q08 and q13 (no decompress/compress pair) a few %. Geomean about -2%.

**Generality.** Helps any join whose probe key would have been compressed by CM: integer FK joins where the build side is large enough to pass the CM thresholds. Removing the key projections lets the runtime BF, min/max and perfect-HJ filters reach the probe scan directly, and saves a projection per key. Could get slower: joins with very large builds, where 4-byte compressed keys made the hash table smaller and more cache-friendly, and memory-bound or spilling joins. The payload compression that matters most for memory is kept.

**Risk.** Low-medium. The change only removes an optimization, so correctness risk is minimal: uncompressed keys go through the same code path as joins below the CM thresholds. The main risk is performance on large-build joins without a selective BF, and the perfect HJ / exact-BF gates seeing BIGINT keys instead of compressed ones; check q13 and q18.



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
