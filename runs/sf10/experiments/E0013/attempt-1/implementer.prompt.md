You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.

## The issue

### Perfect hash join for RIGHT joins on dense integer keys (range up to 4M)

**Hypothesis.** q13 is the slowest template (773ms, 18.7% of total). Its customer LEFT JOIN orders runs as a physical RIGHT hash join: orders is the probe (14.8M rows), customer the build (1.5M rows, c_custkey dense in [1,1.5M]). The join costs 2.06s CPU. Each probe goes through the pointer table (about 16MB) and then compares keys in the row data, so it pays two random cache misses. PerfectHashJoinExecutor::CanDoPerfectHashJoin (perfect_hash_join_executor.cpp:73) only accepts INNER joins, and MAX_BUILD_SIZE=1048576 at :108 is a file-local constant, not a setting. So q13 is excluded twice: by join type (RIGHT) and by range (1.5M). A perfect probe indexes directly into gathered key vectors (6MB of uinteger keys for q13), with no hashing and no pointer chasing. RIGHT join probe output is the same as INNER output (the matched pairs). The only extra work is recording which build slots matched, so that the existing full-outer scan can emit unmatched build rows. Separately verified this round: in q09, compressed materialization does block the o_orderkey BF from reaching the orders scan, but with CM disabled the BF cut orders from 15M to 2.96M rows and q09 wall time was unchanged (560 vs 560ms). That direction is dead, which is why q13 is the target.

**Plan.** In src/execution/operator/join/perfect_hash_join_executor.cpp:
(1) CanDoPerfectHashJoin: also accept JoinType::RIGHT, with 1 COMPARE_EQUAL integer condition as today.
(2) Range limit: keep MAX_BUILD_SIZE=1M for the existing INNER rule. Add MAX_DENSE_BUILD_SIZE = 1<<22. A range in (1M, 4M] is allowed only if ht.Count()*2 >= range+1 (at least 50% dense). A RIGHT join of any range also requires that density, so sparse builds and builds where a BF would help stay on the normal HT.
(3) RIGHT match tracking: FullScanHashTable already gathers key_locations (the row pointers). Keep a per-slot row-pointer array and a uint8 matched-flag array, sized by build_size. In ProbePerfectHashTable (:269), when op.join_type==RIGHT, set matched[idx]=1 for each matching probe row (benign race; same as the existing HT found_match writes).
(4) Before the full-outer scan, copy matched flags into the rows' found_match field: one pass over the slots, writing through the stored pointers. Then the existing PhysicalHashJoin full-outer scan source path (physical_hash_join.cpp, ScanFullOuter / the HT's found-match offset) runs unchanged. Hook this where the probe phase finishes and the outer scan starts. Verify the HT actually checks those flags for perfect-HT joins.
(5) Build rows with NULL keys (kept in the HT for RIGHT joins) must not go into a slot. They must stay unmatched so the outer scan emits them. Check how FullScanHashTable handles them today (it may bail out or fail).
The probe output path stays the INNER one. Do not touch LEFT/OUTER/SEMI/ANTI/MARK.
Before the full bench: run EXPLAIN ANALYZE on q13.m0 and confirm the join time drops. Correctness: compare against SET disabled_optimizers='join_filter_pushdown' and the plain HT on a RIGHT join with NULL build keys, duplicate build keys (must fall back), an empty build, unmatched build rows, a negative-key range, multi-column payloads, and customer LEFT JOIN orders with count(o_orderkey) (q13 shape).

**Target files.** src/execution/operator/join/perfect_hash_join_executor.cpp, src/execution/operator/join/physical_hash_join.cpp

**Expected gain.** q13: join CPU from 2.06s to about 0.8-1.0s, so about 10-20% wall on q13 (about 1.5% geomean). Other templates mostly unchanged, unless an INNER join has a 1-4M dense build (customer at SF10 when unfiltered).

**Generality.** Helps any outer join where the preserved side is a dense-keyed dimension table: the planner puts it on the build side as RIGHT, as in the per-customer, per-part and per-supplier counts with LEFT JOIN that are common in reporting. It also helps INNER joins with dense builds of 1-4M keys. Could get slower: RIGHT joins where the perfect HT replaces a selective bloom filter (gated by the 50% density rule), and very wide build payloads where gathering into vectors costs more than the probe saves.

**Risk.** Medium. RIGHT-join correctness hinges on the found_match handoff to the outer scan and on NULL build keys. The perfect HT disables the BF, which is why the density gate exists. Most of the code is in one .cpp file, and the header change is limited to new members in perfect_hash_join_executor.hpp (not widely included).



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

This session is capped at about $1.75 of model usage and is cut off without warning when it
runs out, which loses your work. Keep exploration proportionate, and return your answer as soon as
the change builds and `bench` shows the effect. A smaller finished change beats a larger unfinished one.
