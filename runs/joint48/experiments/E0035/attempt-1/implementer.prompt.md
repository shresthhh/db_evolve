You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Parallel hash-join finalize for medium builds (64K-1M rows)

**Hypothesis.** PhysicalHashJoin finalizes the hash table on a single thread whenever the build has fewer than PARALLEL_CONSTRUCT_THRESHOLD = 1,048,576 rows (physical_hash_join.cpp:388, FinalizeSingleThreaded:403). That covers both the pointer-table init memset and the Finalize/InsertHashes loop, which also fills the BF. On 8 threads, every 100K-1M row build therefore runs as a serial phase of about 40ns/row before probing can start. I measured this with a 703K-row temp-table build joined against a 15M-row orders probe: the default (serial finalize) took 77-107ms, and with PRAGMA verify_parallelism (forced parallel finalize, despite its 1-chunk-per-task overhead) it took 64-67ms. That is about 25ms of wall time saved on one join. TPC-H-style plans contain many builds of this size: q03 has a 300K customer build (that HJ is 0.20s CPU in the profile), and q05/q07/q08/q09/q02/q22 have filtered dimension and partsupp builds.

**Plan.** In src/execution/operator/join/physical_hash_join.cpp:
(1) Lower PARALLEL_CONSTRUCT_THRESHOLD from 1048576 to about 65536 rows. Keep the num_threads==1 and KeysAreSkewed checks unchanged.
(2) In HashJoinFinalizeEvent::Schedule, make the chunk count per task adaptive. CHUNKS_PER_TASK=64 means 131K rows per task, so a 300K build would get only 3 tasks. Use chunks_per_task = clamp(chunk_count / (4 * num_threads), 4, 64).
(3) In HashJoinTableInitEvent, check whether MINIMUM_ENTRIES_PER_TASK=131072 still makes sense. It probably does, because the memset is cheap.
Before the bench, A/B on the micro query with the threshold at 1M vs 64K: CREATE TEMP TABLE b AS SELECT o_orderkey bk, o_shippriority bp FROM orders WHERE o_orderkey % 256 < 3; SELECT count(*), sum(bp) FROM b JOIN orders o ON bk=o.o_orderkey. Also try 300K and 100K builds (% 256 < 1, and smaller). Check that results are identical, including with duplicate build keys: build from lineitem l_orderkey, so there are many duplicates per key, which exercises chain insert under CAS.

**Target files.** src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** Roughly 3-15ms of wall time per medium-size HJ build. q03 (customer 300K build) -3..-6%; q05/q07/q08/q09/q02/q22 a few % each; visible geomean maybe -2..-4%.

**Generality.** Every hash join with a 64K-1M row build on a multi-threaded machine, which is the most common join size class in star-schema analytics. Builds under 64K rows are unchanged. Possible slowdown: builds just above 64K that previously ran serial could pay CAS and task-scheduling overhead (~µs per task). Very skewed keys still use the single-thread path.

**Risk.** Low. The parallel InsertHashesLoop<true> path is already used for builds over 1M rows, so this only moves the threshold. Main risk is a small regression from atomic CAS cost on 64K-200K builds; tune the threshold if the micro A/B shows it.



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
