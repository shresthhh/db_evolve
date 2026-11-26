You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Perfect hash join for RIGHT joins v2 (all 3 gates)

**Hypothesis.** q13 is now the largest template (785.6ms, 17.1% of total). Its plan is customer LEFT JOIN orders, run as a RIGHT HASH_JOIN with customer (1.5M dense unique c_custkey) as the build side. That join took about 1.8s CPU. The perfect HJ is never used here, because of three gates I verified in the code: (1) perfect_hash_join_executor.cpp:73 requires join_type==INNER. (2) join_filter_pushdown_optimizer.cpp:275 computes compute_aggregates_anyway only for INNER joins. The probe keys sit behind a compress projection, so probe_info is empty and the join gets no build min/max. (3) perfect_hash_join_executor.cpp:115 bails when ht.Count() > build_range. A fully dense key set has range+1 keys, so this off-by-one rejects every fully dense build, including INNER ones. A previous run fixed all three and measured q13 -20% (join operator 1.87s→0.19s CPU).

**Plan.** 1) In src/optimizer/join_filter_pushdown_optimizer.cpp near line 275, allow compute_aggregates_anyway for RIGHT joins too, as well as INNER. Single condition, equality, same conditions as today. 2) In src/execution/operator/join/perfect_hash_join_executor.cpp: (a) CanDoPerfectHashJoin at line 73 should accept JoinType::RIGHT alongside INNER. (b) Fix the dup check at line 115 to `ht.Count() > build_range + 1`. (c) RIGHT builds keep NULL-key rows in the HT with has_null=false, so the build fill must check key validity and skip NULL keys. Those rows still have to be emitted by the RIGHT scan as unmatched. (d) Track RIGHT-join matches. Mark found_match in a per-slot byte array during probe, then flush it into the HT rows' found_match field before the outer scan (PrepareScanHT / the full-outer scan path in physical_hash_join.cpp). The previous run measured this at -17.8%, against -11.6% for writing found_match into rows directly at probe time. Make sure the existing RIGHT-join outer-scan code in physical_hash_join.cpp still emits unmatched build rows. Keep MAX_BUILD_SIZE as it is.

**Target files.** src/execution/operator/join/perfect_hash_join_executor.cpp, src/execution/operator/join/physical_hash_join.cpp, src/optimizer/join_filter_pushdown_optimizer.cpp

**Expected gain.** q13 -15..-20% (about -1.5% geomean). Fixing the off-by-one may also help INNER joins on fully dense dimension keys in q02, q05 and q08 (nation, region, supplier).

**Generality.** FK joins against dense-key dimension tables with outer semantics (LEFT JOIN fact-to-dim, or dim-to-fact planned as RIGHT). Fully dense INNER builds also gain from the off-by-one fix. Downside: a sparse range close to MAX_BUILD_SIZE could cost more memory, but the existing range cap still applies.

**Risk.** Medium. RIGHT-join correctness for unmatched rows and NULL build keys is the main risk; bench results checks should catch it. The optimizer change only adds min/max aggregate computation for RIGHT joins.



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
