You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Raise operator output caching threshold to 256 rows (sparse HJ/FILTER output coalescing)

**Hypothesis.** E0040 showed that downstream operators pay a fixed cost per chunk (about 3.5us per chunk in HJ probe). Merging filtered scan chunks below 256 rows (STANDARD_VECTOR_SIZE/8) cut the geomean 9.3% with no regressions. The same merging already exists for operator outputs in CachingPhysicalOperator (src/execution/physical_operator.cpp SelectExecutionMode, used by PhysicalJoin, PhysicalFilter and PhysicalCrossProduct). But it only triggers for chunks of at most CACHE_THRESHOLD = 64 rows (physical_operator.hpp:270). Join and filter outputs with 65-255 rows per chunk pass through unmerged, and every operator above them pays the per-chunk cost. Examples: joins against a filtered dimension that keep 6-25% of rows (region, nation or segment joins) and post-join FILTERs. In q07 hot, the n1/n2 OR FILTER keeps 50%, and 1/5 or 2/25 selective dimension joins are common in q02, q03, q05, q07 and q08. Also, every flush calls make_uniq<DataChunk> plus cached_chunk->Initialize, which reallocates the full vector set each time.

**Plan.** 1) In src/include/duckdb/execution/physical_operator.hpp, change CachingPhysicalOperator::CACHE_THRESHOLD from 64 to STANDARD_VECTOR_SIZE/8 (256 at the default vector size). Keep the existing ORDERED/PARTITIONED/continuation logic in SelectExecutionMode unchanged; it already handles correctness for every threshold. 2) Optional, if cheap: in CachingPhysicalOperator::Execute (physical_operator.cpp ~443-460), avoid the make_uniq<DataChunk> temporary in RETURN_CACHED_APPEND_CHUNK. Do this by keeping a second owned DataChunk in CachingOperatorState and swapping the two, instead of re-Initializing (allocating) after every Move. 3) Measure thresholds 128 and 256 on full bench. Check q22 and q04 alone, because the scan version regressed q22 at 512 rows, where copying about 260 rows/chunk cost as much as it saved. Report which HJ/FILTER operators in q03/q07/q08 change chunk counts (operator timing of the parents).

**Target files.** src/include/duckdb/execution/physical_operator.hpp, src/execution/physical_operator.cpp

**Expected gain.** A few % on join-heavy templates with selective dimension joins (q02, q03, q05, q07, q08); geomean -1..-3%. Uncertain, because scan-level coalescing (E0040) already densified the biggest sources.

**Generality.** Every pipeline where a hash join, filter or cross product drops most but not almost all rows. This is generic across star/snowflake joins. Queries whose operator outputs sit at 150-256 rows/chunk pay a copy that may cost about what it saves (the q22-style break-even), so 128 is the fallback threshold.

**Risk.** Low. The mechanism and its order-preserving modes already exist and are tested; only the threshold changes. Main risk is a small regression from extra copies near break-even.



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
