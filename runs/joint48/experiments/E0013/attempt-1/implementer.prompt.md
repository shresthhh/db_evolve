You are the implementer in db_evolve, a system that improves an existing database engine
(duckdb) by landing small, verified, general changes to its source code. Your working
directory is a checkout of the engine at the current best version. Implement the one issue below.



## The issue

### Large perfect HA v2: large-mode-only code paths, plan-identical guard for other templates

**Hypothesis.** q13 is the largest template (646ms, 16.6%). Its inner HASH_GROUP_BY on c_custkey (1.5M dense groups, 15M input rows) takes 2.40s CPU, the largest single operator in the profile. E0009 (perfect HA up to 22 bits, striped parallel combine, parallel source, lazy slot init, DELIM_SCAN guard) gave a consistent q13 -20..-23% over 3 runs. It was retired because the official bench showed q16 +14% and q18 +7.8%. Neither template should be able to reach the large mode: q16 groups by VARCHARs, q18's outer agg groups by VARCHAR c_name, and its IN-subquery agg on l_orderkey needs about 26 bits, which is more than 22. So the regressions were either noise or overhead that E0009 added to code shared by ALL perfect HAs, such as the refactored Combine (CombineRange/TakeAllocator) and the ScanRange source. Keeping the original code path for every non-large perfect HA, and confirming that the q16/q18 plans are unchanged, removes the second possibility.

**Plan.** Re-implement E0009 (see the ledger entry for the details: the plan_aggregate.cpp CanUsePerfectHashAggregate large mode up to 22 bits, with the density guard est_input >= slots/2, the memory guard slots*(state+1)*(threads+1) <= max_memory/8, the DELIM_SCAN subtree guard, and the threshold >= 12 guard; lazy per-slot InitializeStates; striped-lock parallel CombineRange; block-parallel ScanRange source). New requirements: (1) add an `is_large` flag on PhysicalPerfectHashAggregate, set only when total bits > perfect_ht_threshold. When the flag is false, Sink/Combine/Finalize/GetData must run the EXACT original code with no extra branches in hot loops, so dispatch once per operator rather than per row. Lazy init is used only in large mode. (2) Before benchmarking, compare EXPLAIN of every visible template against the current best. Only q13 (and possibly q02) may change operator type; q16/q18 must be byte-identical. Report this. (3) Run the bench for q13, q16, q18 and q17 at least twice each.

**Target files.** src/execution/physical_plan/plan_aggregate.cpp, src/execution/operator/aggregate/physical_perfecthash_aggregate.cpp, src/execution/perfect_aggregate_hashtable.cpp, src/include/duckdb/execution/perfect_aggregate_hashtable.hpp, src/include/duckdb/execution/operator/aggregate/physical_perfecthash_aggregate.hpp

**Expected gain.** q13 -20% (about -1.6% geomean); q02 small gain; all other templates unchanged by construction

**Generality.** Any GROUP BY on one or a few dense integer keys with 4K..4M groups, which is typical of FK-key aggregation such as per-customer and per-part counts. Queries with badly overestimated agg inputs could regress through memory and page faults; this is mitigated by lazy init, the density/memory guards and the DELIM guard.

**Risk.** Medium. The code is known to work from E0009. The main risk is that the official bench again flags q16/q18 noise; the plan-identity check gives the evidence to argue it is noise.



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
